import os
import base64
import uuid
from typing import Tuple, Optional
import boto3

S3_BUCKET = os.getenv("S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION")
MOCK_STORAGE = os.getenv("MOCK_STORAGE", "0") == "1"


def _get_s3_client():
    # boto3 will pick up AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from env
    return boto3.client("s3", region_name=AWS_REGION)


def _parse_base64_data(data: str) -> bytes:
    """
    Accepts raw base64 or a data URL (e.g., 'data:application/pdf;base64,....').
    Returns decoded bytes.
    """
    if "," in data and data.lower().startswith("data:"):
        data = data.split(",", 1)[1]
    return base64.b64decode(data)


def upload_pdf_from_base64(
    *,
    checklist_id: str,
    filename: str,
    base64_data: str,
    content_type: Optional[str] = None,
) -> Tuple[str, int]:
    """
    Upload base64-encoded file content to S3.

    Returns: (storage_key, size_bytes)
    """
    data = _parse_base64_data(base64_data)
    size = len(data)
    key = f"checklists/{checklist_id}/documents/{uuid.uuid4().hex}/{filename}"

    if MOCK_STORAGE:
        # Return a mock storage key without writing to S3.
        return f"mock://{key}", size

    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET env is not set")

    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type

    s3 = _get_s3_client()
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=data, **extra_args)
    return key, size


def download_bytes(storage_key: str) -> bytes:
    """
    Download an object from S3 using the given storage key and return its bytes.
    """
    if storage_key.startswith("mock://"):
        raise RuntimeError("Cannot download mock:// storage keys. Upload with real S3 or disable MOCK_STORAGE.")
    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET env is not set")
    s3 = _get_s3_client()
    obj = s3.get_object(Bucket=S3_BUCKET, Key=storage_key)
    return obj["Body"].read()
