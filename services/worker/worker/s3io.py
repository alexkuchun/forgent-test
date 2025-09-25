from __future__ import annotations
import boto3
from botocore.config import Config
from typing import Optional
from .config import get_settings


def _client():
    s = get_settings()
    session = boto3.session.Session()
    kwargs = {
        "region_name": s.aws_region,
        "aws_access_key_id": s.aws_key,
        "aws_secret_access_key": s.aws_secret,
        "config": Config(s3={"addressing_style": "path" if s.s3_force_path_style else "virtual"}),
    }
    if s.s3_endpoint:
        kwargs["endpoint_url"] = s.s3_endpoint
    return session.client("s3", **kwargs)


def get_object_bytes(key: str) -> bytes:
    s = get_settings()
    c = _client()
    out = c.get_object(Bucket=s.s3_bucket, Key=key)
    data = out["Body"].read()
    return data


def put_object_bytes(key: str, data: bytes, content_type: Optional[str] = None):
    s = get_settings()
    c = _client()
    extra = {}
    if content_type:
        extra["ContentType"] = content_type
    c.put_object(Bucket=s.s3_bucket, Key=key, Body=data, **extra)
