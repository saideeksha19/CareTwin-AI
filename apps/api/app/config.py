from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _algorithms(value: str | None) -> tuple[str, ...]:
    allowed = {"RS256", "RS384", "RS512", "ES256"}
    raw = (value or "RS256,RS384,RS512,ES256").split(",")
    chosen = tuple(item.strip().upper() for item in raw if item.strip().upper() in allowed)
    return chosen or ("RS256",)


def _origins(value: str | None) -> tuple[str, ...]:
    raw = value or "http://localhost:3000,http://127.0.0.1:3000"
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def load_local_env() -> None:
    """Load optional local .env files without adding a dependency.

    Real process environment variables always win. .env files are never read by
    the frontend, are excluded from git, and are never logged.
    """
    for candidate in (PROJECT_ROOT / ".env", PROJECT_ROOT / "apps" / "api" / ".env"):
        if not candidate.is_file():
            continue
        try:
            for raw_line in candidate.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            continue


@dataclass(frozen=True)
class Settings:
    app_name: str = "CareTwin AI API"
    version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    db_path: Path = PROJECT_ROOT / "data" / "demo" / "caretwin.db"
    document_storage_path: Path = PROJECT_ROOT / "data" / "documents"
    cors_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    demo_mode: bool = True
    seed_demo: bool = True
    log_level: str = "INFO"
    # Authentication mode: "demo" keeps the synthetic header identity; "production"
    # requires a verified OpenID Connect bearer token and never accepts the demo header.
    auth_mode: str = "demo"
    auth_issuer: str = ""
    auth_audience: str = ""
    auth_jwks_url: str = ""
    auth_algorithms: tuple[str, ...] = ("RS256", "RS384", "RS512", "ES256")
    auth_leeway_seconds: int = 60
    auth_jwks_cache_seconds: int = 900
    auth_require_identity_link: bool = True
    auth_client_id: str = ""
    auth_client_secret: str = ""
    auth_redirect_uri: str = ""
    auth_post_login_redirect: str = "/workspace"
    auth_session_ttl_seconds: int = 28800
    auth_session_idle_seconds: int = 3600
    auth_cookie_secure: bool = False
    auth_required_amr: tuple[str, ...] = ()
    ai_provider: str = "gemini"
    ai_model: str = "gemini-3.8-flash"
    ai_api_base: str = "https://generativelanguage.googleapis.com/v1beta"
    ai_api_key: str | None = None
    ai_timeout_seconds: float = 40.0
    ai_max_input_chars: int = 24000
    ai_max_output_tokens: int = 3072
    ai_requests_per_hour: int = 40
    ai_retry_attempts: int = 2
    upload_requests_per_hour: int = 200
    assistant_requests_per_hour: int = 120
    max_upload_bytes: int = 15 * 1024 * 1024
    max_pdf_pages: int = 50
    allowed_document_mime_types: tuple[str, ...] = (
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/webp",
    )
    # Database: SQLite remains the supported local/demo engine. A PostgreSQL URL
    # can be configured for production planning, but live Postgres execution is
    # only supported when the runtime and repository layer are validated for it.
    database_backend: str = "sqlite"
    database_url: str = ""
    db_pool_size: int = 5
    # Storage/encryption/backup: local private storage is the implemented backend.
    # Object-storage and shared-store backends are adapter-ready/configurable but
    # not claimed live without real-service verification.
    storage_backend: str = "local"
    storage_bucket: str = ""
    storage_prefix: str = ""
    document_encryption_key: str | None = None
    require_document_encryption: bool = False
    backup_root_path: Path = PROJECT_ROOT / "data" / "backups"
    backup_encryption_key: str | None = None
    backup_retention_count: int = 14
    rate_limit_backend: str = "memory"
    rate_limit_store_url: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        load_local_env()
        auth_mode = (os.getenv("CARETWIN_AUTH_MODE", "demo").strip().lower() or "demo")
        if auth_mode not in {"demo", "production"}:
            raise ValueError(
                "CARETWIN_AUTH_MODE must be 'demo' or 'production'; refusing to start "
                "with an ambiguous identity mode."
            )
        return cls(
            environment=os.getenv("CARETWIN_ENV", "development"),
            auth_mode=auth_mode,
            auth_issuer=os.getenv("CARETWIN_AUTH_ISSUER", "").strip(),
            auth_audience=os.getenv("CARETWIN_AUTH_AUDIENCE", "").strip(),
            auth_jwks_url=os.getenv("CARETWIN_AUTH_JWKS_URL", "").strip(),
            auth_algorithms=_algorithms(os.getenv("CARETWIN_AUTH_ALGORITHMS")),
            auth_leeway_seconds=int(os.getenv("CARETWIN_AUTH_LEEWAY_SECONDS", "60")),
            auth_jwks_cache_seconds=int(os.getenv("CARETWIN_AUTH_JWKS_CACHE_SECONDS", "900")),
            auth_require_identity_link=_bool(
                os.getenv("CARETWIN_AUTH_REQUIRE_IDENTITY_LINK"), True
            ),
            auth_client_id=os.getenv("CARETWIN_AUTH_CLIENT_ID", "").strip(),
            auth_client_secret=os.getenv("CARETWIN_AUTH_CLIENT_SECRET", "").strip(),
            auth_redirect_uri=os.getenv("CARETWIN_AUTH_REDIRECT_URI", "").strip(),
            auth_post_login_redirect=(
                os.getenv("CARETWIN_AUTH_POST_LOGIN_REDIRECT", "/workspace").strip()
                or "/workspace"
            ),
            auth_session_ttl_seconds=int(
                os.getenv("CARETWIN_AUTH_SESSION_TTL_SECONDS", "28800")
            ),
            auth_session_idle_seconds=int(
                os.getenv("CARETWIN_AUTH_SESSION_IDLE_SECONDS", "3600")
            ),
            auth_cookie_secure=_bool(
                os.getenv("CARETWIN_AUTH_COOKIE_SECURE"), auth_mode == "production"
            ),
            auth_required_amr=tuple(
                item.strip()
                for item in os.getenv("CARETWIN_AUTH_REQUIRED_AMR", "").split(",")
                if item.strip()
            ),
            db_path=Path(
                os.getenv(
                    "CARETWIN_DB_PATH",
                    str(PROJECT_ROOT / "data" / "demo" / "caretwin.db"),
                )
            ),
            document_storage_path=Path(
                os.getenv(
                    "CARETWIN_DOCUMENT_STORAGE_PATH",
                    str(PROJECT_ROOT / "data" / "documents"),
                )
            ),
            cors_origins=_origins(os.getenv("CARETWIN_CORS_ORIGINS")),
            demo_mode=_bool(os.getenv("CARETWIN_DEMO_MODE"), True),
            seed_demo=_bool(os.getenv("CARETWIN_SEED_DEMO"), True),
            log_level=os.getenv("CARETWIN_LOG_LEVEL", "INFO").upper(),
            ai_provider=os.getenv("CARETWIN_AI_PROVIDER", "gemini"),
            ai_model=os.getenv("CARETWIN_AI_MODEL", "gemini-3.8-flash"),
            ai_api_base=os.getenv(
                "CARETWIN_AI_API_BASE", "https://generativelanguage.googleapis.com/v1beta"
            ).rstrip("/"),
            ai_api_key=os.getenv("GEMINI_API_KEY") or None,
            ai_timeout_seconds=float(os.getenv("CARETWIN_AI_TIMEOUT_SECONDS", "40")),
            ai_max_input_chars=int(os.getenv("CARETWIN_AI_MAX_INPUT_CHARS", "24000")),
            ai_max_output_tokens=int(os.getenv("CARETWIN_AI_MAX_OUTPUT_TOKENS", "3072")),
            ai_requests_per_hour=int(os.getenv("CARETWIN_AI_REQUESTS_PER_HOUR", "40")),
            ai_retry_attempts=int(os.getenv("CARETWIN_AI_RETRY_ATTEMPTS", "2")),
            upload_requests_per_hour=int(
                os.getenv("CARETWIN_UPLOAD_REQUESTS_PER_HOUR", "200")
            ),
            assistant_requests_per_hour=int(
                os.getenv("CARETWIN_ASSISTANT_REQUESTS_PER_HOUR", "120")
            ),
            max_upload_bytes=int(os.getenv("CARETWIN_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024))),
            max_pdf_pages=int(os.getenv("CARETWIN_MAX_PDF_PAGES", "50")),
            database_backend=(os.getenv("CARETWIN_DATABASE_BACKEND", "sqlite").strip().lower() or "sqlite"),
            database_url=os.getenv("CARETWIN_DATABASE_URL", "").strip(),
            db_pool_size=int(os.getenv("CARETWIN_DB_POOL_SIZE", "5")),
            storage_backend=(os.getenv("CARETWIN_STORAGE_BACKEND", "local").strip().lower() or "local"),
            storage_bucket=os.getenv("CARETWIN_STORAGE_BUCKET", "").strip(),
            storage_prefix=os.getenv("CARETWIN_STORAGE_PREFIX", "").strip(),
            document_encryption_key=os.getenv("CARETWIN_DOCUMENT_ENCRYPTION_KEY") or None,
            require_document_encryption=_bool(os.getenv("CARETWIN_REQUIRE_DOCUMENT_ENCRYPTION"), False),
            backup_root_path=Path(
                os.getenv("CARETWIN_BACKUP_ROOT_PATH", str(PROJECT_ROOT / "data" / "backups"))
            ),
            backup_encryption_key=os.getenv("CARETWIN_BACKUP_ENCRYPTION_KEY") or None,
            backup_retention_count=int(os.getenv("CARETWIN_BACKUP_RETENTION_COUNT", "14")),
            rate_limit_backend=(os.getenv("CARETWIN_RATE_LIMIT_BACKEND", "memory").strip().lower() or "memory"),
            rate_limit_store_url=os.getenv("CARETWIN_RATE_LIMIT_STORE_URL", "").strip(),
        )

    def ensure_paths(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.document_storage_path.mkdir(parents=True, exist_ok=True)
        self.backup_root_path.mkdir(parents=True, exist_ok=True)

    def production_config_issues(self) -> list[str]:
        """Return configuration issues that must fail closed in production.

        Only checks requirements that can be validated locally without claiming
        live external services. External services (Postgres, object storage,
        shared rate-limit stores, monitoring backends) are reported separately.
        """
        issues: list[str] = []
        if self.auth_mode == "production":
            if self.require_document_encryption and not self.document_encryption_key:
                issues.append(
                    "CARETWIN_REQUIRE_DOCUMENT_ENCRYPTION=true but CARETWIN_DOCUMENT_ENCRYPTION_KEY is not set."
                )
            # PostgreSQL, object storage and shared stores are strongly recommended
            # for production, but live verification depends on external services not
            # available in this repository. Reported via readiness/docs, not hard-failed
            # here to preserve existing validated auth behavior.
        return issues


ANON = "demo_anonymous"
