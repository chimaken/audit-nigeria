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
    from botocore.config import Config

    from app.core.config import settings

    # Keep API requests under App Runner's ~120s request ceiling.
    cfg = Config(
        connect_timeout=5,
        read_timeout=8,
        retries={"mode": "standard", "max_attempts": 2},
    )
    return boto3.client("s3", region_name=settings.AWS_REGION, config=cfg)


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


def delete_bytes_local(base: Path, relative_key: str) -> None:
    if _unsafe_key(relative_key):
        raise ValueError(f"Invalid storage key: {relative_key!r}")
    path = base / relative_key
    if path.is_file():
        path.unlink()


def delete_bytes_s3(bucket: str, relative_key: str) -> None:
    if _unsafe_key(relative_key):
        raise ValueError(f"Invalid storage key: {relative_key!r}")
    _s3_client().delete_object(Bucket=bucket, Key=relative_key)


async def adelete_bytes(
    *,
    use_s3: bool,
    local_base: Path,
    bucket: str,
    relative_key: str,
) -> None:
    if use_s3:
        await asyncio.to_thread(delete_bytes_s3, bucket, relative_key)
    else:
        await asyncio.to_thread(delete_bytes_local, local_base, relative_key)


def generate_presigned_put_url(
    bucket: str,
    relative_key: str,
    content_type: str | None,
    expires_in: int = 3600,
) -> str:
    """Browser PUT to this URL must send the same Content-Type when the URL was signed with one."""
    if _unsafe_key(relative_key):
        raise ValueError(f"Invalid storage key: {relative_key!r}")
    params: dict[str, str] = {"Bucket": bucket, "Key": relative_key}
    if content_type:
        params["ContentType"] = content_type
    return _s3_client().generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )
