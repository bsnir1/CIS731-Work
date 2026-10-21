# validate_mp5_input.py
from collections import Counter
from pathlib import Path
import json
import sys
import wave

from contracts import (
    normalize_payload,
    contract_errors,
    admit_chunk,
)

BASE = Path(__file__).resolve().parent

# These must match the directories in prepare_mp5_input.py.
PAYLOAD_PATH = (
    BASE
    / "data/staging_notes_v1/vocadito_1_chunk_000.json"
)

MANIFEST_PATH = (
    BASE
    / "data/manifests_notes_v1/admitted_sources.json"
)


def load_json(path):
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing file: {path}\n"
            "Run prepare_mp5_input.py first, or correct "
            "the configured path."
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():
    raw_payload = load_json(PAYLOAD_PATH)
    admitted_sources = load_json(MANIFEST_PATH)

    record = normalize_payload(raw_payload)

    # Validate the record against the schema/business contracts.
    errors = contract_errors(record, admitted_sources)

    # Inspect the text actually saved in the payload.
    if isinstance(record, dict):
        note_text = record.get("text")
    else:
        note_text = None

    if isinstance(note_text, str):
        tokens = note_text.split()
        counts = Counter(tokens)

        print("NOTE-TEXT DIAGNOSTICS")
        print("Note count:", len(tokens))
        print("Distinct notes:", len(counts))
        print("Note frequencies:", dict(counts.most_common()))
        print()

    # Verify the local WAV exists and its duration agrees
    # with the manifest. This is an additional file check,
    # not something the original contract function does.
    if isinstance(record, dict):
        audio_uri = record.get("audio_uri")
        source_id = record.get("source_id")

        if isinstance(audio_uri, str) and audio_uri:
            audio_path = Path(audio_uri)

            if not audio_path.is_file():
                errors.append(
                    f"Audio file not found: {audio_path}"
                )
            else:
                try:
                    with wave.open(str(audio_path), "rb") as audio:
                        actual_duration = (
                            audio.getnframes()
                            / audio.getframerate()
                        )
                        sample_rate = audio.getframerate()
                        channels = audio.getnchannels()

                    print("AUDIO DIAGNOSTICS")
                    print("Audio:", audio_path)
                    print("Duration:", actual_duration, "seconds")
                    print("Sample rate:", sample_rate, "Hz")
                    print("Channels:", channels)
                    print()

                    source = (
                        admitted_sources.get(source_id)
                        if isinstance(source_id, str)
                        else None
                    )

                    if isinstance(source, dict):
                        expected_duration = source.get(
                            "duration_sec"
                        )

                        if (
                            isinstance(
                                expected_duration, (int, float)
                            )
                            and not isinstance(
                                expected_duration, bool
                            )
                        ):
                            if abs(
                                actual_duration
                                - expected_duration
                            ) > 0.001:
                                errors.append(
                                    "WAV duration does not match "
                                    "manifest duration."
                                )

                except (wave.Error, EOFError, OSError) as exc:
                    errors.append(
                        f"Cannot read WAV: {exc}"
                    )

    if errors:
        print("VALIDATION FAILED")

        for error in errors:
            print(f" - {error}")

        return 1

    # Enforce the deal precondition as well.
    accepted = admit_chunk(record, admitted_sources)

    duration = (
        accepted["ts_end"] - accepted["ts_start"]
    ).total_seconds()

    print("VALIDATION PASSED")
    print("Record ID:", accepted["record_id"])
    print("Source ID:", accepted["source_id"])
    print("Chunk duration:", duration, "seconds")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        sys.exit(1)