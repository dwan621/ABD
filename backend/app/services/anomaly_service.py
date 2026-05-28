import logging

from app.services.spark_bridge import execute_sql, get_spark

logger = logging.getLogger(__name__)


def detect_anomalies(table_name: str, schema_json: list[dict]) -> list[dict]:
    """Detect anomalies in a dataset using statistical methods.

    Returns list of dicts with: column_name, anomaly_type, severity, detected_value, expected_range
    """
    numeric_cols = [
        col["name"]
        for col in schema_json
        if col["type"] in ("double", "float", "int", "bigint", "decimal", "integer")
    ]

    anomalies: list[dict] = []

    for col_name in numeric_cols:
        try:
            stats_sql = f"""
                SELECT
                    COUNT(*) as cnt,
                    AVG({col_name}) as mean_val,
                    STDDEV({col_name}) as std_val,
                    PERCENTILE_APPROX({col_name}, 0.25) as q1,
                    PERCENTILE_APPROX({col_name}, 0.75) as q3
                FROM {table_name}
            """
            stats = execute_sql(stats_sql)
            if not stats["rows"] or not stats["rows"][0]:
                continue

            row = stats["rows"][0]
            cnt = row[0] or 0
            mean_val = row[1]
            std_val = row[2]
            q1 = row[3]
            q3 = row[4]

            if cnt < 10 or std_val is None or std_val == 0:
                continue

            iqr = q3 - q1 if q1 is not None and q3 is not None else None
            lower_3s = mean_val - 3 * std_val
            upper_3s = mean_val + 3 * std_val

            # 3-sigma detection
            outliers_sql = f"""
                SELECT {col_name} FROM {table_name}
                WHERE {col_name} < {lower_3s} OR {col_name} > {upper_3s}
                LIMIT 20
            """
            result = execute_sql(outliers_sql)
            for r in result["rows"]:
                val = r[0]
                severity = "high" if abs(val - mean_val) > 4 * std_val else "medium"
                anomalies.append({
                    "column_name": col_name,
                    "anomaly_type": "statistical",
                    "severity": severity,
                    "detected_value": str(val),
                    "expected_range": f"{lower_3s:.2f} – {upper_3s:.2f}",
                })

            # IQR detection
            if iqr and iqr > 0:
                lower_iqr = q1 - 1.5 * iqr
                upper_iqr = q3 + 1.5 * iqr
                iqr_sql = f"""
                    SELECT {col_name} FROM {table_name}
                    WHERE {col_name} < {lower_iqr} OR {col_name} > {upper_iqr}
                    LIMIT 20
                """
                result = execute_sql(iqr_sql)
                for r in result["rows"]:
                    val = r[0]
                    if val < lower_3s or val > upper_3s:
                        continue  # already caught by 3-sigma
                    anomalies.append({
                        "column_name": col_name,
                        "anomaly_type": "iqr",
                        "severity": "low",
                        "detected_value": str(val),
                        "expected_range": f"{lower_iqr:.2f} – {upper_iqr:.2f}",
                    })

        except Exception as e:
            logger.warning(f"Could not analyze column {col_name}: {e}")
            continue

    return anomalies


def run_isolation_forest(table_name: str, numeric_cols: list[str]) -> list[dict]:
    """Run Spark MLlib Isolation Forest on numeric columns. Returns anomalies."""
    if len(numeric_cols) < 2:
        return []

    spark = get_spark()
    df = spark.sql(f"SELECT {', '.join(numeric_cols)} FROM {table_name}")

    from pyspark.ml.feature import VectorAssembler  # noqa: E402
    from pyspark.ml.ensemble import IsolationForest  # noqa: E402

    assembler = VectorAssembler(inputCols=numeric_cols, outputCol="features")
    df_vec = assembler.transform(df)

    iso = IsolationForest(contamination=0.05, seed=42)
    model = iso.fit(df_vec)
    predictions = model.transform(df_vec)

    anomalies: list[dict] = []
    outlier_rows = predictions.filter("prediction = 1").limit(20).collect()
    for row in outlier_rows:
        for col_name in numeric_cols:
            val = row[col_name]
            if val is not None:
                anomalies.append({
                    "column_name": col_name,
                    "anomaly_type": "isolation_forest",
                    "severity": "medium",
                    "detected_value": str(val),
                    "expected_range": None,
                })

    return anomalies
