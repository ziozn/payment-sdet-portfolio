# JMeter脚本与性能报告

被测对象为本机FastAPI模拟后端，Android不参与，不涉及真实支付。脚本：[health](../performance/jmeter/health.jmx)、[user-query](../performance/jmeter/user-query.jmx)、[payment](../performance/jmeter/payment.jmx)、[runner](../performance/jmeter/run.py)、[分析器](../performance/jmeter/analyze.py)。

## 安装与Smoke
固定Apache JMeter5.6.3，验证使用JDK21；[官方要求](https://jmeter.apache.org/changes.html)为Java8+。不用第三方插件。下载官方发行版，先核对摘要再解压：

~~~sh
mkdir -p .tools
curl -fL https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.tgz -o .tools/apache-jmeter-5.6.3.tgz
curl -fL https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.tgz.sha512 -o .tools/apache-jmeter-5.6.3.tgz.sha512
(cd .tools && shasum -a 512 -c apache-jmeter-5.6.3.tgz.sha512)
tar -xzf .tools/apache-jmeter-5.6.3.tgz -C .tools
.venv/bin/python performance/jmeter/run.py --scenario health --threads 1 --ramp-up 1 --duration 10 --loops 3 --output artifacts/performance/health-smoke-01
.venv/bin/python performance/jmeter/run.py --scenario payment --mode replay --threads 1 --ramp-up 1 --duration 10 --loops 3 --output artifacts/performance/replay-smoke-01
~~~

JMETER_BIN可指定已有官方工具，或从PATH查找。每次输出目录必须全新。JTL、summary/errors、cleanup、consistency和HTML均放在该次目录。退出0之外仍需看清理/一致性；不上传完整JTL。

本次官方归档网络下载超时，实际使用此前下载、重新匹配新取得官方SHA-512的归档，在独立目录解压。没有使用未校验的半下载文件，工具不随源码发布；“从零网络下载完成”标NOT VERIFIED。

## 本次新Smoke（2026-11-07）
| 场景 | 线程 | 样本 | 失败 | 平均ms | P95 | P99 | 采样秒 | 观察HTTP RPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| public-smoke-authorized-01 | 1 | 3 | 0 | 6.667 | 18 | 18 | 0.353 | 8.50 |
| public-payment-replay-01 | 1 | 3 | 0 | 7.333 | 19 | 19 | 0.086 | 34.88 |

[实际Smoke/清理与一致性记录](evidence/jmeter-smoke.json)。重放3次成功对应主空间1笔交易；其他空间独立，最终三表0、外键检查空、guard保留后才清理。有限loops提前结束，duration10不是实际压测10秒，3样本不能给出稳态容量。

## 历史正式实验（2026-10-29）
以下来自原始summary.json，11场共639,503样本；不包含Smoke和独立warmup，不是本次重新压测。8场读取为35秒含ramp-up，支付为5线程有限循环。原环境macOS26.6.2/ARM64/16GiB、JDK21/JMeter5.6.3、单Uvicorn worker、SQLite DELETE journal、5秒锁等待；发生器与服务同机。

| 场景 | 线程 | 样本 | 均值ms | P95 | P99 | HTTP RPS | 失败 |
|---|---:|---:|---:|---:|---:|---:|---:|
| health-baseline-t1-01 | 1 | 58166 | 0.540 | 1 | 1 | 1664.83 | 0 |
| health-load-t5-01 | 5 | 105080 | 1.558 | 2 | 3 | 3006.84 | 0 |
| health-load-t10-01 | 10 | 110471 | 2.913 | 4 | 5 | 3160.56 | 0 |
| health-load-t20-01 | 20 | 121800 | 5.308 | 7 | 8 | 3484.38 | 0 |
| user-query-baseline-t1-01 | 1 | 42842 | 0.717 | 1 | 1 | 1226.23 | 0 |
| user-query-load-t5-01 | 5 | 67392 | 2.411 | 3 | 4 | 1928.57 | 0 |
| user-query-load-t10-01 | 10 | 67152 | 4.782 | 7 | 8 | 1921.65 | 0 |
| user-query-load-t20-01 | 20 | 66520 | 9.710 | 14 | 17 | 1903.24 | 0 |
| payment-unique-t5-01 | 5 | 50 | 11.460 | 26 | 32 | 164.47 | 0 |
| payment-replay-t5-01 | 5 | 20 | 14.700 | 31 | 42 | 109.29 | 0 |
| payment-conflict-t5-01 | 5 | 10 | 17.100 | 24 | 24 | 78.12 | 0 |

[机器可读历史统计及来源摘要](evidence/historical-performance.json)。unique50请求写50笔、replay20请求仅1笔、conflict10次预期409保留原1笔；预期409通过精确状态/JSON断言，不计业务失败。控制请求不计入JMeter采样。

## 指标与限制
RPS=完成HTTP样本数/真实采样窗口，窗口为(max(timestamp+elapsed)-min(timestamp))/1000；分位数按最近秩法。JMeter Dashboard算法可能不同，不能混用。毫秒粒度的0不代表无成本。

历史用户查询5→10→20线程，RPS约1928.57→1921.65→1903.24，P95为3→7→14ms，呈现平台与延迟上升。单worker调度、逐请求SQLite连接、发生器和日志开销可能参与，未做受控实验，不能断言已定位瓶颈或容量上限。

读取RPS不是支付TPS；重放HTTP成功不等于新增交易。支付采样仅0.128–0.304秒，不用于稳态容量。没有生产网络、长稳态、SLA或多实例压测；0错误只说明该次样本通过业务约定。

runner限制20线程/60秒、支付最多100请求，保留监控/失败数据并尝试清理；强杀/断电无法保证finally。禁止指向真实支付或生产数据库。
