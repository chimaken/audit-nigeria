import logging
import mimetypes
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.demo import router as demo_router
from app.api.results import router as results_router
from app.api.uploads import router as uploads_router
from app.api.uploads_async import router as uploads_async_router
from app.core.config import settings
from app.services import object_storage
from app.db.models import Base
from app.db.session import engine

logger = logging.getLogger("audit_nigeria")


def _normalize_browser_origin(value: str) -> str:
    """Origin header is scheme+host+port only; strip whitespace and stray trailing slashes from config."""
    o = value.strip()
    while o.endswith("/"):
        o = o[:-1]
    return o


_cors_origins = [
    _normalize_browser_origin(o)
    for o in settings.CORS_ALLOW_ORIGINS.split(",")
    if o.strip()
]

# Dev: any localhost port. Prod dashboards: default CloudFront distribution hostnames (scheme+host only).
_LOCAL_ORIGIN_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")
_CLOUDFRONT_DEFAULT_DIST_RE = re.compile(
    r"^https://[A-Za-z0-9]+\.cloudfront\.net$",
    re.IGNORECASE,
)

_CORS_ALLOW_ORIGIN_REGEX = (
    r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
    r"|^https://[A-Za-z0-9]+\.cloudfront\.net$"
)


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    o = _normalize_browser_origin(origin)
    if o in _cors_origins:
        return True
    if _LOCAL_ORIGIN_RE.match(o):
        return True
    if _CLOUDFRONT_DEFAULT_DIST_RE.match(o):
        return True
    return False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "CORS_ALLOW_ORIGINS effective allow-list (%d entries): %s",
        len(_cors_origins),
        ", ".join(_cors_origins) if _cors_origins else "(empty - localhost regex only)",
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="AuditNigeria API", lifespan=lifespan)


def _cors_headers_for_request(request: Request) -> dict[str, str]:
    """Mirror CORSMiddleware allow-list so error responses still carry CORS (some clients hide real errors)."""
    origin = request.headers.get("origin")
    if not origin or not _origin_allowed(origin):
        return {}
    return {
        "access-control-allow-origin": origin,
        "vary": "Origin",
    }


def _merge_cors(request: Request, response: Response) -> Response:
    for k, v in _cors_headers_for_request(request).items():
        if response.headers.get(k) is None:
            response.headers[k] = v
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> Response:
    if isinstance(exc, HTTPException):
        resp = await http_exception_handler(request, exc)
        return _merge_cors(request, resp)
    logger.exception("%s %s", request.method, request.url)
    payload: dict = {"detail": "Internal Server Error"}
    if settings.APP_EXPOSE_ERRORS:
        payload["error"] = str(exc)
        payload["type"] = type(exc).__name__
    return JSONResponse(
        status_code=500,
        content=payload,
        headers=_cors_headers_for_request(request),
    )


app.include_router(uploads_router)
app.include_router(uploads_async_router)
app.include_router(demo_router)
app.include_router(results_router)

if settings.use_s3_uploads:

    @app.get("/files/{full_path:path}")
    async def serve_proof_file(full_path: str) -> Response:
        data = await object_storage.aget_bytes(
            use_s3=True,
            local_base=settings.uploads_dir,
            bucket=settings.AWS_S3_BUCKET.strip(),
            relative_key=full_path,
        )
        if data is None:
            raise HTTPException(status_code=404, detail="File not found")
        media, _ = mimetypes.guess_type(full_path)
        return Response(content=data, media_type=media or "application/octet-stream")

else:
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/files",
        StaticFiles(directory=str(settings.uploads_dir)),
        name="files",
    )


@app.get("/health")
async def health() -> dict[str, str | bool]:
    """Non-sensitive flags for dashboards (e.g. whether upload can omit pu_id for vision-based header read)."""
    return {
        "status": "ok",
        "openrouter_configured": bool(settings.OPENROUTER_API_KEY),
        "reset_collated_votes_enabled": bool((settings.DASHBOARD_RESET_TOKEN or "").strip()),
        "async_upload_enabled": bool(
            settings.use_s3_uploads and (settings.UPLOAD_JOBS_QUEUE_URL or "").strip()
        ),
    }


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    """Verify Postgres accepts queries (useful after restarts / recovery)."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "database": str(e)},
        ) from e
    return {"status": "ok", "database": "connected"}
