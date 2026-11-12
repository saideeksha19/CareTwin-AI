from __future__ import annotations

import os
from typing import Any

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import FileResponse, RedirectResponse

from app.ai.service import AiService
from app.auth import sessions as auth_sessions
from app.auth.identity import (
    bearer_token,
    record_auth_event,
    resolve_identity,
)
from app.auth.oidc_flow import OidcFlowError
from app.auth.tokens import TokenError
from app.deps import (
    current_user,
    get_ai_service,
    get_rate_limiter,
    get_settings,
    get_store,
)
from app.domain.schemas import (
    AiExplainRequest,
    AssistantAskRequest,
    AlertAcknowledgeRequest,
    AlertResolveRequest,
    CheckinResponse,
    ConsentUpdateRequest,
    CreateCheckinRequest,
    CreateEncounterRequest,
    CreateLabResultRequest,
    CreateObservationRequest,
    DemoSessionResponse,
    DemoSwitchRequest,
    DocumentExplainRequest,
    DocumentReviewRequest,
    GuidanceRequest,
    HealthResponse,
    MedicationVerifyRequest,
    MilestoneUpdateRequest,
    MonitoringRuleUpdateRequest,
    ObservationResponse,
    TimelineResponse,
    TwinResponse,
)
from app.errors import ApiError, not_found
from app.repositories.store import Store
from app.services import (
    agent_registry,
    assistant_service,
    alert_service,
    clinical_records_service,
    clinical_service,
    consent_service,
    document_service,
    observation_service,
    record_service,
    summary_service,
    twin_service,
)
from app.safety.rate_limit import SlidingWindowLimiter
from app.services.auth import require_access
from app.services.checkin_service import create_checkin
from app.services.twin_service import build_twin
from app.utils import iso

router = APIRouter()


def _component_database(store: Store) -> dict[str, Any]:
    try:
        store.conn.execute("SELECT 1").fetchone()
        fk = store.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        return {"status": "ok", "engine": "sqlite", "foreignKeys": bool(fk)}
    except Exception:
        return {"status": "error", "engine": "sqlite"}


def _component_storage(settings) -> dict[str, Any]:
    try:
        root = settings.document_storage_path
        exists = root.exists() and root.is_dir()
        writable = exists and os.access(root, os.W_OK)
        return {
            "status": "ok" if exists else "error",
            "backend": getattr(settings, "storage_backend", "local"),
            "writable": bool(writable),
        }
    except Exception:
        return {"status": "error", "backend": getattr(settings, "storage_backend", "local")}


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(
    request: Request,
    store: Store = Depends(get_store),
    settings=Depends(get_settings),
    ai: AiService = Depends(get_ai_service),
) -> dict[str, Any]:
    db = _component_database(store)
    storage = _component_storage(settings)
    ai_status = ai.status()
    auth_configured = settings.auth_mode == "production"
    status = "ok" if db.get("status") == "ok" and storage.get("status") == "ok" else "degraded"
    return {
        "status": status,
        "service": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "database": "connected" if db.get("status") == "ok" else "error",
        "aiState": ai_status["state"],
        "demoMode": settings.demo_mode,
        "authMode": settings.auth_mode,
        "requestId": getattr(request.state, "request_id", None),
        "components": {
            "database": db,
            "storage": {"status": storage.get("status"), "backend": storage.get("backend")},
            "ai": {
                "status": "configured" if ai_status.get("configured") else "not_configured",
                "state": ai_status.get("state"),
            },
            "authentication": {
                "mode": settings.auth_mode,
                "configured": bool(auth_configured),
            },
        },
    }


@router.get("/ready", tags=["system"])
def ready(
    request: Request,
    store: Store = Depends(get_store),
    settings=Depends(get_settings),
    ai: AiService = Depends(get_ai_service),
) -> dict[str, Any]:
    db = _component_database(store)
    storage = _component_storage(settings)
    ai_status = ai.status()
    config_issues = []
    try:
        config_issues = settings.production_config_issues()
    except Exception:
        config_issues = []
    # Readiness is conservative: core dependencies must be reachable. AI/auth
    # provider live availability is reported but does not make local demo unusable.
    ready_state = db.get("status") == "ok" and storage.get("status") == "ok"
    return {
        "ready": ready_state,
        "requestId": getattr(request.state, "request_id", None),
        "components": {
            "database": db,
            "storage": storage,
            "aiProvider": {
                "configured": bool(ai_status.get("configured")),
                "state": ai_status.get("state"),
            },
            "authentication": {
                "mode": settings.auth_mode,
                "configured": settings.auth_mode == "production",
            },
            "rateLimiting": {
                "backend": getattr(request.app.state.rate_limiter, "backend", "memory"),
                "sharedStoreConfigured": bool(getattr(request.app.state.rate_limiter, "is_shared_store", False)),
            },
        },
        "productionConfigIssues": config_issues,
    }


def _demo_session_payload(store: Store, patient: dict[str, Any]) -> dict[str, Any]:
    users = []
    for user in store.list_users():
        relationship = store.get_relationship(patient["id"], user["id"])
        if not relationship:
            continue
        consent_status = "not_required"
        scopes = list(relationship.get("scopes", []))
        if user["role"] == "caregiver":
            consent = store.get_active_consent(patient["id"], user["id"])
            if consent:
                consent_status = "granted"
                scopes = sorted(
                    set(scopes) & set(consent.get("scopes", []))
                )
            else:
                consent_status = "revoked"
                scopes = []
        users.append(
            {
                "id": user["id"],
                "name": user["name"],
                "role": user["role"],
                "title": user["title"],
                "organization": user["organization"],
                "initials": user["initials"],
                "patientId": patient["id"],
                "linkedPatientName": patient["full_name"],
                "consentStatus": consent_status,
                "scopes": scopes,
            }
        )
    return {
        "users": users,
        "patient": {
            "id": patient["id"],
            "fullName": patient["full_name"],
            "synthetic": True,
        },
        "disclaimer": (
            "Synthetic demo access. No real patient information. "
            "Role identity is provided by a demo header, not production authentication."
        ),
    }


@router.get("/demo/session", response_model=DemoSessionResponse, tags=["demo"])
def demo_session(
    request: Request, store: Store = Depends(get_store)
) -> dict[str, Any]:
    # The synthetic switcher is a demo-mode capability only. Production mode never
    # exposes demo identities, not even read-only.
    if request.app.state.settings.auth_mode != "demo":
        raise not_found("Demo session")
    patient = store.get_patient("pat_maya")
    if not patient:
        raise not_found("Demo patient")
    return _demo_session_payload(store, patient)


@router.post(
    "/demo/session/switch", response_model=DemoSessionResponse, tags=["demo"]
)
def demo_session_switch(
    request: Request,
    payload: DemoSwitchRequest,
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    if request.app.state.settings.auth_mode != "demo":
        raise not_found("Demo session")
    patient = store.get_patient("pat_maya")
    if not patient:
        raise not_found("Demo patient")
    session = _demo_session_payload(store, patient)
    target = next(
        (user for user in session["users"] if user["id"] == payload.user_id), None
    )
    if not target:
        raise not_found("Demo identity")
    record_auth_event(
        store,
        event="demo.role_switched",
        outcome="allowed",
        user_id=target["id"],
        reason="synthetic_demo_switch",
    )
    return session


@router.get("/patients", tags=["patients"])
def list_patients(
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return record_service.list_accessible_patients(store, user=user)


@router.get(
    "/patients/{patient_id}/twin",
    response_model=TwinResponse,
    tags=["recovery-twin"],
)
def get_twin(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    access = require_access(store, user, patient_id, "twin:read")
    twin = store.get_twin(patient_id)
    if not twin:
        raise not_found("Recovery twin")
    return build_twin(
        store,
        patient=access.patient,
        twin=twin,
        role=user["role"],
        scopes=access.scopes,
    )


@router.get(
    "/patients/{patient_id}/timeline",
    response_model=TimelineResponse,
    tags=["timeline"],
)
def get_timeline(
    patient_id: str,
    event_type: str | None = Query(default=None, alias="eventType"),
    source_type: str | None = Query(default=None, alias="sourceType"),
    verification_status: str | None = Query(default=None, alias="verificationStatus"),
    limit: int = Query(default=200, ge=1, le=500),
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return record_service.get_timeline(
        store,
        user=user,
        patient_id=patient_id,
        event_type=event_type,
        source_type=source_type,
        verification_status=verification_status,
        limit=limit,
    )


@router.get("/patients/{patient_id}/audit", tags=["audit"])
def get_audit(
    patient_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return record_service.list_audit(
        store, user=user, patient_id=patient_id, limit=limit
    )


@router.get("/patients/{patient_id}/snapshots", tags=["recovery-twin"])
def get_snapshots(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return record_service.list_snapshots(store, user=user, patient_id=patient_id)


@router.get("/patients/{patient_id}/snapshots/{snapshot_id}", tags=["recovery-twin"])
def get_snapshot(
    patient_id: str,
    snapshot_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    snapshot = record_service.get_snapshot(
        store, user=user, patient_id=patient_id, snapshot_id=snapshot_id
    )
    if not snapshot:
        raise not_found("Twin snapshot")
    return snapshot


@router.get("/patients/{patient_id}/evidence", tags=["evidence"])
def get_evidence(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return record_service.list_evidence(store, user=user, patient_id=patient_id)


@router.get("/patients/{patient_id}/checkins", tags=["check-ins"])
def get_checkins(
    patient_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return record_service.list_checkins(
        store, user=user, patient_id=patient_id, limit=limit
    )


@router.post(
    "/patients/{patient_id}/checkins",
    response_model=CheckinResponse,
    tags=["check-ins"],
)
def post_checkin(
    patient_id: str,
    payload: CreateCheckinRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return create_checkin(store, user=user, patient_id=patient_id, payload=payload)


@router.get("/patients/{patient_id}/observations", tags=["caregiver"])
def get_observations(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return record_service.list_observations(store, user=user, patient_id=patient_id)


@router.post(
    "/patients/{patient_id}/observations",
    response_model=ObservationResponse,
    tags=["caregiver"],
)
def post_observation(
    patient_id: str,
    payload: CreateObservationRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return observation_service.create_observation(
        store, user=user, patient_id=patient_id, payload=payload
    )



@router.get("/patients/{patient_id}/labs", tags=["clinical-records"])
def get_lab_results(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return clinical_records_service.list_lab_results(store, user=user, patient_id=patient_id)


@router.post("/patients/{patient_id}/labs", tags=["clinical-records"])
def post_lab_result(
    patient_id: str,
    payload: CreateLabResultRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return clinical_records_service.create_lab_result(
        store, user=user, patient_id=patient_id, payload=payload
    )


@router.get("/patients/{patient_id}/encounters", tags=["clinical-records"])
def get_encounters(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return clinical_records_service.list_encounters(store, user=user, patient_id=patient_id)


@router.post("/patients/{patient_id}/encounters", tags=["clinical-records"])
def post_encounter(
    patient_id: str,
    payload: CreateEncounterRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return clinical_records_service.create_encounter(
        store, user=user, patient_id=patient_id, payload=payload
    )

@router.get("/patients/{patient_id}/alerts", tags=["safety"])
def get_alerts(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return alert_service.list_alerts(store, user=user, patient_id=patient_id)


@router.post(
    "/patients/{patient_id}/alerts/{alert_id}/acknowledge", tags=["safety"]
)
def acknowledge_alert(
    patient_id: str,
    alert_id: str,
    payload: AlertAcknowledgeRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return alert_service.acknowledge_alert(
        store,
        user=user,
        patient_id=patient_id,
        alert_id=alert_id,
        payload=payload,
    )


@router.post("/patients/{patient_id}/alerts/{alert_id}/resolve", tags=["safety"])
def resolve_alert(
    patient_id: str,
    alert_id: str,
    payload: AlertResolveRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return alert_service.resolve_alert(
        store,
        user=user,
        patient_id=patient_id,
        alert_id=alert_id,
        payload=payload,
    )


@router.get("/patients/{patient_id}/consents", tags=["consent"])
def get_consents(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return consent_service.list_consents(store, user=user, patient_id=patient_id)


@router.patch("/patients/{patient_id}/consents/{consent_id}", tags=["consent"])
def patch_consent(
    patient_id: str,
    consent_id: str,
    payload: ConsentUpdateRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return consent_service.update_consent(
        store,
        user=user,
        patient_id=patient_id,
        consent_id=consent_id,
        payload=payload,
    )


@router.get("/patients/{patient_id}/clinical-summary", tags=["clinical"])
def get_clinical_summary(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return summary_service.generate_clinical_summary(
        store, user=user, patient_id=patient_id
    )


@router.get("/patients/{patient_id}/safety-decisions", tags=["safety"])
def get_safety_decisions(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return record_service.list_safety_decisions(
        store, user=user, patient_id=patient_id
    )


@router.get("/patients/{patient_id}/monitoring-rules", tags=["safety"])
def get_monitoring_rules(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return clinical_service.list_rules(store, user=user, patient_id=patient_id)


@router.patch(
    "/patients/{patient_id}/monitoring-rules/{rule_id}", tags=["safety"]
)
def patch_monitoring_rule(
    patient_id: str,
    rule_id: str,
    payload: MonitoringRuleUpdateRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return clinical_service.update_rule(
        store,
        user=user,
        patient_id=patient_id,
        rule_id=rule_id,
        payload=payload,
    )


@router.post("/patients/{patient_id}/monitoring/run", tags=["safety"])
def run_monitoring(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return clinical_service.run_monitoring_sweep_for_clinician(
        store, user=user, patient_id=patient_id
    )


@router.post(
    "/patients/{patient_id}/medications/{medication_id}/verify", tags=["clinical"]
)
def verify_medication(
    patient_id: str,
    medication_id: str,
    payload: MedicationVerifyRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return clinical_service.verify_medication(
        store,
        user=user,
        patient_id=patient_id,
        medication_id=medication_id,
        payload=payload,
    )


@router.patch(
    "/patients/{patient_id}/milestones/{milestone_id}", tags=["clinical"]
)
def patch_milestone(
    patient_id: str,
    milestone_id: str,
    payload: MilestoneUpdateRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return clinical_service.update_milestone(
        store,
        user=user,
        patient_id=patient_id,
        milestone_id=milestone_id,
        payload=payload,
    )


@router.get("/agents", tags=["intelligence"])
def get_agents() -> dict[str, Any]:
    return {"generatedAt": iso(), "agents": agent_registry.list_agents()}


@router.get("/auth/login", tags=["auth"])
def auth_login(
    request: Request,
    store: Store = Depends(get_store),
    settings=Depends(get_settings),
    limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
):
    limiter.hit("auth_login", request.client.host if request.client else "unknown", 120)
    """Start Authorization Code + PKCE. State is bound to an HttpOnly cookie."""
    if settings.auth_mode != "production":
        raise not_found("Production sign-in")
    flow = getattr(request.app.state, "oidc_flow", None)
    if flow is None:
        raise ApiError(
            503,
            "provider_not_configured",
            "Sign-in is not configured on this server.",
        )
    try:
        state, authorize_url = flow.start(store)
    except OidcFlowError as exc:
        record_auth_event(
            store,
            event="auth.login_failed",
            outcome="denied",
            reason=exc.reason,
        )
        raise ApiError(
            503, "provider_not_configured", "Sign-in is not configured on this server."
        ) from exc
    response = RedirectResponse(authorize_url, status_code=302)
    response.set_cookie(
        auth_sessions.OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/auth/callback", tags=["auth"])
def auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    store: Store = Depends(get_store),
    settings=Depends(get_settings),
    limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
):
    limiter.hit("auth_callback", request.client.host if request.client else "unknown", 240)
    """Complete the flow, verify the ID token and create a server-side session."""
    if settings.auth_mode != "production":
        raise not_found("Production sign-in")
    flow = getattr(request.app.state, "oidc_flow", None)
    if flow is None:
        raise ApiError(
            503, "provider_not_configured", "Sign-in is not configured on this server."
        )
    if error:
        record_auth_event(
            store, event="auth.login_failed", outcome="denied", reason="provider_error"
        )
        raise ApiError(401, "authentication_failed", "Sign-in could not be completed.")

    cookie_state = request.cookies.get(auth_sessions.OAUTH_STATE_COOKIE)
    if (
        not cookie_state
        or not state
        or not __import__("hmac").compare_digest(cookie_state, state)
    ):
        record_auth_event(
            store,
            event="auth.login_failed",
            outcome="denied",
            reason="state_mismatch",
        )
        raise ApiError(401, "authentication_failed", "Sign-in could not be completed.")

    try:
        identity = flow.complete(store, code=code or "", state=state)
    except OidcFlowError as exc:
        record_auth_event(
            store,
            event="auth.login_failed",
            outcome="denied",
            reason=exc.reason,
        )
        raise ApiError(
            401, "authentication_failed", "Sign-in could not be completed."
        ) from exc

    user = resolve_identity(
        store, identity, require_link=settings.auth_require_identity_link
    )
    token, csrf, _session = auth_sessions.create_session(
        store,
        user_id=user["id"],
        issuer=identity.issuer,
        subject=identity.subject,
        auth_time=identity.claims.get("auth_time"),
        amr=str(identity.claims.get("amr") or "").split(),
        ttl_seconds=settings.auth_session_ttl_seconds,
    )
    record_auth_event(
        store,
        event="auth.login_succeeded",
        outcome="allowed",
        identity=identity,
        user_id=user["id"],
        reason="session_created",
    )

    target = settings.auth_post_login_redirect or "/workspace"
    # Allow only same-origin relative paths; reject protocol-relative URLs,
    # backslash tricks, and control characters to prevent open redirects.
    if (
        not isinstance(target, str)
        or not target.startswith("/")
        or target.startswith("//")
        or "\\" in target
        or any(ord(ch) < 32 for ch in target)
    ):
        target = "/workspace"
    response = RedirectResponse(target, status_code=303)
    auth_sessions.set_session_cookies(
        response,
        token,
        csrf,
        ttl_seconds=settings.auth_session_ttl_seconds,
        secure=settings.auth_cookie_secure,
    )
    response.delete_cookie(auth_sessions.OAUTH_STATE_COOKIE, path="/")
    return response


@router.get("/auth/session", tags=["auth"])
def auth_session(
    user: dict[str, Any] = Depends(current_user),
    settings=Depends(get_settings),
) -> dict[str, Any]:
    return {
        "authenticated": True,
        "mode": settings.auth_mode,
        "providerDependent": settings.auth_mode == "production",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "role": user["role"],
            "title": user.get("title", ""),
            "organization": user.get("organization", ""),
            "initials": user.get("initials", ""),
        },
    }


@router.post("/auth/logout", tags=["auth"])
def auth_logout(
    request: Request,
    response: Response,
    store: Store = Depends(get_store),
    settings=Depends(get_settings),
    user: dict[str, Any] = Depends(current_user),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    if settings.auth_mode != "production":
        return {"mode": "demo", "revoked": False}
    session_token = request.cookies.get(auth_sessions.SESSION_COOKIE)
    if session_token:
        row = store.get_auth_session_by_hash(
            auth_sessions.token_hash(session_token)
        )
        if row and not row["revoked_at"]:
            store.revoke_auth_session(row["id"], reason="logout")
            record_auth_event(
                store,
                event="auth.logout",
                outcome="allowed",
                user_id=user["id"],
                reason="session_revoked",
            )
            auth_sessions.clear_session_cookies(
                response, secure=settings.auth_cookie_secure
            )
            return {"mode": "production", "revoked": True, "scope": "session"}
    provider = getattr(request.app.state, "identity_provider", None)
    if provider is None:
        raise ApiError(
            503,
            "auth_not_configured",
            "Authentication is not configured on this server.",
        )
    try:
        identity = provider.verify(
            bearer_token(authorization), revoked=store.is_token_revoked
        )
    except TokenError as exc:
        record_auth_event(
            store,
            event="auth.logout_rejected",
            outcome="denied",
            user_id=user["id"],
            reason="invalid_token",
        )
        raise ApiError(
            401, "authentication_required", "A valid access token is required."
        ) from exc
    if not identity.jti:
        return {"mode": "production", "revoked": False}
    store.revoke_token(
        jti=identity.jti,
        issuer=identity.issuer,
        subject=identity.subject,
        expires_at=datetime.fromtimestamp(
            identity.expires_at, tz=timezone.utc
        ).isoformat(),
        reason="logout",
    )
    record_auth_event(
        store,
        event="auth.logout",
        outcome="allowed",
        identity=identity,
        user_id=user["id"],
        reason="token_revoked",
    )
    return {"mode": "production", "revoked": True, "scope": "token"}


@router.get("/auth/sessions", tags=["auth"])
def list_auth_sessions(
    request: Request,
    store: Store = Depends(get_store),
    settings=Depends(get_settings),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if settings.auth_mode != "production":
        return {"mode": "demo", "currentSessionId": None, "sessions": []}
    token = request.cookies.get(auth_sessions.SESSION_COOKIE)
    current_hash = auth_sessions.token_hash(token) if token else ""
    rows = store.list_user_sessions(user["id"])
    return {
        "mode": "production",
        "currentSessionId": next(
            (row["id"] for row in rows if row["token_hash"] == current_hash), None
        ),
        "sessions": [
            {
                "id": row["id"],
                "createdAt": row["created_at"],
                "lastSeenAt": row["last_seen_at"],
                "expiresAt": row["expires_at"],
                "revokedAt": row["revoked_at"],
                "amr": row["amr"],
                "current": row["token_hash"] == current_hash,
            }
            for row in rows
        ],
    }


@router.delete("/auth/sessions/{session_id}", tags=["auth"])
def revoke_auth_session(
    session_id: str,
    store: Store = Depends(get_store),
    settings=Depends(get_settings),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if settings.auth_mode != "production":
        raise not_found("Session")
    row = store.get_auth_session(session_id)
    if not row or row["user_id"] != user["id"]:
        raise not_found("Session")
    store.revoke_auth_session(session_id, reason="user_revoked")
    record_auth_event(
        store,
        event="auth.session_revoked",
        outcome="allowed",
        user_id=user["id"],
        reason="user_revoked",
    )
    return {"revoked": True, "sessionId": session_id}


@router.post("/auth/sessions/revoke-all", tags=["auth"])
def revoke_all_auth_sessions(
    response: Response,
    store: Store = Depends(get_store),
    settings=Depends(get_settings),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Account-wide revocation of every local session for the signed-in account."""
    if settings.auth_mode != "production":
        raise not_found("Session")
    revoked = store.revoke_user_sessions(user["id"], reason="user_revoked_all")
    record_auth_event(
        store,
        event="auth.sessions_revoked_all",
        outcome="allowed",
        user_id=user["id"],
        reason=f"revoked_{revoked}",
    )
    auth_sessions.clear_session_cookies(response, secure=settings.auth_cookie_secure)
    return {"revoked": revoked}


@router.get("/ai/status", tags=["intelligence"])
def get_ai_status(ai: AiService = Depends(get_ai_service)) -> dict[str, Any]:
    return ai.status()


@router.get("/ai/health", tags=["intelligence"])
def get_ai_health(ai: AiService = Depends(get_ai_service)) -> dict[str, Any]:
    """Live credential/connectivity check. Never raises and never leaks the key."""
    return ai.health()


@router.post("/ai/explain", tags=["intelligence"])
def explain(
    payload: AiExplainRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
    ai: AiService = Depends(get_ai_service),
) -> dict[str, Any]:
    return ai.explain(
        store,
        user=user,
        patient_id=payload.patient_id,
        question=payload.question,
    )


@router.get("/meta", tags=["system"])
def meta(request: Request) -> dict[str, Any]:
    return {
        "name": "CareTwin AI API",
        "apiPrefix": request.app.state.settings.api_prefix,
        "docs": "/docs",
        "syntheticOnly": True,
        "generatedAt": iso(),
    }


# --------------------------------------------------------------- documents
@router.post("/patients/{patient_id}/documents", tags=["documents"])
async def upload_document(
    patient_id: str,
    request: Request,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
    settings=Depends(get_settings),
    limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
) -> dict[str, Any]:
    limiter.hit("upload", user["id"], settings.upload_requests_per_hour)
    try:
        # prefer FastAPI/Starlette form parsing if available
        form = await request.form()
        upload = form.get("file")
        document_type = str(form.get("documentType") or form.get("document_type") or "other_medical_document")
        if upload is not None and hasattr(upload, "read"):
            data = await upload.read()
            filename = getattr(upload, "filename", "document")
            ctype = getattr(upload, "content_type", None)
        else:
            raise RuntimeError("form file unavailable")
    except Exception:
        data, filename, ctype, fields = await document_service.parse_multipart_upload(request)
        document_type = fields.get("documentType") or fields.get("document_type") or "other_medical_document"
    return document_service.upload_document(
        store, settings, user=user, patient_id=patient_id,
        filename=filename, content_type=ctype, data=data, document_type=document_type,
    )


@router.get("/patients/{patient_id}/documents", tags=["documents"])
def list_documents(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return document_service.list_documents(store, user=user, patient_id=patient_id)


@router.get("/patients/{patient_id}/documents/{document_id}", tags=["documents"])
def get_document(
    patient_id: str,
    document_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return document_service.get_document_detail(store, user=user, patient_id=patient_id, document_id=document_id)


@router.get("/patients/{patient_id}/documents/{document_id}/status", tags=["documents"])
def get_document_status(
    patient_id: str,
    document_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return document_service.get_document_status(store, user=user, patient_id=patient_id, document_id=document_id)


@router.get("/patients/{patient_id}/documents/{document_id}/extractions", tags=["documents"])
def get_document_extractions(
    patient_id: str,
    document_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    detail = document_service.get_document_detail(store, user=user, patient_id=patient_id, document_id=document_id)
    return {"documentId": document_id, "extractions": detail.get("extractions", []), "pages": detail.get("pages", [])}


@router.post("/patients/{patient_id}/documents/{document_id}/extractions/{extraction_id}/review", tags=["documents"])
def review_document_extraction(
    patient_id: str,
    document_id: str,
    extraction_id: str,
    payload: DocumentReviewRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return document_service.review_extraction(
        store, user=user, patient_id=patient_id, document_id=document_id, extraction_id=extraction_id, payload=payload,
    )


@router.get("/patients/{patient_id}/documents/{document_id}/analysis", tags=["documents"])
def get_document_analysis(
    patient_id: str,
    document_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
    ai: AiService = Depends(get_ai_service),
) -> dict[str, Any]:
    return document_service.get_document_analysis(
        store, user=user, patient_id=patient_id, document_id=document_id, ai_status=ai.status()
    )


@router.get("/patients/{patient_id}/documents/{document_id}/explanation", tags=["documents"])
def get_document_explanation(
    patient_id: str,
    document_id: str,
    mode: str = Query(default="report", pattern="^(report|prescription)$"),
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return document_service.get_document_explanation(
        store, user=user, patient_id=patient_id, document_id=document_id, mode=mode
    )


@router.post("/patients/{patient_id}/documents/{document_id}/explain", tags=["documents"])
def explain_document(
    patient_id: str,
    document_id: str,
    payload: DocumentExplainRequest | None = None,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
    ai: AiService = Depends(get_ai_service),
) -> dict[str, Any]:
    return document_service.explain_document(
        store,
        ai,
        user=user,
        patient_id=patient_id,
        document_id=document_id,
        mode=(payload.mode if payload else "report"),
        force=bool(payload.force) if payload else False,
    )


@router.get("/patients/{patient_id}/documents/{document_id}/prescription", tags=["documents"])
def get_document_prescription(
    patient_id: str,
    document_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return document_service.get_document_prescription(
        store, user=user, patient_id=patient_id, document_id=document_id
    )


@router.get("/patients/{patient_id}/documents/{document_id}/file", tags=["documents"])
def get_document_file(
    patient_id: str,
    document_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
    settings=Depends(get_settings),
) -> FileResponse:
    path, media_type, filename = document_service.get_document_file(
        store, settings, user=user, patient_id=patient_id, document_id=document_id
    )
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/patients/{patient_id}/documents/{document_id}/reprocess", tags=["documents"])
def reprocess_document(
    patient_id: str,
    document_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
    settings=Depends(get_settings),
) -> dict[str, Any]:
    return document_service.reprocess_document(
        store, settings, user=user, patient_id=patient_id, document_id=document_id
    )


@router.get("/patients/{patient_id}/reports/comparison", tags=["documents"])
def compare_reports(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return document_service.compare_patient_reports(store, user=user, patient_id=patient_id)


@router.post("/patients/{patient_id}/assistant/ask", tags=["intelligence"])
def ask_assistant(
    patient_id: str,
    payload: AssistantAskRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
    ai: AiService = Depends(get_ai_service),
    settings=Depends(get_settings),
    limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
) -> dict[str, Any]:
    limiter.hit("assistant", user["id"], settings.assistant_requests_per_hour)
    if payload.patient_id != patient_id:
        from app.errors import validation_error

        raise validation_error("Patient in body does not match the path.")
    if user["role"] == "caregiver":
        from app.errors import forbidden

        raise forbidden(
            "The assistant is limited to the patient and the care team. Caregivers keep shared records access."
        )
    return assistant_service.ask_assistant(
        store,
        ai,
        user=user,
        patient_id=patient_id,
        question=payload.question,
        conversation_id=payload.conversation_id,
        document_id=payload.document_id,
    )


@router.get("/patients/{patient_id}/assistant/history", tags=["intelligence"])
def assistant_history(
    patient_id: str,
    conversation_id: str | None = Query(default=None, alias="conversationId"),
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return assistant_service.list_conversation(
        store, user=user, patient_id=patient_id, conversation_id=conversation_id
    )


@router.get("/patients/{patient_id}/document-history", tags=["documents"])
def get_document_history(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    docs = document_service.list_documents(store, user=user, patient_id=patient_id)
    return {"patientId": patient_id, "documents": docs, "total": len(docs)}


@router.post("/patients/{patient_id}/guidance", tags=["guidance"])
def create_guidance(
    patient_id: str,
    payload: GuidanceRequest,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
    settings=Depends(get_settings),
    ai: AiService = Depends(get_ai_service),
) -> dict[str, Any]:
    return document_service.generate_guidance(store, settings, ai, user=user, patient_id=patient_id, payload=payload)


@router.get("/patients/{patient_id}/guidance/history", tags=["guidance"])
def get_guidance_history(
    patient_id: str,
    store: Store = Depends(get_store),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    return document_service.list_guidance_history(store, user=user, patient_id=patient_id)

