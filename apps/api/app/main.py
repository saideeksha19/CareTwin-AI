from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.config import Settings
from app.db import connect, init_db
from app.errors import ApiError
from app.repositories.store import Store
from app.safety.rate_limit import SlidingWindowLimiter
from app.seed import seed_demo_data

LOGGER = logging.getLogger("caretwin.api")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_paths()
        init_db(settings.db_path)
        if settings.seed_demo:
            conn = connect(settings.db_path)
            try:
                store = Store(conn)
                seed_demo_data(store, include_clinical_records=settings.environment != "test")
                conn.commit()
            finally:
                conn.close()
        LOGGER.info(
            "CareTwin API started env=%s demo=%s db=%s ai=%s",
            settings.environment,
            settings.demo_mode,
            "sqlite",
            "configured" if settings.ai_api_key else "not_configured",
        )
        yield
        LOGGER.info("CareTwin API stopped")

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Evidence-linked recovery digital twin, deterministic safety controls, "
            "role-scoped workflows, and a provider-independent AI boundary. "
            "Synthetic demo data only."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.state.rate_limiter = SlidingWindowLimiter()

    # Authentication is configuration-driven and fails closed: production mode
    # refuses to start without an issuer, audience and key set, and it never falls
    # back to the synthetic demo header.
    app.state.identity_provider = None
    app.state.oidc_flow = None
    if settings.auth_mode == "production":
        if not (
            settings.auth_issuer and settings.auth_audience and settings.auth_jwks_url
        ):
            raise RuntimeError(
                "Production authentication requires CARETWIN_AUTH_ISSUER, "
                "CARETWIN_AUTH_AUDIENCE and CARETWIN_AUTH_JWKS_URL. Refusing to "
                "start with demo identity in production mode."
            )
        from app.auth import JwksCache, OidcIdentityProvider

        app.state.identity_provider = OidcIdentityProvider(
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
            algorithms=settings.auth_algorithms,
            leeway_seconds=settings.auth_leeway_seconds,
            jwks=JwksCache(
                settings.auth_jwks_url,
                ttl_seconds=settings.auth_jwks_cache_seconds,
            ),
        )
        # The login flow is optional: token-only API clients work with just the
        # verifier. Browser sign-in requires a client id and an exact redirect URI.
        if settings.auth_client_id and settings.auth_redirect_uri:
            from app.auth.oidc_flow import OidcFlow, OidcFlowConfig

            app.state.oidc_flow = OidcFlow(
                OidcFlowConfig(
                    issuer=settings.auth_issuer,
                    client_id=settings.auth_client_id,
                    redirect_uri=settings.auth_redirect_uri,
                    post_login_redirect=settings.auth_post_login_redirect,
                    client_secret=settings.auth_client_secret,
                    required_amr=settings.auth_required_amr,
                ),
                provider=app.state.identity_provider,
            )

    allow_credentials = settings.auth_mode == "production"
    origins = list(settings.cors_origins)
    if allow_credentials and ("*" in origins or not origins):
        raise RuntimeError(
            "Production authenticated CORS requires explicit CARETWIN_CORS_ORIGINS "
            "and must not use '*'."
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Demo-User-Id", "Accept", "X-CSRF-Token"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        # Defense-in-depth: reject obviously oversized API bodies early.
        if request.url.path.startswith(settings.api_prefix):
            limit = settings.max_upload_bytes + 1024 * 1024
            content_length = request.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > limit:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "payload_too_large",
                            "message": "The request payload is too large.",
                            "details": {},
                            "requestId": request_id,
                        }
                    },
                )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.middleware("http")
    async def harden_response(request: Request, call_next):
        """Baseline browser hardening plus no-store for personalised API data."""
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if request.url.path.startswith(settings.api_prefix):
            response.headers.setdefault("Content-Security-Policy", _API_CSP)
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "requestId": getattr(request.state, "request_id", None),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [
            {
                "location": ".".join(str(part) for part in error.get("loc", [])),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_failed",
                    "message": "The request payload did not pass validation.",
                    "details": {"fields": fields},
                    "requestId": getattr(request.state, "request_id", None),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        LOGGER.exception("Unhandled request failure request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected server error occurred.",
                    "details": {},
                    "requestId": request_id,
                }
            },
        )

    app.include_router(v1_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": "CareTwin AI API",
            "api": settings.api_prefix,
            "docs": "/docs",
        }

    return app


app = create_app()
