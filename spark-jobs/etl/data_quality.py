"""PySpark job: data quality checks on Iceberg table."""
import argparse
import json

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, isnan, when


def run_quality_checks(spark: SparkSession, dataset_id: str) -> dict:
    table_name = f"iceberg.abd.{dataset_id.replace('-', '_')}"
    df = spark.table(table_name)

    total_rows = df.count()
    checks = {"total_rows": total_rows, "columns": {}}

    for column_name in df.columns:
        null_count = df.filter(col(column_name).isNull()).count()
        null_pct = round(null_count / total_rows * 100, 2) if total_rows > 0 else 0
        distinct_count = df.select(column_name).distinct().count()

        checks["columns"][column_name] = {
            "null_count": null_count,
            "null_pct": null_pct,
            "distinct_count": distinct_count,
        }

    print(json.dumps(checks, indent=2))
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", required=True)
    args = parser.parse_args()

    spark = (
        SparkSession.builder
        .appName("ABD-DataQuality")
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.iceberg.type", "hadoop")
        .config("spark.sql.catalog.iceberg.warehouse", "s3a://datalake/")
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )

    run_quality_checks(spark, args.dataset_id)
    spark.stop()
