import os
from dataclasses import dataclass


@dataclass
class Settings:
    redis_url: str
    s3_bucket: str
    aws_key: str | None
    aws_secret: str | None
    aws_region: str | None
    s3_endpoint: str | None
    s3_force_path_style: bool

    anthropic_api_key: str | None
    anthropic_model: str
    anthropic_repair_model: str

    api_base: str | None
    ingest_token: str | None

    chunk_window_pages: int
    chunk_overlap_pages: int
    similarity_threshold: float


def get_settings() -> Settings:
    return Settings(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        s3_bucket=os.getenv("S3_BUCKET", ""),
        aws_key=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret=os.getenv("AWS_SECRET_ACCESS_KEY"),
        aws_region=os.getenv("AWS_REGION"),
        s3_endpoint=os.getenv("S3_ENDPOINT"),
        s3_force_path_style=os.getenv("S3_FORCE_PATH_STYLE", "false").lower() in ("1", "true", "yes"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        anthropic_repair_model=os.getenv("ANTHROPIC_REPAIR_MODEL", "claude-3-haiku-20240307"),
        api_base=os.getenv("API_BASE"),
        ingest_token=os.getenv("WORKER_INGEST_TOKEN"),
        chunk_window_pages=int(os.getenv("CHUNK_WINDOW_PAGES", "5")),
        chunk_overlap_pages=int(os.getenv("CHUNK_OVERLAP_PAGES", "1")),
        similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.92")),
    )
