from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    postgres_user: str = "abd"
    postgres_password: str = "changeme"
    postgres_db: str = "abd_platform"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # MinIO
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_endpoint: str = "localhost:9000"
    minio_bucket: str = "datalake"

    # Spark
    spark_master_url: str = "spark://localhost:7077"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-to-a-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # LLM (placeholder for Phase 2)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"

    model_config = {"env_file": ".env"}


settings = Settings()
