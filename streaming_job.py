# streaming_job.py
from pathlib import Path
import json
import time
import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from contracts import CHUNK_SCHEMA

BASE = Path(__file__).resolve().parent

EXPERIMENT = os.environ.get(
    "MP5_EXPERIMENT",
    "reference_v1",
)

INPUT_DIR = BASE / "data/replay_input_windows_v1"

OUTPUT_ROOT = BASE / "output" / EXPERIMENT

CHECKPOINT_ROOT = (
    BASE / "output/checkpoints" / EXPERIMENT
)

METRICS_PATH = OUTPUT_ROOT / "metrics.jsonl"

WATERMARK_DELAY = "11 seconds"

# Vocabulary for this specific vocadito_1 fixture.
NOTE_VOCABULARY = (
    "A2", "A#2", "B2", "C3", "C#3",
    "D3", "D#3", "F3", "F#3", "G3",
)


def build_window_result(tokens, duration, slide, window_type):
    counters = [
        F.sum(
            F.when(F.col("token") == note, 1).otherwise(0)
        ).alias(f"note_count_{index}")
        for index, note in enumerate(NOTE_VOCABULARY)
    ]

    grouped = (
        tokens
        .withWatermark("ts_end", WATERMARK_DELAY)
        .groupBy(
            F.window("ts_end", duration, slide)
        )
        .agg(
            # Count each chunk once, at its first token.
            F.sum(
                F.when(F.col("token_position") == 0, 1)
                .otherwise(0)
            ).alias("record_count"),

            F.approx_count_distinct("token").alias(
                "approx_distinct_notes"
            ),

            # Average once per chunk, not once per note.
            F.avg(
                F.when(
                    F.col("token_position") == 0,
                    F.col("ingest_latency_sec"),
                )
            ).alias("mean_ingest_latency_sec"),

            *counters,
        )
    )

    # Negative count sorts most frequent first.
    # The note name breaks ties deterministically.
    ranked = F.sort_array(
        F.array(*[
            F.struct(
                (-F.col(f"note_count_{index}")).alias(
                    "negative_count"
                ),
                F.lit(note).alias("note"),
            )
            for index, note in enumerate(NOTE_VOCABULARY)
        ])
    )

    nonzero = F.filter(
        ranked,
        lambda item: item["negative_count"] < 0,
    )

    top_ten = F.transform(
        F.slice(nonzero, 1, 10),
        lambda item: F.struct(
            item["note"].alias("note"),
            (-item["negative_count"]).alias("count"),
        ),
    )

    return grouped.select(
        F.lit(window_type).alias("window_type"),
        F.col("window.start").alias("window_start"),
        F.col("window.end").alias("window_end"),
        "record_count",
        "approx_distinct_notes",
        "mean_ingest_latency_sec",
        top_ten.alias("top_10_notes"),
    )


def start_sink(result, name):
    return (
        result.writeStream
        .queryName(name)
        .format("parquet")
        .outputMode("append")
        .option(
            "path",
            str(OUTPUT_ROOT / name),
        )
        .option(
            "checkpointLocation",
            str(CHECKPOINT_ROOT / name),
        )
        .trigger(processingTime="5 seconds")
        .start()
    )


def main():
    for directory in (
        INPUT_DIR,
        OUTPUT_ROOT,
        CHECKPOINT_ROOT,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    spark = (
        SparkSession.builder
        .appName("MP5-Vocadito-Windows")
        .master("local[2]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    print("Spark version:", spark.version)
    print("Input:", INPUT_DIR)
    print("Watermark delay:", WATERMARK_DELAY)

    queries = []

    try:
        chunks = (
            spark.readStream
            .schema(CHUNK_SCHEMA)
            .option("multiLine", "true")
            .option("mode", "FAILFAST")
            .option("maxFilesPerTrigger", 10)
            .json(str(INPUT_DIR))
        )

        prepared = (
            chunks
            .withColumn(
                "ingest_latency_sec",
                F.col("ingest_ts").cast("double")
                - F.col("ts_end").cast("double"),
            )
            .withColumn(
                "note_tokens",
                F.split(F.trim("text"), r"\s+"),
            )
        )

        # Fail rather than silently omit unsupported pitches.
        allowed = F.array(*[
            F.lit(note) for note in NOTE_VOCABULARY
        ])

        invalid = (
            F.col("text").isNull()
            | (F.length(F.trim("text")) == 0)
            | (
                F.size(
                    F.array_except(
                        F.col("note_tokens"),
                        allowed,
                    )
                ) > 0
            )
        )

        prepared = prepared.withColumn(
            "checked_tokens",
            F.when(
                invalid,
                F.raise_error(
                    "Empty or unsupported note-token text"
                ),
            ).otherwise(F.col("note_tokens")),
        )

        tokens = prepared.select(
            "ts_end",
            "ingest_latency_sec",
            F.posexplode("checked_tokens").alias(
                "token_position",
                "token",
            ),
        )

        tumbling = build_window_result(
            tokens,
            "60 seconds",
            "60 seconds",
            "tumbling_60s",
        )

        sliding = build_window_result(
            tokens,
            "5 minutes",
            "1 minute",
            "sliding_5m_1m",
        )

        queries.append(
            start_sink(tumbling, "tumbling_60s")
        )
        queries.append(
            start_sink(sliding, "sliding_5m_1m")
        )

        seen_progress = set()

        with METRICS_PATH.open(
            "a", encoding="utf-8"
        ) as log:
            while True:
                for query in queries:
                    if query.exception() is not None:
                        raise RuntimeError(
                            str(query.exception())
                        )

                    for progress in query.recentProgress:
                        key = (
                            progress["id"],
                            progress["runId"],
                            progress["batchId"],
                        )

                        if key not in seen_progress:
                            log.write(
                                json.dumps(progress) + "\n"
                            )
                            log.flush()
                            seen_progress.add(key)

                if not all(q.isActive for q in queries):
                    break

                time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping queries.")

    finally:
        for query in queries:
            if query.isActive:
                query.stop()

        spark.stop()


if __name__ == "__main__":
    main()