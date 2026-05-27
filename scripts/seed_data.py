"""Generate 4320-row e-commerce sales dataset and register as Spark SQL table.

Uses Spark's built-in Parquet catalog (no Iceberg needed).
Table persists under /app/data/spark-warehouse/ on the host volume.

Run inside the FastAPI container:
    docker exec abd-platform-fastapi-1 python /app/seed_data.py
"""

import os
import random
import uuid
from datetime import date, timedelta

random.seed(42)

TABLE_NAME = "ecommerce_orders"
WAREHOUSE_DIR = "/app/data/spark-warehouse"
CSV_FILE = "/app/data/ecommerce_orders_4320.csv"

# --- Data generation ---
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


def generate_rows(start_date: date, end_date: date) -> list[dict]:
    rows = []
    current = start_date
    while current <= end_date:
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

    # Write CSV locally (mounted volume, persists on host)
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    import csv
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote CSV to {CSV_FILE}")

    # Create Spark session and table (no Iceberg, no S3A needed)
    print("Creating Spark table...")
    from pyspark.sql import SparkSession
    from pyspark.sql.types import (
        StructType, StructField, StringType, DateType, IntegerType, DoubleType,
    )

    os.makedirs(WAREHOUSE_DIR, exist_ok=True)

    spark = (
        SparkSession.builder
        .appName("ABD-Seed")
        .master(os.getenv("SPARK_MASTER_URL", "local[*]"))
        .config("spark.sql.warehouse.dir", f"file://{WAREHOUSE_DIR}")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
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

    df = spark.read.option("header", "true").schema(schema).csv(f"file://{CSV_FILE}")
    df.write.mode("overwrite").saveAsTable(TABLE_NAME)

    row_count = spark.sql(f"SELECT count(*) FROM {TABLE_NAME}").collect()[0][0]
    print(f"Table '{TABLE_NAME}' created with {row_count} rows.")

    print("\nSample rows:")
    spark.sql(f"SELECT * FROM {TABLE_NAME} LIMIT 5").show(truncate=False)

    # Verify analytical queries work
    print("\n--- Category breakdown ---")
    spark.sql(f"""
        SELECT product_category, COUNT(*) as orders, ROUND(SUM(total_amount), 2) as revenue
        FROM {TABLE_NAME}
        GROUP BY product_category
        ORDER BY revenue DESC
    """).show(truncate=False)

    spark.stop()
    print("Done.")


if __name__ == "__main__":
    main()
