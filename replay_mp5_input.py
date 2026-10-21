# replay_mp5_input.py
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import math
import os
import time

from contracts import (
    normalize_payload,
    contract_errors,
    admit_chunk,
)

BASE = Path(__file__).resolve().parent

TEMPLATE_PATH = (
    BASE / "data/staging_notes_v1/vocadito_1_chunk_000.json"
)

MANIFEST_PATH = (
    BASE / "data/manifests_notes_v1/admitted_sources.json"
)

INPUT_DIR = BASE / "data/replay_input_v1"
TEMP_DIR = BASE / "data/replay_pending_v1"
METRICS_DIR = BASE / "output/replay_v1"

INTERVAL_SEC = 2.0

# Deliberate event-time lag at scheduled admission.
# These are test conditions, not measured results.
LAG_PATTERN_SEC = [
    0.5, 1.0, 2.0, 0.5,
    4.0, 1.0, 7.0, 2.0,
    0.5, 4.0, 1.0, 10.0,
]


def iso_utc(value):
    return value.isoformat().replace("+00:00", "Z")


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction

    lower = math.floor(position)
    upper = math.ceil(position)
    weight = position - lower

    return (
        ordered[lower] * (1 - weight)
        + ordered[upper] * weight
    )


def main():
    template = json.loads(
        TEMPLATE_PATH.read_text(encoding="utf-8")
    )
    admitted_sources = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )

    # Verify the template before creating a replay.
    template_errors = contract_errors(
        normalize_payload(template),
        admitted_sources,
    )

    if template_errors:
        raise ValueError(
            f"Template rejected: {template_errors}"
        )

    for directory in (INPUT_DIR, TEMP_DIR, METRICS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    metrics_path = METRICS_DIR / "admissions.jsonl"
    summary_path = METRICS_DIR / "lateness_summary.json"

    if (
        any(INPUT_DIR.iterdir())
        or any(TEMP_DIR.iterdir())
        or metrics_path.exists()
        or summary_path.exists()
    ):
        raise FileExistsError(
            "Replay outputs already exist. Do not overwrite "
            "records used for recovery tests. Use new run "
            "directories for a new experiment."
        )

    # Allows a brief startup interval.
    wall_origin = datetime.now(timezone.utc) + timedelta(
        seconds=2
    )
    monotonic_origin = time.monotonic() + 2

    lateness_values = []

    with metrics_path.open("x", encoding="utf-8") as log:
        for index, planned_lag in enumerate(LAG_PATTERN_SEC):
            due_monotonic = (
                monotonic_origin + index * INTERVAL_SEC
            )

            time.sleep(
                max(0.0, due_monotonic - time.monotonic())
            )

            scheduled_admission = wall_origin + timedelta(
                seconds=index * INTERVAL_SEC
            )

            event_end = scheduled_admission - timedelta(
                seconds=planned_lag
            )
            event_start = event_end - timedelta(seconds=30)

            # Actual replay-admission boundary.
            admitted_at = datetime.now(timezone.utc)

            payload = dict(template)
            payload.update({
                "record_id": (
                    f"replay_v1_vocadito_1_{index:03d}"
                ),
                "ts_start": iso_utc(event_start),
                "ts_end": iso_utc(event_end),
                "ingest_ts": iso_utc(admitted_at),
            })

            record = normalize_payload(payload)
            errors = contract_errors(
                record,
                admitted_sources,
            )

            if errors:
                raise ValueError(
                    f"{payload['record_id']} rejected: {errors}"
                )

            admit_chunk(record, admitted_sources)

            filename = f"chunk_{index:03d}.json"
            temporary = TEMP_DIR / filename
            destination = INPUT_DIR / filename

            temporary.write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )

            # Same-filesystem rename publishes a complete file.
            os.replace(temporary, destination)

            lateness = (
                admitted_at - event_end
            ).total_seconds()

            lateness_values.append(lateness)

            log.write(json.dumps({
                "record_id": payload["record_id"],
                "ts_end": payload["ts_end"],
                "ingest_ts": payload["ingest_ts"],
                "planned_lag_sec": planned_lag,
                "lateness_sec": lateness,
                "fixture_kind": "synthetic_repeated_audio",
            }) + "\n")
            log.flush()

            print(
                f"Published {filename}: "
                f"lateness={lateness:.3f}s"
            )

    summary = {
        "record_count": len(lateness_values),
        "fixture_kind": "synthetic_repeated_audio",
        "ingest_boundary": (
            "publisher admission before JSON publication"
        ),
        "p50_sec": percentile(lateness_values, 0.50),
        "p95_sec": percentile(lateness_values, 0.95),
        "p99_sec": percentile(lateness_values, 0.99),
        "max_sec": max(lateness_values),
    }

    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print("\nMeasured replay lateness:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()