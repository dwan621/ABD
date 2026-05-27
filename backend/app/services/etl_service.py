from pathlib import Path

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "abd_etl",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

SPARK_JOB_DIR = Path("/opt/spark-jobs")


@celery_app.task(name="etl.ingest_csv")
def ingest_csv(dataset_id: str, file_path: str, delimiter: str = ","):
    import subprocess

    job_path = SPARK_JOB_DIR / "etl" / "csv_ingest.py"
    result = subprocess.run(
        [
            "spark-submit",
            "--master", settings.spark_master_url,
            "--packages", "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2",
            str(job_path),
            "--file-path", file_path,
            "--dataset-id", dataset_id,
            "--delimiter", delimiter,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Spark job failed: {result.stderr}")
    return {"status": "ok", "stdout": result.stdout}


@celery_app.task(name="etl.run_data_quality")
def run_data_quality(dataset_id: str):
    import subprocess

    job_path = SPARK_JOB_DIR / "etl" / "data_quality.py"
    result = subprocess.run(
        [
            "spark-submit",
            "--master", settings.spark_master_url,
            str(job_path),
            "--dataset-id", dataset_id,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Data quality job failed: {result.stderr}")
    return {"status": "ok", "stdout": result.stdout}
