# Test Data Seeding (4000+ Rows) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a 4000+ row e-commerce sales dataset, upload it to MinIO, register it as an Iceberg table via Spark, and make it queryable through the application frontend.

**Architecture:** A Python seeding script generates a CSV with 4320 rows of e-commerce order data (3 years of daily sales, Jan 2023–Dec 2025), uploads it to MinIO via boto3, creates a Spark Iceberg table from it, then registers the datasource + dataset in PostgreSQL so the frontend QueryPage can run SQL against it.

**Tech Stack:** Python 3.12, boto3 (MinIO/S3), PySpark (Iceberg), asyncpg (PostgreSQL metadata)

---

### Task 1: Create the data seeding script

**Files:**
- Create: `scripts/seed_data.py`

- [ ] **Step 1: Create the seed_data.py script**

```python
"""Generate 4320-row e-commerce sales dataset and seed into the platform.

Run inside the FastAPI container:
    docker exec abd-platform-fastapi-1 python /app/seed_data.py
"""

import csv
import io
import os
import random
import uuid
from datetime import date, timedelta

import boto3
from botocore.client import Config

# --- Config (from .env / container environment) ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "datalake")
TABLE_NAME = "ecommerce_orders"
CSV_FILENAME = "ecommerce_orders_4320.csv"

# --- Data generation parameters ---
random.seed(42)

CATEGORIES = ["电子产品", "服装鞋帽", "食品饮料", "家居用品", "美妆个护", "运动户外", "图书音像"]
PRODUCTS = {
    "电子产品": [
        ("iPhone 15 Pro", "Apple"), ("Mate 60 Pro", "Huawei"), ("ThinkPad X1", "Lenovo"),
        ("AirPods Pro", "Apple"), ("iPad Air", "Apple"), ("Galaxy S24", "Samsung"),
        ("小米14 Pro", "Xiaomi"), ("Watch GT4", "Huawei"), ("ROG 游戏本", "ASUS"),
        ("Surface Pro 10", "Microsoft"),
    ],
    "服装鞋帽": [
        ("羽绒服", "波司登"), ("运动跑鞋", "Nike"), ("休闲T恤", "优衣库"),
        ("牛仔裤", "Levi's"), ("冲锋衣", "Arc'teryx"), ("连衣裙", "ZARA"),
        ("商务衬衫", "海澜之家"), ("卫衣", "Adidas"), ("高跟鞋", "Staccato"),
        ("棒球帽", "New Era"),
    ],
    "食品饮料": [
        ("有机牛奶", "蒙牛"), ("坚果礼盒", "三只松鼠"), ("矿泉水24瓶装", "农夫山泉"),
        ("速溶咖啡", "雀巢"), ("方便面5连包", "康师傅"), ("酸奶", "伊利"),
        ("巧克力", "德芙"), ("薯片", "乐事"), ("茶叶礼盒", "八马"),
        ("枸杞原浆", "同仁堂"),
    ],
    "家居用品": [
        ("乳胶枕", "睡眠博士"), ("智能门锁", "小米"), ("四件套", "水星家纺"),
        ("空气炸锅", "飞利浦"), ("吸尘器", "Dyson"), ("台灯", "小米"),
        ("收纳箱", "IKEA"), ("净水器", "美的"), ("电饭煲", "苏泊尔"),
        ("扫地机器人", "石头"),
    ],
    "美妆个护": [
        ("精华液", "兰蔻"), ("面膜套装", "SK-II"), ("口红", "MAC"),
        ("防晒霜", "安耐晒"), ("洗发水", "清扬"), ("香水", "Dior"),
        ("眼霜", "雅诗兰黛"), ("洗面奶", "芙丽芳丝"), ("粉底液", "阿玛尼"),
        ("身体乳", "凡士林"),
    ],
    "运动户外": [
        ("瑜伽垫", "Lululemon"), ("登山包", "Osprey"), ("跑步机", "华为智选"),
        ("篮球", "Spalding"), ("帐篷", "牧高笛"), ("公路自行车", "捷安特"),
        ("羽毛球拍", "尤尼克斯"), ("游泳镜", "Speedo"), ("钓竿套装", "光威"),
        ("筋膜枪", "菠萝君"),
    ],
    "图书音像": [
        ("Python编程从入门到实践", "人民邮电出版社"), ("百年孤独", "新经典"),
        ("三体全集", "重庆出版社"), ("小王子", "译林出版社"),
        ("活着", "作家出版社"), ("人类简史", "中信出版社"),
        ("哈利波特全集", "人民文学出版社"), ("原则", "中信出版社"),
        ("鬼灭之刃漫画", "集英社"), ("周杰伦CD套装", "杰威尔"),
    ],
}
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆",
          "苏州", "长沙", "天津", "郑州", "东莞", "青岛", "厦门", "合肥", "福州", "昆明"]
PROVINCES = ["北京", "上海", "广东", "广东", "浙江", "四川", "湖北", "江苏", "陕西", "重庆",
             "江苏", "湖南", "天津", "河南", "广东", "山东", "福建", "安徽", "福建", "云南"]
PAYMENTS = ["微信支付", "支付宝", "银行卡", "货到付款"]
PAYMENT_WEIGHTS = [0.45, 0.35, 0.15, 0.05]
CHANNELS = ["APP", "PC网页", "小程序", "线下门店"]
CHANNEL_WEIGHTS = [0.40, 0.25, 0.20, 0.15]
STATUSES = ["已完成", "待发货", "已发货", "已退货", "已取消"]
STATUS_WEIGHTS = [0.65, 0.05, 0.15, 0.08, 0.07]

LAST_NAMES = ["张", "王", "李", "赵", "陈", "杨", "黄", "周", "吴", "徐", "孙", "马",
              "朱", "胡", "郭", "何", "林", "罗", "高", "梁", "刘", "郑", "谢", "宋"]
FIRST_NAMES = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "洋", "勇", "艳", "杰",
               "涛", "明", "超", "秀英", "华", "慧", "鑫", "军", "林", "桂英", "建华", "文"]


def customer_name():
    return random.choice(LAST_NAMES) + random.choice(FIRST_NAMES)


def generate_rows(start_date: date, end_date: date):
    """Generate one row per day per category, yielding 4320 rows (3 years = ~1096 days * ~4/day)."""
    rows = []
    current = start_date
    while current <= end_date:
        # 3-5 orders per day
        n_orders = random.choices([3, 4, 5], weights=[0.3, 0.4, 0.3])[0]
        for _ in range(n_orders):
            cat = random.choice(CATEGORIES)
            prod, brand = random.choice(PRODUCTS[cat])
            qty = random.randint(1, 5)
            price = round(random.uniform(9.9, 8999.0), 2)
            total = round(qty * price, 2)
            city_idx = random.randint(0, len(CITIES) - 1)
            rows.append({
                "order_id": str(uuid.uuid4())[:8].upper(),
                "order_date": current.isoformat(),
                "customer_name": customer_name(),
                "customer_city": CITIES[city_idx],
                "customer_province": PROVINCES[city_idx],
                "product_category": cat,
                "product_name": prod,
                "brand": brand,
                "quantity": qty,
                "unit_price": price,
                "total_amount": total,
                "payment_method": random.choices(PAYMENTS, weights=PAYMENT_WEIGHTS)[0],
                "channel": random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0],
                "status": random.choices(STATUSES, weights=STATUS_WEIGHTS)[0],
            })
        current += timedelta(days=1)
    return rows


def main():
    print("Generating e-commerce sales data (Jan 2023 – Dec 2025)...")
    rows = generate_rows(date(2023, 1, 1), date(2025, 12, 31))
    print(f"Generated {len(rows)} rows.")

    # Write CSV to in-memory buffer
    buf = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)

    # Upload to MinIO
    print(f"Uploading {CSV_FILENAME} to MinIO bucket '{MINIO_BUCKET}'...")
    s3 = boto3.client(
        "s3",
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS,
        aws_secret_access_key=MINIO_SECRET,
        config=Config(signature_version="s3v4"),
    )

    # Create bucket if not exists
    try:
        s3.head_bucket(Bucket=MINIO_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=MINIO_BUCKET)
        print(f"Created bucket '{MINIO_BUCKET}'.")

    s3.put_object(
        Bucket=MINIO_BUCKET,
        Key=f"raw/{CSV_FILENAME}",
        Body=buf.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )
    print("Upload complete.")

    # Create Iceberg table via Spark
    print("Creating Iceberg table via Spark...")
    from pyspark.sql import SparkSession
    from pyspark.sql.types import (
        StructType, StructField, StringType, DateType, IntegerType, DoubleType,
    )

    spark = (
        SparkSession.builder
        .appName("ABD-Seed")
        .master(os.getenv("SPARK_MASTER_URL", "local[*]"))
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.iceberg.type", "hadoop")
        .config("spark.sql.catalog.iceberg.warehouse", f"s3a://{MINIO_BUCKET}/")
        .config("spark.hadoop.fs.s3a.endpoint", f"http://{MINIO_ENDPOINT}")
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )

    schema = StructType([
        StructField("order_id", StringType()),
        StructField("order_date", DateType()),
        StructField("customer_name", StringType()),
        StructField("customer_city", StringType()),
        StructField("customer_province", StringType()),
        StructField("product_category", StringType()),
        StructField("product_name", StringType()),
        StructField("brand", StringType()),
        StructField("quantity", IntegerType()),
        StructField("unit_price", DoubleType()),
        StructField("total_amount", DoubleType()),
        StructField("payment_method", StringType()),
        StructField("channel", StringType()),
        StructField("status", StringType()),
    ])

    # Read CSV from MinIO via s3a
    csv_path = f"s3a://{MINIO_BUCKET}/raw/{CSV_FILENAME}"
    df = spark.read.option("header", "true").schema(schema).csv(csv_path)

    # Create Iceberg namespace and table
    spark.sql("CREATE NAMESPACE IF NOT EXISTS iceberg.abd")
    df.writeTo(f"iceberg.abd.{TABLE_NAME}").createOrReplace()

    row_count = spark.sql(f"SELECT count(*) FROM iceberg.abd.{TABLE_NAME}").collect()[0][0]
    print(f"Iceberg table 'iceberg.abd.{TABLE_NAME}' created with {row_count} rows.")

    # Print sample
    print("Sample rows:")
    spark.sql(f"SELECT * FROM iceberg.abd.{TABLE_NAME} LIMIT 5").show(truncate=False)

    spark.stop()
    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script file exists**

Run: `ls -la D:/Projects/ABD/abd-platform/scripts/seed_data.py`
Expected: file exists with content

- [ ] **Step 3: Copy script into the running FastAPI container and execute**

Run:
```bash
docker cp D:/Projects/ABD/abd-platform/scripts/seed_data.py abd-platform-fastapi-1:/app/seed_data.py
docker exec abd-platform-fastapi-1 python /app/seed_data.py
```
Expected: Script generates 4320 rows, uploads CSV to MinIO, creates Iceberg table, prints sample rows.

- [ ] **Step 4: Copy the script into the running FastAPI container (Windows path)**

Run:
```bash
docker cp D:\\Projects\\ABD\\abd-platform\\scripts\\seed_data.py abd-platform-fastapi-1:/app/seed_data.py
```

- [ ] **Step 5: Execute the seed script**

Run:
```bash
docker exec abd-platform-fastapi-1 python /app/seed_data.py
```
Expected: "Generated 4320 rows." → "Upload complete." → "Iceberg table created with 4320 rows." → sample rows printed.

---

### Task 2: Register dataset metadata in PostgreSQL

**Files:**
- Create: `scripts/register_dataset.py`

- [ ] **Step 1: Create register_dataset.py**

```python
"""Register the seeded dataset in the application database metadata."""
import asyncio
import os
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://abd:changeme@localhost:5433/abd_platform",
)

COLUMNS_SCHEMA = [
    {"name": "order_id", "type": "string"},
    {"name": "order_date", "type": "date"},
    {"name": "customer_name", "type": "string"},
    {"name": "customer_city", "type": "string"},
    {"name": "customer_province", "type": "string"},
    {"name": "product_category", "type": "string"},
    {"name": "product_name", "type": "string"},
    {"name": "brand", "type": "string"},
    {"name": "quantity", "type": "integer"},
    {"name": "unit_price", "type": "double"},
    {"name": "total_amount", "type": "double"},
    {"name": "payment_method", "type": "string"},
    {"name": "channel", "type": "string"},
    {"name": "status", "type": "string"},
]


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Find the admin user
        result = await session.execute(select(text("id FROM users WHERE username = 'admin'")))
        row = result.fetchone()
        if not row:
            print("ERROR: admin user not found. Register a user first.")
            return
        user_id = row[0]

        # Create datasource record
        ds_id = uuid.uuid4()
        await session.execute(
            text(
                "INSERT INTO datasources (id, name, type, config_json, created_by) "
                "VALUES (:id, :name, :type, :config, :created_by)"
            ),
            {
                "id": ds_id,
                "name": "E-Commerce Orders (Seed)",
                "type": "csv",
                "config": '{"filename": "ecommerce_orders_4320.csv", "rows": 4320}',
                "created_by": user_id,
            },
        )

        # Create dataset record
        dataset_id = uuid.uuid4()
        await session.execute(
            text(
                "INSERT INTO datasets (id, name, table_name, iceberg_path, schema_json, row_count, source_id, created_by) "
                "VALUES (:id, :name, :table_name, :iceberg_path, :schema, :row_count, :source_id, :created_by)"
            ),
            {
                "id": dataset_id,
                "name": "E-Commerce Orders (2023-2025)",
                "table_name": "ecommerce_orders",
                "iceberg_path": "s3a://datalake/ecommerce_orders",
                "schema": COLUMNS_SCHEMA,
                "row_count": 4320,
                "source_id": ds_id,
                "created_by": user_id,
            },
        )

        await session.commit()
        print(f"Registered datasource {ds_id}")
        print(f"Registered dataset {dataset_id}")
        print("Metadata registration complete.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Copy and run the registration script**

Run:
```bash
docker cp D:\\Projects\\ABD\\abd-platform\\scripts\\register_dataset.py abd-platform-fastapi-1:/app/register_dataset.py
docker exec abd-platform-fastapi-1 python /app/register_dataset.py
```
Expected: "Registered datasource ..." "Registered dataset ..." "Metadata registration complete."

---

### Task 3: Verify end-to-end through the API

- [ ] **Step 1: Login and get a JWT token**

Run:
```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}"
```
Expected: `{"access_token":"eyJ..."}` with a valid JWT.

- [ ] **Step 2: List datasets via API**

Run:
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && curl -s http://127.0.0.1:8000/api/v1/datasets/ -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
Expected: List with 1 dataset, `"name":"E-Commerce Orders (2023-2025)"`, `"row_count":4320`.

- [ ] **Step 3: Run a sample SQL query via the API**

Run:
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && curl -s -X POST http://127.0.0.1:8000/api/v1/query/ -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"sql\":\"SELECT status, COUNT(*) as cnt, ROUND(SUM(total_amount), 2) as revenue FROM iceberg.abd.ecommerce_orders GROUP BY status ORDER BY cnt DESC\"}"
```
Expected: JSON with columns, rows showing order status breakdown with counts and revenue.

- [ ] **Step 4: Run a category analysis query**

Run:
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && curl -s -X POST http://127.0.0.1:8000/api/v1/query/ -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"sql\":\"SELECT product_category, COUNT(*) as order_count, ROUND(SUM(total_amount), 2) as revenue FROM iceberg.abd.ecommerce_orders GROUP BY product_category ORDER BY revenue DESC\"}"
```
Expected: 7 categories with order counts and revenue, 电子产品 likely highest.

- [ ] **Step 5: Run a regional analysis query**

Run:
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && curl -s -X POST http://127.0.0.1:8000/api/v1/query/ -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"sql\":\"SELECT customer_province, COUNT(*) as orders, ROUND(SUM(total_amount), 2) as revenue FROM iceberg.abd.ecommerce_orders GROUP BY customer_province ORDER BY revenue DESC LIMIT 10\"}"
```
Expected: Top 10 provinces by revenue.

- [ ] **Step 6: Run a monthly trend query**

Run:
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && curl -s -X POST http://127.0.0.1:8000/api/v1/query/ -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"sql\":\"SELECT DATE_TRUNC('month', order_date) as month, COUNT(*) as orders, ROUND(SUM(total_amount), 2) as revenue FROM iceberg.abd.ecommerce_orders GROUP BY DATE_TRUNC('month', order_date) ORDER BY month\"}"
```
Expected: Monthly aggregates for 36 months (Jan 2023–Dec 2025).

- [ ] **Step 7: Open the frontend and verify**

Instructions:
1. Open http://localhost:5173 in a browser
2. Login with admin / admin123
3. Navigate to "Datasets" — should show "E-Commerce Orders (2023-2025)" with 4,320 rows
4. Navigate to "Query" — paste and run:
   ```sql
   SELECT product_category, COUNT(*) as orders, ROUND(SUM(total_amount), 2) as revenue
   FROM iceberg.abd.ecommerce_orders
   GROUP BY product_category
   ORDER BY revenue DESC
   ```
5. Switch to "Chart" view to see a bar chart of categories vs revenue
6. Try a time-series query:
   ```sql
   SELECT DATE_TRUNC('month', order_date) as month, ROUND(SUM(total_amount), 2) as revenue
   FROM iceberg.abd.ecommerce_orders
   GROUP BY DATE_TRUNC('month', order_date)
   ORDER BY month
   ```
7. Switch to "Chart" view to see the revenue trend over 36 months

