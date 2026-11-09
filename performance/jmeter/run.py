"""Run one bounded local JMeter experiment with its own service, DB and evidence."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import shutil
import sys
import time
import traceback
from uuid import uuid4

import requests

from analyze import analyze, load_samples

ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path(sys.executable)
JMETER = Path(os.environ.get('JMETER_BIN') or shutil.which('jmeter') or ROOT / '.tools/apache-jmeter-5.6.3/bin/jmeter')
TIMEOUT = (2, 10)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def stop_group(process):
    # JMeter launcher may keep a Java child: stop only our new process group.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    try:
        os.killpg(process.pid, signal.SIGKILL)  # Any remaining child from this owned group only.
    except ProcessLookupError:
        pass


def stop(process):
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def http(base, observations, method, path, namespace=None, body=None, key=None, code=200):
    headers = {'X-Test-Run-ID': namespace} if namespace else {}
    if key:
        headers['Idempotency-Key'] = key
    response = requests.request(method, base + path, headers=headers, json=body, timeout=TIMEOUT)
    result = response.json()
    observations.append({'method': method, 'path': path, 'namespace': namespace,
                         'body': body, 'key': key, 'status': response.status_code, 'response': result})
    assert response.status_code == code, (method, path, response.status_code, response.text)
    return result


def create_user(base, observations, namespace, verified=False):
    user = http(base, observations, 'POST', '/users', namespace, {'display_name': 'DEMO_PERF_USER'}, code=201)
    row = {'namespace': namespace, 'user_id': user['user_id'], 'display_name': user['display_name'], 'card_id': ''}
    if verified:
        http(base, observations, 'POST', f"/users/{user['user_id']}/verification", namespace,
             {'verification_name': 'DEMO_PERSON_01', 'identity_token': 'DEMO_ID_01'})
        card = http(base, observations, 'POST', f"/users/{user['user_id']}/cards", namespace,
                    {'card_token': 'DEMO_CARD_OK'}, code=201)
        row['card_id'] = card['card_id']
    return row


def counts(db):
    with sqlite3.connect(db) as connection:
        return {table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                for table in ('users', 'cards', 'payments')}


def database_state(db):
    with sqlite3.connect(db) as connection:
        return {table: connection.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall()
                for table in ('users', 'cards', 'payments')}


def cleanup(db, namespaces, guard):
    """Delete only owned spaces; verify the guard survives, then remove our guard."""
    connection = sqlite3.connect(db, timeout=5)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        with connection:
            for namespace in namespaces:
                connection.execute('DELETE FROM users WHERE test_run_id=?', (namespace,))
        remaining = {namespace: {table: connection.execute(
            f'SELECT COUNT(*) FROM {table} WHERE test_run_id=?', (namespace,)).fetchone()[0]
            for table in ('users', 'cards', 'payments')} for namespace in namespaces}
        assert all(value == 0 for row in remaining.values() for value in row.values()), remaining
        guard_count = connection.execute('SELECT COUNT(*) FROM users WHERE test_run_id=?', (guard,)).fetchone()[0]
        assert guard_count == 1, f'Unrelated guard space was changed: {guard_count}'
        with connection:
            connection.execute('DELETE FROM users WHERE test_run_id=?', (guard,))
        foreign_keys = connection.execute('PRAGMA foreign_key_check').fetchall()
        assert not foreign_keys, foreign_keys
        final = counts(db)
        assert final == {'users': 0, 'cards': 0, 'payments': 0}, final
        return {'owned_spaces_after_delete': remaining, 'guard_preserved': guard_count == 1,
                'foreign_key_check': foreign_keys, 'final_counts': final}
    finally:
        connection.close()


def environment(output):
    details = {'local_time': datetime.now().astimezone().isoformat(), 'logical_cpus': os.cpu_count()}
    for name, command in [('macos', ['sw_vers']), ('architecture', ['uname', '-m']),
                          ('memory_bytes', ['sysctl', '-n', 'hw.memsize']),
                          ('load', ['uptime']), ('vm', ['vm_stat']),
                          ('java', ['java', '-version']), ('git', ['git', 'rev-parse', 'HEAD'])]:
        if shutil.which(command[0]) is None:
            details[name] = {'available': False, 'note': 'Optional platform diagnostic unavailable'}
            continue
        result = subprocess.run(command, capture_output=True, text=True)
        details[name] = {'command': command, 'exit_code': result.returncode, 'output': result.stdout + result.stderr}
    save(output / 'environment.json', details)


def jmeter_run(args, output, port, data_file, service, expected_id=''):
    command = [str(JMETER), '-n', '-t', str(ROOT / 'performance/jmeter' / (
        'payment.jmx' if args.scenario == 'payment' else args.scenario + '.jmx')),
        '-l', str(output / 'result.jtl'), '-j', str(output / 'jmeter.log'),
        '-e', '-o', str(output / 'html-report'),
        '-Jhost=127.0.0.1', f'-Jport={port}', f'-Jthreads={args.threads}',
        f'-Jramp_up={args.ramp_up}', f'-Jduration={args.duration}', f'-Jloops={args.loops}',
        f'-Jdata_file={data_file}', f'-Jmode={args.mode}', f'-Jamount_cent={1251 if args.mode == "conflict" else 1250}',
        '-Jidempotency_key=DEMO_SHARED', f'-Jexpected_code={409 if args.mode == "conflict" else 201}',
        f'-Jexpected_payment_id={expected_id}',
        '-Jjmeter.save.saveservice.output_format=csv', '-Jjmeter.save.saveservice.timestamp_format=ms',
        '-Jjmeter.save.saveservice.assertion_results_failure_message=true',
        '-Jjmeter.save.saveservice.print_field_names=true',
        '-Jsample_variables=namespace,user_id,payment_key,payment_id']
    save(output / 'jmeter-command.json', {'argv': command, 'cwd': str(ROOT)})
    env = os.environ.copy()
    env['HEAP'] = '-Xms256m -Xmx512m -XX:MaxMetaspaceSize=256m'
    env['JVM_ARGS'] = '-Djava.awt.headless=true -Djava.util.prefs.userRoot=' + str(ROOT / '.local/jmeter-preferences')
    start = time.monotonic()
    monitor, reason = [], None
    with (output / 'console.log').open('w') as console:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=console, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                result = subprocess.run(['ps', '-axo', 'pid=,pgid=,pcpu=,rss='],
                                        capture_output=True, text=True)
                owned = [line for line in result.stdout.splitlines() if int(line.split()[0]) == service.pid or int(line.split()[1]) == process.pid]
                monitor.append({'elapsed_seconds': time.monotonic()-start, 'columns':'pid pgid pcpu rss_kib','output': '\n'.join(owned), 'exit_code': result.returncode})
                if service.poll() is not None:
                    reason = 'Owned Uvicorn exited during test'
                if time.monotonic() - start > args.duration + 100:
                    reason = 'Experiment exceeded bounded execution time'
                if result.returncode == 0:
                    for line in owned:
                        if int(line.split()[3]) > 2 * 1024 * 1024:
                            reason = 'Owned process RSS exceeded 2 GiB safety bound'
                jtl = output / 'result.jtl'
                if jtl.exists() and jtl.stat().st_size:
                    try:
                        with jtl.open() as source:
                            rows = list(csv.DictReader(source))
                        failed = sum(row.get('success') == 'false' for row in rows)
                        if len(rows) >= 20 and failed / len(rows) > 0.05:
                            reason = f'Observed failed samples {failed}/{len(rows)} > 5%; stop increasing load'
                    except (OSError, csv.Error):
                        pass  # Incomplete write is inspected again; final analyzer is authoritative.
                if reason:
                    stop_group(process)
                    break
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if process.poll() is None:
                stop_group(process)
            save(output / 'resource-monitor.json', monitor)
            save(output / 'jmeter-result.json', {'exit_code': process.returncode,
                 'elapsed_seconds': time.monotonic()-start, 'stop_reason': reason})
    samples = load_samples(output / 'result.jtl')
    summary, errors = analyze(samples)
    save(output / 'summary.json', summary)
    save(output / 'errors.json', errors)
    if args.trim_seconds:
        first = min(row['timeStamp'] for row in samples)
        steady = [row for row in samples if row['timeStamp'] >= first + args.trim_seconds * 1000]
        steady_summary, steady_errors = analyze(steady) if steady else ({'not_measured': 'No samples remain after trim'}, [])
        save(output / 'steady-summary.json', {'trim_first_seconds': args.trim_seconds, 'note': 'Filtered from real JTL; full dashboard includes ramp and cold-start samples.', **steady_summary})
    assert reason is None, reason
    assert process.returncode == 0, f'JMeter exited {process.returncode}; inspect console.log/jmeter.log'
    assert not errors, f'{len(errors)} failed JTL samples; see errors.json'
    if args.scenario == 'payment':
        assert len(samples) == args.threads * args.loops, 'Incomplete bounded payment experiment'
    assert (output / 'html-report/index.html').is_file(), 'Dashboard was not generated'
    print(json.dumps(summary['total'], ensure_ascii=False), flush=True)
    return samples


def verify_payment(args, db, base, observations, rows, output, samples):
    primary, other = rows
    if args.mode == 'conflict':
        before = json.loads((output/'database-before.json').read_text())
        assert json.loads(json.dumps(database_state(db))) == before, 'Conflict requests changed pre-existing rows'
    with sqlite3.connect(db) as connection:
        connection.row_factory = sqlite3.Row
        payments = [dict(row) for row in connection.execute('SELECT * FROM payments WHERE test_run_id=?', (primary['namespace'],))]
        expected = args.threads * args.loops if args.mode == 'unique' else 1
        assert len(payments) == expected, (len(payments), expected)
        assert all(p['status'] == 'SUCCEEDED' and p['amount_cent'] == 1250 and p['user_id'] == primary['user_id'] and p['card_id'] == primary['card_id'] for p in payments)
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
    ids = {row.get('payment_id') for row in samples}
    if args.mode != 'conflict':
        assert ids == {p['payment_id'] for p in payments}, 'JTL response IDs differ from actual DB records'
    with sqlite3.connect(db) as connection:
        assert connection.execute('SELECT COUNT(*) FROM payments WHERE test_run_id=?', (other['namespace'],)).fetchone()[0] == 0
    first = payments[0]
    queried = http(base, observations, 'GET', '/payments/' + first['payment_id'], primary['namespace'])
    assert queried == {key: first[key] for key in ('payment_id','user_id','card_id','amount_cent','status')}
    denied = http(base, observations, 'GET', '/payments/' + first['payment_id'], other['namespace'], code=404)
    assert denied == {'detail':'Payment not found'}
    other_payment = http(base, observations, 'POST', '/payments', other['namespace'],
                         {'user_id':other['user_id'],'card_id':other['card_id'],'amount_cent':1250},
                         key=first['idempotency_key'],code=201)
    assert other_payment['payment_id'] not in {p['payment_id'] for p in payments}
    http(base, observations, 'POST', '/payments', other['namespace'],
         {'user_id':primary['user_id'],'card_id':primary['card_id'],'amount_cent':1250},
         key='DEMO_CROSS_DENIED',code=404)
    assert counts(db)['payments'] == expected + 1
    save(output / 'consistency.json', {'primary_expected':expected,'primary_actual':len(payments),
         'primary_records':payments,'other_space_payment':other_payment,'cross_space_GET':404,'cross_space_POST':404,
         'response_payment_ids':sorted(x for x in ids if x), 'foreign_key_check':[],
         'note':'Other-space HTTP controls are outside JMeter samples. Thread overlap is not concurrent DB writes.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=['health','user-query','payment'],required=True)
    parser.add_argument('--mode',choices=['unique','replay','conflict'],default='unique')
    parser.add_argument('--threads',type=int,default=1)
    parser.add_argument('--ramp-up',type=int,default=1)
    parser.add_argument('--duration',type=int,default=35)
    parser.add_argument('--loops',type=int,default=-1)
    parser.add_argument('--trim-seconds',type=int,default=0)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'artifacts/performance') or output==ROOT/'artifacts/performance':
        parser.error('Output must be an experiment directory under this project artifacts/performance')
    if output.exists():
        parser.error('Output already exists; use a unique directory, never overwrite results')
    if not 1 <= args.threads <= 20 or not 0 <= args.ramp_up <= 15 or not 1 <= args.duration <= 60:
        parser.error('Local safety bounds: threads 1..20, ramp-up 0..15, duration 1..60')
    if args.scenario=='payment' and not 1 <= args.loops * args.threads <= 100:
        parser.error('Payment validation requires positive loops and at most 100 requests')
    if not 0 <= args.trim_seconds < args.duration:
        parser.error('Trim must be nonnegative and shorter than duration')
    output.mkdir(parents=True)
    signal.signal(signal.SIGTERM,lambda number,frame:sys.exit(128+number))
    observations=[]
    namespaces=[]
    service=None
    guard='DEMO_GUARD_'+uuid4().hex[:16]
    db=output/'test.db'
    exit_code=1
    try:
        environment(output)
        save(output/'invocation.json',{'argv':[str(PYTHON),*sys.argv],'cwd':str(ROOT),'started_at':datetime.now().astimezone().isoformat()})
        save(output/'source-sha256.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'service/main.py',ROOT/'service/database.py',*sorted((ROOT/'performance/jmeter').glob('*.jmx'))]})
        save(output/'parameters.json',{**vars(args),'output':str(output),
             'steady_note':'Read duration includes ramp-up. trim_seconds excludes cold/ramp samples for separate steady analysis.',
             'workers':1,'database':str(db),'sqlite_timeout_seconds':5,'java_heap_max_mib':512})
        assert JMETER.is_file(),'Approved project-local JMeter is not installed'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        command=[str(PYTHON),'-m','uvicorn','service.main:app','--host','127.0.0.1','--port',str(port),'--workers','1']
        env=os.environ.copy()
        env['PAYMENT_DB_PATH']=str(db)
        save(output/'service-command.json',{'argv':command,'PAYMENT_DB_PATH':str(db)})
        with (output/'service.log').open('w') as log:
            service=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            base=f'http://127.0.0.1:{port}'
            deadline=time.monotonic()+15
            while True:
                if service.poll() is not None: raise RuntimeError('Owned FastAPI exited during startup')
                try:
                    response=requests.get(base+'/health',timeout=(1,1))
                    if response.status_code==200 and response.json()=={'status':'ok'}: break
                except requests.ConnectionError: pass
                if time.monotonic()>deadline: raise RuntimeError('Service readiness timeout')
                time.sleep(0.1)
            create_user(base,observations,guard)
            rows=[]
            for index in range(2 if args.scenario=='payment' else 5 if args.scenario=='user-query' else 0):
                namespace='DEMO_PERF_'+uuid4().hex[:16]
                namespaces.append(namespace)  # Include partially prepared spaces in finally cleanup.
                rows.append(create_user(base,observations,namespace,args.scenario=='payment'))
            data_file=output/'users.csv'
            with data_file.open('w',newline='') as dest:
                writer=csv.DictWriter(dest,fieldnames=['namespace','user_id','display_name','card_id'])
                writer.writeheader()
                writer.writerows(rows[:1] if args.scenario=='payment' else rows)
            expected_id=''
            if args.scenario=='payment' and args.mode=='conflict':
                row=rows[0]
                seeded=http(base,observations,'POST','/payments',row['namespace'],
                     {'user_id':row['user_id'],'card_id':row['card_id'],'amount_cent':1250},key='DEMO_SHARED',code=201)
                expected_id=seeded['payment_id']
            before=database_state(db)
            save(output/'database-before.json',before)
            with sqlite3.connect(db) as connection:
                save(output/'sqlite-settings.json',{name:connection.execute('PRAGMA '+name).fetchone()[0] for name in ('journal_mode','synchronous','busy_timeout')})
            samples=jmeter_run(args,output,port,data_file,service,expected_id)
            if args.scenario=='payment': verify_payment(args,db,base,observations,rows,output,samples)
            else:
                assert database_state(db)==before,'Read-only load changed DB records'
                if rows:
                    assert http(base,observations,'GET','/users/'+rows[0]['user_id'],rows[1]['namespace'],code=404)=={'detail':'User not found'}
                save(output/'consistency.json',{'database_unchanged':True,'foreign_key_check':[],
                     'parameterized_spaces':len(rows),'cross_space_GET':404 if rows else 'not applicable'})
            save(output/'database-after.json',database_state(db))
            exit_code=0
    except BaseException:
        (output/'error.txt').write_text(traceback.format_exc())
        traceback.print_exc()
    finally:
        if service is not None:
            stop(service)
            save(output/'service-result.json',{'pid':service.pid,'exit_code':service.returncode,'stopped':service.poll() is not None})
            if service.returncode!=0: exit_code=1
        save(output/'http-checks.json',observations)
        if db.exists():
            try: save(output/'cleanup.json',cleanup(db,namespaces,guard))
            except Exception:
                (output/'cleanup-error.txt').write_text(traceback.format_exc())
                traceback.print_exc()
                exit_code=1
        (output/'exit-code.txt').write_text(str(exit_code)+'\n')
        print('Experiment:',output,'exit:',exit_code,flush=True)
    return exit_code


if __name__=='__main__':
    sys.exit(main())
