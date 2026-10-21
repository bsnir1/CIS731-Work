from collections import defaultdict
from pathlib import Path
import json
import statistics

BASE = Path(__file__).resolve().parent
METRICS_PATH = BASE / "output/windows_v1/metrics.jsonl"

groups = defaultdict(list)
seen = set()

with METRICS_PATH.open(encoding="utf-8") as file:
    for line in file:
        if not line.strip():
            continue

        item = json.loads(line)

        key = (
            item["id"],
            item["runId"],
            item["batchId"],
        )

        if key in seen:
            continue

        seen.add(key)
        groups[item.get("name", item["id"])].append(item)

for name, entries in groups.items():
    data_batches = [
        item for item in entries
        if item.get("numInputRows", 0) > 0
    ]

    durations = [
        item["durationMs"]["triggerExecution"]
        for item in entries
        if "triggerExecution" in item.get("durationMs", {})
    ]

    state_rows = [
        operator.get("numRowsTotal", 0)
        for item in entries
        for operator in item.get("stateOperators", [])
    ]

    watermarks = [
        item["eventTime"]["watermark"]
        for item in entries
        if "watermark" in item.get("eventTime", {})
    ]

    print(f"\nQUERY: {name}")
    print("Logged progress entries:", len(entries))
    print("Data-bearing batches:", len(data_batches))
    print(
        "Logged source input rows:",
        sum(item.get("numInputRows", 0) for item in entries),
    )

    for field in (
        "inputRowsPerSecond",
        "processedRowsPerSecond",
    ):
        values = [
            item[field]
            for item in data_batches
            if field in item
        ]

        if values:
            print(
                f"Mean batch {field}:",
                round(statistics.mean(values), 3),
            )

    if durations:
        print(
            "Mean trigger execution, ms:",
            round(statistics.mean(durations), 3),
        )
        print(
            "Maximum trigger execution, ms:",
            max(durations),
        )

    if state_rows:
        print("Maximum operator state rows:", max(state_rows))

    if watermarks:
        print("Maximum logged watermark:", max(watermarks))