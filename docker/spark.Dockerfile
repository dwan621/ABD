FROM bitnami/spark:3.5

USER root
RUN pip install --no-cache-dir \
    pyiceberg==0.6.1 \
    boto3==1.35.0 \
    pyarrow==17.0.0

# Configure Iceberg catalog
ENV PYSPARK_PYTHON=/opt/bitnami/python/bin/python3
ENV PYSPARK_DRIVER_PYTHON=/opt/bitnami/python/bin/python3

USER 1001
