from pathlib import Path
import wave

AUDIO_PATH = Path(
    "/workspaces/MP2/data/raw/vocadito_1.wav"
).resolve()

if not AUDIO_PATH.is_file():
    raise FileNotFoundError(
        f"Audio file not found: {AUDIO_PATH}"
    )

with wave.open(str(AUDIO_PATH), "rb") as audio:
    duration_sec = (
        audio.getnframes() / audio.getframerate()
    )

SOURCE_ID = "vocadito_1"

admitted_sources = {
    SOURCE_ID: {
        "audio_uri": str(AUDIO_PATH),
        "source_revision": "zenodo_5578807_v3",
        "license_class": "CC-BY-4.0",
        "duration_sec": duration_sec,

        # Change only after actual source/track approval.
        "approved_for_mp5": False,
    }
}

from datetime import datetime, timedelta, timezone

REPLAY_ORIGIN = datetime(
    2026, 10, 20, 18, 0, 0,
    tzinfo=timezone.utc,
)

SIMULATED_DELAY_SEC = 2.0
MAX_CHUNK_SEC = 30.0

def iso_utc(value):
    return value.isoformat().replace("+00:00", "Z")

raw_payloads = []

chunk_index = 0

while chunk_index * MAX_CHUNK_SEC < duration_sec:
    offset_start = chunk_index * MAX_CHUNK_SEC
    offset_end = min(
        offset_start + MAX_CHUNK_SEC,
        duration_sec,
    )

    ts_start = REPLAY_ORIGIN + timedelta(
        seconds=offset_start
    )
    ts_end = REPLAY_ORIGIN + timedelta(
        seconds=offset_end
    )

    simulated_ingest_ts = ts_end + timedelta(
        seconds=SIMULATED_DELAY_SEC
    )

    raw_payloads.append({
        "record_id": (
            f"{SOURCE_ID}_chunk_{chunk_index:03d}"
        ),
        "track": "music",
        "source_id": SOURCE_ID,

        "ts_start": iso_utc(ts_start),
        "ts_end": iso_utc(ts_end),
        "ingest_ts": iso_utc(simulated_ingest_ts),

        "text": "",

        "audio_uri": str(AUDIO_PATH),
        "offset_start_sec": float(offset_start),
        "offset_end_sec": float(offset_end),

        "source_revision": (
            admitted_sources[SOURCE_ID]["source_revision"]
        ),
        "license_class": (
            admitted_sources[SOURCE_ID]["license_class"]
        ),
    })

    chunk_index += 1

from contracts import (
    normalize_payload,
    contract_errors,
    admit_chunk,
)

accepted_records = []
rejected_records = []

for raw_payload in raw_payloads:
    record = normalize_payload(raw_payload)
    errors = contract_errors(
        record,
        admitted_sources,
    )

    if errors:
        rejected_records.append({
            "record_id": record.get("record_id"),
            "errors": errors,
        })
    else:
        accepted_records.append(
            admit_chunk(record, admitted_sources)
        )

print("Accepted:", len(accepted_records))
print("Rejected:", rejected_records)