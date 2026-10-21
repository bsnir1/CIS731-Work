# contracts.py
from collections.abc import Mapping
from datetime import datetime, timezone
import math

import deal
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    TimestampType,
    DoubleType,
)

MAX_CHUNK_SECONDS = 30.0
TIME_TOLERANCE_SECONDS = 0.001

TRACK_NAME = "music"

CHUNK_SCHEMA = StructType([
    StructField("record_id", StringType(), nullable=False),
    StructField("track", StringType(), nullable=False),
    StructField("source_id", StringType(), nullable=False),

    StructField("ts_start", TimestampType(), nullable=False),
    StructField("ts_end", TimestampType(), nullable=False),
    StructField("text", StringType(), nullable=False),
    StructField("ingest_ts", TimestampType(), nullable=False),

    StructField("audio_uri", StringType(), nullable=False),
    StructField("offset_start_sec", DoubleType(), nullable=False),
    StructField("offset_end_sec", DoubleType(), nullable=False),
    StructField("source_revision", StringType(), nullable=False),
    StructField("license_class", StringType(), nullable=False),
])

TEXT_FIELDS = (
    "record_id",
    "track",
    "source_id",
    "text",
    "audio_uri",
    "source_revision",
    "license_class",
)

TIME_FIELDS = ("ts_start", "ts_end", "ingest_ts")
OFFSET_FIELDS = ("offset_start_sec", "offset_end_sec")


def is_aware_datetime(value):
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def is_finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def contract_errors(record, admitted_sources):
    """
    admitted_sources is a trusted manifest keyed by source_id.

    Each entry must contain:
      audio_uri, source_revision, license_class,
      duration_sec, approved_for_mp5

    approved_for_mp5 must reflect actual source approval.
    It is not evidence of approval by itself.
    """
    if not isinstance(record, Mapping):
        return ["record must be a mapping"]

    errors = []

    required = set(CHUNK_SCHEMA.fieldNames())
    missing = required - set(record)
    unexpected = set(record) - required

    if missing:
        errors.append(f"missing fields: {sorted(missing)}")

    if unexpected:
        errors.append(f"unexpected fields: {sorted(unexpected)}")

    for field in TEXT_FIELDS:
        value = record.get(field)

        if not isinstance(value, str):
            errors.append(f"{field} must be a non-null string")
        elif not value.strip():
            errors.append(f"{field} must not be empty")

    # Empty text is structurally allowed, but fabricated text is not.
    # Its semantics and empty-text policy require track approval.
    if record.get("track") != TRACK_NAME:
        errors.append(f"track must equal {TRACK_NAME!r}")

    for field in TIME_FIELDS:
        if not is_aware_datetime(record.get(field)):
            errors.append(
                f"{field} must be a timezone-aware datetime"
            )

    if all(is_aware_datetime(record.get(f)) for f in TIME_FIELDS):
        start = record["ts_start"].astimezone(timezone.utc)
        end = record["ts_end"].astimezone(timezone.utc)
        ingest = record["ingest_ts"].astimezone(timezone.utc)

        duration = (end - start).total_seconds()

        if not 0 < duration <= MAX_CHUNK_SECONDS:
            errors.append(
                "chunk duration must be greater than 0 "
                "and at most 30 seconds"
            )

        # Policy for completed chunks in the proposed replay.
        if ingest < end:
            errors.append("ingest_ts must not precede ts_end")

    for field in OFFSET_FIELDS:
        if not is_finite_number(record.get(field)):
            errors.append(f"{field} must be a finite number")

    offsets_valid = all(
        is_finite_number(record.get(f)) for f in OFFSET_FIELDS
    )

    if offsets_valid:
        offset_start = record["offset_start_sec"]
        offset_end = record["offset_end_sec"]

        if not 0 <= offset_start < offset_end:
            errors.append(
                "offsets must satisfy 0 <= start < end"
            )

        if all(
            is_aware_datetime(record.get(f))
            for f in ("ts_start", "ts_end")
        ):
            timestamp_duration = (
                record["ts_end"] - record["ts_start"]
            ).total_seconds()

            offset_duration = offset_end - offset_start

            if abs(
                timestamp_duration - offset_duration
            ) > TIME_TOLERANCE_SECONDS:
                errors.append(
                    "timestamp duration and audio-offset "
                    "duration disagree"
                )

    source_id = record.get("source_id")
    source = (
        admitted_sources.get(source_id)
        if isinstance(source_id, str)
        else None
    )

    if not isinstance(source, Mapping):
        errors.append("source_id is absent from the trusted manifest")
    else:
        if source.get("approved_for_mp5") is not True:
            errors.append("source is not approved for this MP5 track")

        for field in (
            "audio_uri",
            "source_revision",
            "license_class",
        ):
            if record.get(field) != source.get(field):
                errors.append(
                    f"{field} does not match the trusted manifest"
                )

        source_duration = source.get("duration_sec")

        if (
            not is_finite_number(source_duration)
            or source_duration <= 0
        ):
            errors.append("manifest has invalid source duration")
        elif offsets_valid:
            if record["offset_end_sec"] > source_duration:
                errors.append(
                    "audio offset exceeds source duration"
                )

    return errors


@deal.pre(
    lambda record, admitted_sources:
        not contract_errors(record, admitted_sources)
)
def admit_chunk(record, admitted_sources):
    """Return a validated, schema-shaped record."""
    result = {
        field.name: record[field.name]
        for field in CHUNK_SCHEMA.fields
    }

    for field in TIME_FIELDS:
        result[field] = result[field].astimezone(timezone.utc)

    for field in OFFSET_FIELDS:
        result[field] = float(result[field])

    return result

def normalize_payload(payload):
    if not isinstance(payload, Mapping):
        return payload

    record = dict(payload)

    for field in TIME_FIELDS:
        value = record.get(field)

        if isinstance(value, str):
            try:
                record[field] = datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                )
            except ValueError:
                pass

    return record