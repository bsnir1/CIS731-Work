# prepare_mp5_input.py
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import wave

BASE = Path(__file__).resolve().parent

RAW_WAV = BASE / "data/raw/vocadito_1.wav"
NOTES_FILE = BASE / "data/raw/vocadito_1_notesA1.csv"
ANNOTATION_SET = "A1"

PREPARED_DIR = BASE / "data/prepared_notes_v1"
MANIFEST_DIR = BASE / "data/manifests_notes_v1"
STAGING_DIR = BASE / "data/staging_notes_v1"

TRIMMED_WAV = PREPARED_DIR / "vocadito_1_first30.wav"
MANIFEST_FILE = MANIFEST_DIR / "admitted_sources.json"
PAYLOAD_FILE = STAGING_DIR / "vocadito_1_chunk_000.json"
PROVENANCE_FILE = MANIFEST_DIR / "preparation_provenance.json"

SOURCE_ID = "vocadito_1_first30"
CHUNK_SECONDS = 30

# Confirm this matches your downloaded release.
SOURCE_REVISION = "zenodo_5578807_v3"

# Set True only after actual approval of this source/track.
APPROVED_FOR_MP5 = True

import csv
import math

NOTE_NAMES = (
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B",
)


def hz_to_note_token(frequency_hz):
    if not math.isfinite(frequency_hz) or frequency_hz <= 0:
        raise ValueError("Frequency must be finite and positive.")

    midi_float = (
        69.0 + 12.0 * math.log2(frequency_hz / 440.0)
    )

    # Explicit nearest-semitone rounding policy.
    midi_note = math.floor(midi_float + 0.5)

    if not 0 <= midi_note <= 127:
        raise ValueError(
            f"Pitch outside supported MIDI range: {midi_float}"
        )

    name = NOTE_NAMES[midi_note % 12]
    octave = midi_note // 12 - 1

    return f"{name}{octave}"


def notes_to_text(notes_path, start_sec=0.0, end_sec=30.0):
    selected = []

    with notes_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.reader(file)

        for line_number, row in enumerate(reader, start=1):
            if not row or all(not value.strip() for value in row):
                continue

            if len(row) != 3:
                raise ValueError(
                    f"{notes_path}, line {line_number}: "
                    "expected onset, frequency, duration."
                )

            try:
                onset, frequency_hz, duration = map(float, row)
            except ValueError as exc:
                raise ValueError(
                    f"{notes_path}, line {line_number}: "
                    "expected three numeric values. "
                    "Check whether the file has a header "
                    "or is the wrong annotation type."
                ) from exc

            if not all(
                math.isfinite(value)
                for value in (onset, frequency_hz, duration)
            ):
                raise ValueError(
                    f"Nonfinite annotation on line {line_number}"
                )

            if onset < 0 or duration <= 0 or frequency_hz <= 0:
                raise ValueError(
                    f"Invalid annotation on line {line_number}"
                )

            # Include notes whose onsets belong to [0, 30).
            if start_sec <= onset < end_sec:
                selected.append((
                    onset,
                    line_number,
                    hz_to_note_token(frequency_hz),
                ))

    selected.sort(key=lambda item: (item[0], item[1]))

    if not selected:
        raise ValueError(
            "No reference notes begin inside the selected interval."
        )

    return " ".join(token for _, _, token in selected)


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            h.update(block)

    return h.hexdigest()


def iso_utc(value):
    return value.isoformat().replace("+00:00", "Z")


def main():
    for path in (RAW_WAV, NOTES_FILE):
        if not path.is_file():
            raise FileNotFoundError(path)

#    lyrics = LYRICS_FILE.read_text(
#        encoding="utf-8"
#    ).strip()
#
 #   if not lyrics:
  #      raise ValueError(
   #         "Add the verified first-30-second lyrics "
    #        "to the lyrics text file."
     #   )

    for directory in (
        PREPARED_DIR,
        MANIFEST_DIR,
        STAGING_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    targets = (
        TRIMMED_WAV,
        MANIFEST_FILE,
        PAYLOAD_FILE,
        PROVENANCE_FILE,
    )

    if any(path.exists() for path in targets):
        raise FileExistsError(
            "Prepared outputs already exist. Preserve them "
            "for replay/restart tests; use a new run directory "
            "for a deliberate rebuild."
        )

    with wave.open(str(RAW_WAV), "rb") as source:
        sample_rate = source.getframerate()
        frame_count = CHUNK_SECONDS * sample_rate

        if source.getnframes() < frame_count:
            raise ValueError(
                "Source audio is shorter than 30 seconds."
            )

        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        frames = source.readframes(frame_count)

    with wave.open(str(TRIMMED_WAV), "wb") as destination:
        destination.setnchannels(channels)
        destination.setsampwidth(sample_width)
        destination.setframerate(sample_rate)
        destination.writeframes(frames)

    with wave.open(str(TRIMMED_WAV), "rb") as trimmed:
        actual_duration = (
            trimmed.getnframes() / trimmed.getframerate()
        )

    assert actual_duration == 30.0

    admitted_sources = {
        SOURCE_ID: {
            "audio_uri": str(TRIMMED_WAV.resolve()),
            "source_revision": SOURCE_REVISION,
            "license_class": "CC-BY-4.0",
            "duration_sec": actual_duration,
            "approved_for_mp5": APPROVED_FOR_MP5,
        }
    }

    # Synthetic event timeline for this prepared replay record.
    # This creates no measured lateness distribution.
    ingest_ts = datetime.now(timezone.utc)
    ts_end = ingest_ts
    ts_start = ts_end - timedelta(seconds=CHUNK_SECONDS)
    note_text = notes_to_text(
        NOTES_FILE,
        start_sec=0.0,
        end_sec=30.0,
    )

    raw_payload = {
        "record_id": "vocadito_1_chunk_000",
        "track": "music",
        "source_id": SOURCE_ID,

        "ts_start": iso_utc(ts_start),
        "ts_end": iso_utc(ts_end),
        "ingest_ts": iso_utc(ingest_ts),

        "text": note_text,

        "audio_uri": str(TRIMMED_WAV.resolve()),
        "offset_start_sec": 0.0,
        "offset_end_sec": actual_duration,

        "source_revision": SOURCE_REVISION,
        "license_class": "CC-BY-4.0",
    }

    provenance = {
        "original_audio": str(RAW_WAV.resolve()),
        "original_sha256": sha256_file(RAW_WAV),
        "trimmed_audio": str(TRIMMED_WAV.resolve()),
        "trimmed_sha256": sha256_file(TRIMMED_WAV),
        "notes_file": str(NOTES_FILE.resolve()),
        "notes_sha256": sha256_file(NOTES_FILE),
        "annotation_set": ANNOTATION_SET,
        "text_kind": "reference_note_names",
        "pitch_mapping": "nearest_semitone_sharp_spelling",
        "note_selection": "onset_in_[0,30)",
        "original_offset_start_sec": 0.0,
        "original_offset_end_sec": actual_duration,
        "event_time_kind": "synthetic_replay",
        "ingest_time_kind": "preparation_admission",
        "prepared_at_utc": iso_utc(ingest_ts),
    }

    for path, content in (
        (MANIFEST_FILE, admitted_sources),
        (PAYLOAD_FILE, raw_payload),
        (PROVENANCE_FILE, provenance),
    ):
        path.write_text(
            json.dumps(content, indent=2),
            encoding="utf-8",
        )

    print(f"Prepared audio: {TRIMMED_WAV}")
    print(f"Duration: {actual_duration} seconds")
    print(f"Manifest: {MANIFEST_FILE}")
    print(f"Staged payload: {PAYLOAD_FILE}")


if __name__ == "__main__":
    main()