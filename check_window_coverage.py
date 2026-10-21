# check_window_coverage.py
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from contracts import CHUNK_SCHEMA

BASE = Path(__file__).resolve().parent
INPUT_DIR = BASE / "data/replay_input_windows_v1"

spark = (
    SparkSession.builder
    .appName("MP5-Check-Window-Coverage")
    .master("local[2]")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate()
)

try:
    records = (
        spark.read
        .schema(CHUNK_SCHEMA)
        .option("multiLine", "true")
        .option("mode", "FAILFAST")
        .json(str(INPUT_DIR))
    )

    print("\nINPUT COVERAGE")

    records.agg(
        F.count("*").alias("input_records"),
        F.countDistinct("record_id").alias("distinct_record_ids"),
        F.min("ts_end").alias("min_event_time"),
        F.max("ts_end").alias("max_event_time"),
    ).show(truncate=False)

    print("\nEXPECTED TUMBLING COUNTS — ALL SAVED INPUT")

    (
        records
        .groupBy(F.window("ts_end", "60 seconds"))
        .count()
        .orderBy("window")
        .show(50, truncate=False)
    )

    print("\nEXPECTED SLIDING COUNTS — ALL SAVED INPUT")

    (
        records
        .groupBy(
            F.window("ts_end", "5 minutes", "1 minute")
        )
        .count()
        .orderBy("window")
        .show(50, truncate=False)
    )

finally:
    spark.stop()