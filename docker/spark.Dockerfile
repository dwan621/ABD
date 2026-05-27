FROM eclipse-temurin:17-jre

USER root

# Install Python 3 and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    procps \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Install Apache Spark
ENV SPARK_VERSION=3.5.0
ENV HADOOP_VERSION=3
ENV SPARK_HOME=/opt/spark

RUN curl -fsSL "https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz" \
    -o /tmp/spark.tgz \
    && mkdir -p /opt \
    && tar xzf /tmp/spark.tgz -C /opt \
    && mv "/opt/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}" "${SPARK_HOME}" \
    && rm /tmp/spark.tgz

# Install Python libs for Iceberg/S3
RUN pip3 install --no-cache-dir --break-system-packages \
    pyiceberg==0.6.1 \
    boto3==1.35.0 \
    pyarrow==17.0.0

ENV PYSPARK_PYTHON=/usr/bin/python3
ENV PYSPARK_DRIVER_PYTHON=/usr/bin/python3
ENV PATH="${SPARK_HOME}/bin:${PATH}"

# Create non-root user
RUN useradd --create-home --shell /bin/bash spark && chown -R spark:spark /opt/spark
USER spark
