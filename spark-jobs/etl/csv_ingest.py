"""PySpark job: ingest CSV file and write to Iceberg table."""
import argparse

from pyspark.sql import SparkSession
from pyspark.sql.types import DoubleType, LongType, StringType, TimestampType


def infer_spark_type(dtype: str):
    mapping = {
        "int64": LongType(),
        "float64": DoubleType(),
        "object": StringType(),
        "datetime64[ns]": TimestampType(),
        "string": StringType(),
        "long": LongType(),
        "double": DoubleType(),
    }
    return mapping.get(dtype, StringType())


def ingest_csv(spark: SparkSession, file_path: str, dataset_id: str, delimiter: str = ","):
    df = spark.read.option("header", "true").option("delimiter", delimiter).option("inferSchema", "true").csv(file_path)

    for col_name in df.columns:
        clean = col_name.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        df = df.withColumnRenamed(col_name, clean)

    table_name = f"iceberg.abd.{dataset_id.replace('-', '_')}"
    df.writeTo(table_name).createOrReplace()

    row_count = df.count()
    print(f"Ingested {row_count} rows into {table_name}")
    return row_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--delimiter", default=",")
    args = parser.parse_args()

    spark = (
        SparkSession.builder
        .appName("ABD-CSV-Ingest")
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

    rows = ingest_csv(spark, args.file_path, args.dataset_id, args.delimiter)
    print(f"Done. {rows} rows written.")
    spark.stop()
