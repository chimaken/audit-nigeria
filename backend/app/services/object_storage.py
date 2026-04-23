"""Proof image storage: local filesystem (default) or private S3 when AWS_S3_BUCKET is set."""

from __future__ import annotations

import asyncio
import re
from functools import lru_cache
from pathlib import Path
_UNSAFE_KEY = re.compile(r"\.\.|^/|\\")

# Lazy imports avoid boto3 at module import when running tests without AWS.


def _unsafe_key(relative_key: str) -> bool:
    k = relative_key.replace("\\", "/").strip()
    if not k or k.startswith("/"):
        return True
    return bool(_UNSAFE_KEY.search(k))


@lru_cache(maxsize=1)
def _s3_client():
    import boto3

    from app.core.config import settings

    return boto3.client("s3", region_name=settings.AWS_REGION)


def put_bytes_local(base: Path, relative_key: str, data: bytes) -> None:
    if _unsafe_key(relative_key):
        raise ValueError(f"Invalid storage key: {relative_key!r}")
    dest = base / relative_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def put_bytes_s3(bucket: str, relative_key: str, data: bytes, content_type: str | None) -> None:
    if _unsafe_key(relative_key):
        raise ValueError(f"Invalid storage key: {relative_key!r}")
    extra: dict = {}
    if content_type:
        extra["ContentType"] = content_type
    _s3_client().put_object(Bucket=bucket, Key=relative_key, Body=data, **extra)


def get_bytes_local(base: Path, relative_key: str) -> bytes | None:
    if _unsafe_key(relative_key):
        return None
    path = base / relative_key
    if not path.is_file():
        return None
    return path.read_bytes()


def get_bytes_s3(bucket: str, relative_key: str) -> bytes | None:
    from botocore.exceptions import ClientError

    if _unsafe_key(relative_key):
        return None
    try:
        obj = _s3_client().get_object(Bucket=bucket, Key=relative_key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    return obj["Body"].read()


def exists_local(base: Path, relative_key: str) -> bool:
    if _unsafe_key(relative_key):
        return False
    return (base / relative_key).is_file()


def exists_s3(bucket: str, relative_key: str) -> bool:
    from botocore.exceptions import ClientError

    if _unsafe_key(relative_key):
        return False
    try:
        _s3_client().head_object(Bucket=bucket, Key=relative_key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NotFound", "NoSuchKey"):
            return False
        raise


async def aput_bytes(
    *,
    use_s3: bool,
    local_base: Path,
    bucket: str,
    relative_key: str,
    data: bytes,
    content_type: str | None = None,
) -> None:
    if use_s3:
        await asyncio.to_thread(put_bytes_s3, bucket, relative_key, data, content_type)
    else:
        await asyncio.to_thread(put_bytes_local, local_base, relative_key, data)


async def aget_bytes(
    *,
    use_s3: bool,
    local_base: Path,
    bucket: str,
    relative_key: str,
) -> bytes | None:
    if use_s3:
        return await asyncio.to_thread(get_bytes_s3, bucket, relative_key)
    return await asyncio.to_thread(get_bytes_local, local_base, relative_key)


async def aexists(
    *,
    use_s3: bool,
    local_base: Path,
    bucket: str,
    relative_key: str,
) -> bool:
    if use_s3:
        return await asyncio.to_thread(exists_s3, bucket, relative_key)
    return await asyncio.to_thread(exists_local, local_base, relative_key)
