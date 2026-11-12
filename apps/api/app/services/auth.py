from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.errors import forbidden, not_found, unauthorized
from app.repositories.store import Store


@dataclass(frozen=True)
class AccessContext:
    user: dict[str, Any]
    patient: dict[str, Any]
    relationship: dict[str, Any]
    scopes: tuple[str, ...]
    consent_id: str | None


def get_user(store: Store, user_id: str | None) -> dict[str, Any]:
    if not user_id:
        raise unauthorized("Provide a demo user via the X-Demo-User-Id header.")
    user = store.get_user(user_id)
    if not user:
        raise unauthorized("The demo user could not be resolved.")
    return user


def get_patient_or_404(store: Store, patient_id: str) -> dict[str, Any]:
    patient = store.get_patient(patient_id)
    if not patient:
        raise not_found("Patient")
    return patient


def effective_scopes(store: Store, user: dict[str, Any], patient_id: str) -> tuple[list[str], dict[str, Any], str | None]:
    relationship = store.get_relationship(patient_id, user["id"])
    if not relationship or relationship["status"] != "active":
        raise forbidden("No active care relationship exists for this patient.")

    if user["role"] == "patient":
        if relationship["relationship"] != "self":
            raise forbidden("A patient can only access their own recovery twin.")
        return ["*"], relationship, None

    if user["role"] == "clinician":
        relationship_scopes = relationship.get("scopes", [])
        if "*" not in relationship_scopes:
            raise forbidden("The clinician relationship is not authorized.")
        return ["*"], relationship, None

    if user["role"] == "caregiver":
        consent = store.get_active_consent(patient_id, user["id"])
        if not consent:
            raise forbidden(
                "Caregiver sharing is not active for this patient.",
                {"reason": "consent_revoked_or_missing"},
            )
        allowed = set(relationship.get("scopes", [])) & set(consent.get("scopes", []))
        return sorted(allowed), relationship, consent["id"]

    raise forbidden("Unknown role.")


def require_access(
    store: Store,
    user: dict[str, Any],
    patient_id: str,
    scope: str,
) -> AccessContext:
    patient = get_patient_or_404(store, patient_id)
    scopes, relationship, consent_id = effective_scopes(store, user, patient_id)
    if "*" not in scopes and scope not in scopes:
        raise forbidden(
            "This action is outside the active consent scope.",
            {"requiredScope": scope},
        )
    return AccessContext(
        user=user,
        patient=patient,
        relationship=relationship,
        scopes=tuple(scopes),
        consent_id=consent_id,
    )


def require_patient_self(
    store: Store, user: dict[str, Any], patient_id: str
) -> AccessContext:
    if user["role"] != "patient":
        raise forbidden("Only the patient can perform this action.")
    return require_access(store, user, patient_id, "twin:read")


def require_clinician(
    store: Store, user: dict[str, Any], patient_id: str, scope: str = "twin:read"
) -> AccessContext:
    if user["role"] != "clinician":
        raise forbidden("Only a clinician can perform this action.")
    return require_access(store, user, patient_id, scope)


def require_caregiver(
    store: Store, user: dict[str, Any], patient_id: str, scope: str
) -> AccessContext:
    if user["role"] != "caregiver":
        raise forbidden("Only an authorized caregiver can perform this action.")
    return require_access(store, user, patient_id, scope)
