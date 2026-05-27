import time
from pathlib import Path

from pyspark.sql import SparkSession

from app.core.config import settings

_spark: SparkSession | None = None

SPARK_JOB_DIR = Path("/opt/spark-jobs")


def _build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("ABD-Platform")
        .master(settings.spark_master_url)
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.iceberg.type", "hadoop")
        .config("spark.sql.catalog.iceberg.warehouse", f"s3a://{settings.minio_bucket}/")
        .config("spark.hadoop.fs.s3a.endpoint", f"http://{settings.minio_endpoint}")
        .config("spark.hadoop.fs.s3a.access.key", settings.minio_root_user)
        .config("spark.hadoop.fs.s3a.secret.key", settings.minio_root_password)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .getOrCreate()
    )


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
