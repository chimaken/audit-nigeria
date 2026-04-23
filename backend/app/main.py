import logging
import mimetypes
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
from app.core.config import settings
from app.services import object_storage
from app.db.models import Base
from app.db.session import engine

logger = logging.getLogger("audit_nigeria")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="AuditNigeria API", lifespan=lifespan)

_cors_origins = [
    o.strip()
    for o in settings.CORS_ALLOW_ORIGINS.split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Any localhost / loopback port (covers :3000, :3001, IPv6 ::1, etc.).
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    logger.exception("%s %s", request.method, request.url)
    payload: dict = {"detail": "Internal Server Error"}
    if settings.APP_EXPOSE_ERRORS:
        payload["error"] = str(exc)
        payload["type"] = type(exc).__name__
    return JSONResponse(status_code=500, content=payload)


app.include_router(uploads_router)
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
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
