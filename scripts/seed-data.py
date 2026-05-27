"""Generate sample CSV data for demo purposes."""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "sample-data"
OUTPUT_DIR.mkdir(exist_ok=True)


def generate_sales_data(filename: str = "sales_data.csv", rows: int = 1000):
    categories = ["Electronics", "Clothing", "Food", "Books", "Sports"]
    regions = ["North", "South", "East", "West"]

    with open(OUTPUT_DIR / filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "category", "region", "amount", "quantity", "customer_rating"])
        base_date = datetime(2024, 1, 1)
        for i in range(rows):
            writer.writerow([
                (base_date + timedelta(days=random.randint(0, 364))).strftime("%Y-%m-%d"),
                random.choice(categories),
                random.choice(regions),
                round(random.uniform(10, 5000), 2),
                random.randint(1, 50),
                round(random.uniform(1, 5), 1),
            ])

    print(f"Generated {rows} rows -> {OUTPUT_DIR / filename}")


if __name__ == "__main__":
    generate_sales_data()
