from pathlib import Path
from pyspark.sql import SparkSession

BASE = Path(__file__).resolve().parent

spark = (
    SparkSession.builder
    .appName("Inspect-MP5-Windows")
    .master("local[2]")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate()
)

try:
    for name in ("tumbling_60s", "sliding_5m_1m"):
        path = BASE / "output/windows_v1" / name

        print(f"\n{name}")

        results = spark.read.parquet(str(path))

        results.orderBy(
            "window_start"
        ).show(30, truncate=False)

finally:
    spark.stop()