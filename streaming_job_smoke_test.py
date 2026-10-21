from contracts import (
    CHUNK_SCHEMA,
    normalize_payload,
    contract_errors,
    admit_chunk,
)

# streaming_job.py
from pathlib import Path

from pyspark.sql import SparkSession

from contracts import CHUNK_SCHEMA

BASE = Path(__file__).resolve().parent

INPUT_DIR = BASE / "data/replay_input_v1"
CHECKPOINT_DIR = BASE / "output/checkpoints/replay_smoke_v1"


def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    spark = (
        SparkSession.builder
        .appName("MP5-Vocadito")
        .master("local[2]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    print("Spark version:", spark.version)
    print(
        "Session timezone:",
        spark.conf.get("spark.sql.session.timeZone"),
    )
    print("Watching:", INPUT_DIR)

    query = None

    try:
        chunks = (
            spark.readStream
            .schema(CHUNK_SCHEMA)
            .option("multiLine", "true")
            .option("mode", "FAILFAST")
            .option("maxFilesPerTrigger", 1)
            .json(str(INPUT_DIR))
        )

        query = (
            chunks.select(
                "record_id",
                "source_id",
                "ts_start",
                "ts_end",
                "ingest_ts",
                "text",
            )
            .writeStream
            .format("console")
            .outputMode("append")
            .option("truncate", "false")
            .option(
                "checkpointLocation",
                str(CHECKPOINT_DIR),
            )
            .trigger(processingTime="5 seconds")
            .start()
        )

        query.awaitTermination()

    except KeyboardInterrupt:
        print("\nStopping streaming query.")

    finally:
        if query is not None:
            query.stop()

        spark.stop()


if __name__ == "__main__":
    main()

