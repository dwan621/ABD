import os
import time
from pathlib import Path

from pyspark.sql import SparkSession

from app.core.config import settings

_spark: SparkSession | None = None

SPARK_JOB_DIR = Path("/opt/spark-jobs")
WAREHOUSE_DIR = "/app/data/spark-warehouse"


def _build_spark() -> SparkSession:
    spark = (
        SparkSession.builder
        .appName("ABD-Platform")
        .master(settings.spark_master_url)
        .config("spark.sql.warehouse.dir", f"file://{WAREHOUSE_DIR}")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .getOrCreate()
    )
    _register_parquet_tables(spark)
    return spark


def _register_parquet_tables(spark: SparkSession) -> None:
    """Register Parquet-backed tables so they are queryable without Derby metastore."""
    for name, path in _discover_tables().items():
        if os.path.isdir(path):
            df = spark.read.parquet(f"file://{path}")
            df.createOrReplaceTempView(name)


def _discover_tables() -> dict[str, str]:
    """Discover available parquet tables under the warehouse dir."""
    tables = {}
    warehouse = Path(WAREHOUSE_DIR)
    if not warehouse.exists():
        return tables
    for entry in warehouse.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            tables[entry.name] = str(entry)
    return tables


def get_spark() -> SparkSession:
    global _spark
    if _spark is None:
        _spark = _build_spark()
    return _spark


def execute_sql(sql: str) -> dict:
    spark = get_spark()
    start = time.time()
    df = spark.sql(sql)
    columns = df.columns
    rows = [list(row) for row in df.limit(1000).collect()]
    elapsed_ms = (time.time() - start) * 1000
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "execution_time_ms": round(elapsed_ms, 2),
    }
