"""Register the seeded dataset in the application database metadata."""
import asyncio
import json
import os
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_PG_USER = os.getenv("POSTGRES_USER", "abd")
_PG_PASS = os.getenv("POSTGRES_PASSWORD", "changeme")
_PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
_PG_PORT = os.getenv("POSTGRES_PORT", "5432")
_PG_DB = os.getenv("POSTGRES_DB", "abd_platform")
DATABASE_URL = f"postgresql+asyncpg://{_PG_USER}:{_PG_PASS}@{_PG_HOST}:{_PG_PORT}/{_PG_DB}"

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
        result = await session.execute(text("SELECT id FROM users WHERE username = 'admin'"))
        row = result.fetchone()
        if not row:
            print("ERROR: admin user not found. Register a user first.")
            return
        user_id = row[0]

        # Check if already registered
        result = await session.execute(
            text("SELECT id FROM datasets WHERE table_name = 'ecommerce_orders'")
        )
        if result.fetchone():
            print("Dataset 'ecommerce_orders' already registered, skipping.")
            return

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
                "config": json.dumps({"filename": "ecommerce_orders_4320.csv", "rows": 4386}),
                "created_by": user_id,
            },
        )

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
                "iceberg_path": "file:///app/data/spark-warehouse/ecommerce_orders",
                "schema": json.dumps(COLUMNS_SCHEMA),
                "row_count": 4386,
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
