"""Analyze real CSV JTL samples; exit 0=pass, 1=failed samples, 2=invalid input."""

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import sys


def load_samples(path):
    """Reject incomplete/malformed input rather than report misleading metrics."""
    required = {"timeStamp", "elapsed", "label", "responseCode",
                "responseMessage", "success", "failureMessage"}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"JTL missing columns: {sorted(required - set(reader.fieldnames or []))}")
        samples = []
        for line, row in enumerate(reader, start=2):
            try:
                if None in row or any(row[key] is None for key in required):
                    raise ValueError("incomplete CSV row")
                if row["success"].lower() not in {"true", "false"}:
                    raise ValueError("success must be true or false")
                timestamp, elapsed = int(row["timeStamp"]), int(row["elapsed"])
                if timestamp < 0 or elapsed < 0 or not row["label"]:
                    raise ValueError("negative timing or empty label")
                samples.append({**row, "timeStamp": timestamp, "elapsed": elapsed,
                                "success": row["success"].lower() == "true"})
            except (ValueError, TypeError) as error:
                raise ValueError(f"JTL line {line}: {error}") from error
    if not samples:
        raise ValueError("JTL contains no samples")
    return samples


def failure_categories(sample):
    """Categories can overlap: an HTTP 500 can also fail a JSON assertion."""
    categories = []
    text = (sample["responseCode"] + " " + sample["responseMessage"]).lower()
    if "timeout" in text or "timed out" in text:
        categories.append("timeout")
    elif any(word in text for word in ("non http", "connectexception", "connection",
                                      "unknownhost", "noroutetohost", "socketexception")):
        categories.append("connection")
    code = sample["responseCode"]
    if len(code) == 3 and code.isdigit():
        if code.startswith("4"):
            categories.append("http_4xx")
        elif code.startswith("5"):
            categories.append("http_5xx")
    if sample["failureMessage"].strip():
        categories.append("assertion")
    return categories or ["other"]


def metrics(samples):
    elapsed = sorted(sample["elapsed"] for sample in samples)
    count = len(samples)
    failed = sum(not sample["success"] for sample in samples)
    wall = (max(sample["timeStamp"] + sample["elapsed"] for sample in samples)
            - min(sample["timeStamp"] for sample in samples)) / 1000
    return {
        "count": count, "passed": count - failed, "failed": failed,
        "error_rate_percent": 100 * failed / count,
        "elapsed_wall_seconds": wall, "rps": count / wall if wall else None,
        "elapsed_ms": {"min": elapsed[0], "max": elapsed[-1],
                       "mean": sum(elapsed) / count,
                       **{f"p{p}": elapsed[math.ceil(p / 100 * count) - 1]
                          for p in (90, 95, 99)}},
        "response_code_counts": dict(sorted(Counter(s["responseCode"] for s in samples).items())),
        "expected_409_count": sum(s["responseCode"] == "409" and s["success"] for s in samples),
    }


def analyze(samples):
    groups = defaultdict(list)
    errors = []
    for sample in samples:
        groups[sample["label"]].append(sample)
        if not sample["success"]:
            errors.append({**sample, "failure_categories": failure_categories(sample)})
    summary = {
        "methods": {
            "percentile": "Nearest rank: sorted elapsed[ceil(p/100*N)-1]; JMeter dashboard may differ.",
            "wall_time": "(max(timeStamp + elapsed) - min(timeStamp))/1000, independently per group.",
            "rps": "All completed samples / elapsed wall seconds; not new payment transaction TPS.",
            "errors": "success != true; expected HTTP 409 with success=true is not an error.",
            "categories": "Overlapping hints from code/message/assertion, not confirmed root causes.",
            "assertions": "JSON/status assertions apply to the sampler label; inspect failureMessage.",
        },
        "total": metrics(samples),
        "by_label": {label: metrics(group) for label, group in sorted(groups.items())},
        "failure_category_counts": dict(Counter(c for s in errors for c in s["failure_categories"])),
    }
    return summary, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jtl", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary, errors = analyze(load_samples(args.jtl))
        args.output.mkdir(parents=True, exist_ok=True)
        for name, data in (("summary.json", summary), ("errors.json", errors)):
            (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
        total = summary["total"]
        print(f"Samples={total['count']} passed={total['passed']} failed={total['failed']} "
              f"error_rate={total['error_rate_percent']:.3f}% rps={total['rps']}")
        print(f"Analysis: {args.output.resolve()}")
        return 1 if errors else 0
    except (OSError, ValueError, csv.Error) as error:
        print(f"Analysis rejected: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
