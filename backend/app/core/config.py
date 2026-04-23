from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .../backend/app/core/config.py — parents[2] is the install root (e.g. repo/backend or /app in Docker).
_cfg = Path(__file__).resolve()
_backend_root = _cfg.parents[2]
_candidate_repo = _cfg.parents[3]
# In Docker, parents[3] is "/" — use install root for .env instead of repo root.
_REPO_ROOT = (
    _candidate_repo
    if (_candidate_repo / "docker-compose.yml").is_file()
    else _backend_root
)
_REPO_ENV = _REPO_ROOT / ".env"
_BACKEND_ENV = _backend_root / ".env"
# Later files override earlier ones (pydantic-settings merge order).
_ENV_FILES = tuple(
    str(p) for p in (_REPO_ENV, _BACKEND_ENV) if p.is_file()
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES if _ENV_FILES else (".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = (
        "postgresql+asyncpg://user:password@localhost:5432/audit_nigeria"
    )

    # Public URL prefix for proof image links (no trailing slash).
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # OpenRouter (vision). Leave key empty to skip live calls in dev.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    # Slug must match https://openrouter.ai/models (vision). Claude 3.5 slug often has no providers (HTTP 404).
    OPENROUTER_MODEL: str = "anthropic/claude-sonnet-4.5"

    @field_validator("OPENROUTER_API_KEY", mode="before")
    @classmethod
    def _strip_openrouter_key(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()

    USE_AWS_BEDROCK: bool = False
    AWS_BEDROCK_MODEL_ID: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    AWS_REGION: str = "us-east-1"

    # When set, proof images are stored in this private S3 bucket (keys = DB `image_path`).
    # IAM: s3:PutObject, s3:GetObject, s3:HeadObject on the bucket (and KMS if bucket uses CMK).
    AWS_S3_BUCKET: str = ""

    # Optional. Same as `terraform output aws_account_id`. Useful for ARNs / docs; boto3 auth
    # uses instance/task role or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, not this field.
    AWS_ACCOUNT_ID: str = ""

    # When true, 500 responses include `error` and `type` (dev only; turn off in production).
    APP_EXPOSE_ERRORS: bool = True

    # Comma-separated browser origins allowed for CORS (e.g. http://localhost:3000).
    # Regex in main.py also allows any localhost / 127.0.0.1 / [::1] port in development.
    CORS_ALLOW_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def backend_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent

    @property
    def uploads_dir(self) -> Path:
        return self.backend_dir / "uploads"

    @property
    def use_s3_uploads(self) -> bool:
        return bool(self.AWS_S3_BUCKET and str(self.AWS_S3_BUCKET).strip())


settings = Settings()
