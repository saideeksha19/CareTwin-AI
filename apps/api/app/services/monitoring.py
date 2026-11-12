from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.repositories.store import Store
from app.utils import iso, new_id, parse_iso, utc_now


def _rule_rows(store: Store, patient_id: str) -> list[dict[str, Any]]:
    return store.list_rules(patient_id)


def _now_dt(now: str | None = None) -> datetime:
    if now:
        return parse_iso(now)
    return utc_now()


def _value_for_checkin(
    *,
    input_type: str,
    input_key: str,
    checkin: dict[str, Any],
    prior_checkin: dict[str, Any] | None,
    now: datetime,
) -> Any:
    symptoms = {s.get("symptom_code"): s for s in checkin.get("symptoms", [])}
    if input_type == "symptom_severity":
        symptom = symptoms.get(input_key)
        return symptom.get("severity") if symptom else None
    if input_type == "temperature":
        return checkin.get("temperature_c")
    if input_type == "missed_doses":
        return checkin.get("missed_doses")
    if input_type == "pain_delta":
        if not prior_checkin:
            return None
        return (checkin.get("pain_score") or 0) - (prior_checkin.get("pain_score") or 0)
    if input_type == "checkin_gap_hours":
        if not prior_checkin:
            return None
        submitted = parse_iso(
            checkin.get("submitted_at") or checkin.get("created_at") or iso(now)
        )
        prev = parse_iso(prior_checkin["submitted_at"])
        return max(0.0, (submitted - prev).total_seconds() / 3600)
    if input_type == "observation_category":
        return checkin.get("category")
    if input_type == "observation_note":
        return checkin.get("note")
    if input_type == "observation_severity":
        details = checkin.get("details") or {}
        return details.get("severity") if isinstance(details, dict) else None
    if input_key and input_key in checkin:
        return checkin.get(input_key)
    return None


def _value_for_sweep(
    *,
    input_type: str,
    input_key: str,
    patient: dict[str, Any],
    latest_checkin: dict[str, Any] | None,
    now: datetime,
) -> Any:
    if input_type == "checkin_gap_hours":
        if latest_checkin:
            return max(
                0.0,
                (now - parse_iso(latest_checkin["submitted_at"])).total_seconds() / 3600,
            )
        discharged = parse_iso(f"{patient['discharged_on']}T09:00:00+00:00")
        return max(0.0, (now - discharged).total_seconds() / 3600)
    return None


def _parse_in_set(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        return [part.strip() for part in text.split(",") if part.strip()]
    return [value]


def _normalize_number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return value
    try:
        if isinstance(value, str) and value.strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _matches(operator: str, observed: Any, threshold: Any, comparison_value: Any = None) -> tuple[bool, str]:
    op = (operator or "greater_than_or_equal").lower()
    if op == "missing":
        missing = observed is None or observed == "" or observed == []
        return missing, "value is missing" if missing else f"value present ({observed!r})"
    if op == "stale":
        obs_num = _normalize_number(observed)
        thr_num = _normalize_number(threshold)
        if obs_num is None or thr_num is None:
            return False, "stale comparison unavailable"
        ok = obs_num >= thr_num
        return ok, f"age {obs_num} >= threshold {thr_num}"
    if op == "in_set":
        choices = _parse_in_set(comparison_value if comparison_value is not None else threshold)
        if observed in choices:
            ok = True
        else:
            obs_s = str(observed)
            ok = obs_s in {str(c) for c in choices}
        return ok, f"value {observed!r} {'in' if ok else 'not in'} configured set"
    if op == "equals":
        if isinstance(observed, (int, float)) and isinstance(threshold, (int, float)):
            ok = float(observed) == float(threshold)
        else:
            ok = str(observed) == str(threshold)
        return ok, f"value {observed!r} {'==' if ok else '!='} {threshold!r}"
    if op == "not_equals":
        if isinstance(observed, (int, float)) and isinstance(threshold, (int, float)):
            ok = float(observed) != float(threshold)
        else:
            ok = str(observed) != str(threshold)
        return ok, f"value {observed!r} {'!=' if ok else '=='} {threshold!r}"

    obs_num = _normalize_number(observed)
    thr_num = _normalize_number(threshold)
    if obs_num is None or thr_num is None:
        return False, "numeric comparison unavailable"
    if op == "greater_than":
        ok = obs_num > thr_num
        sym = ">"
    elif op == "greater_than_or_equal":
        ok = obs_num >= thr_num
        sym = ">="
    elif op == "less_than":
        ok = obs_num < thr_num
        sym = "<"
    elif op == "less_than_or_equal":
        ok = obs_num <= thr_num
        sym = "<="
    else:
        ok = obs_num >= thr_num
        sym = ">="
    return ok, f"value {obs_num} {sym} threshold {thr_num}"


def _should_apply_rule(rule: dict[str, Any], source_type: str, input_context: str) -> bool:
    if not rule.get("enabled"):
        return False
    rule_source = (rule.get("source_type") or "checkin").lower()
    if input_context == "sweep":
        return rule_source in {"system", "sweep", "checkin"} and (
            rule.get("input_type") == "checkin_gap_hours"
        )
    if input_context == "checkin":
        # check-in gap is a staleness rule evaluated by sweep, not per check-in
        if (rule.get("input_type") or "") == "checkin_gap_hours":
            return False
        return rule_source == "checkin"
    if input_context == "observation":
        return rule_source == "observation"
    return rule_source == source_type


def _emit_alert(
    store: Store,
    *,
    patient: dict[str, Any],
    rule: dict[str, Any],
    title: str,
    rationale: str,
    checkin_id: str | None,
    evidence_id: str | None,
    now: str,
    source_type: str = "checkin",
    source_id: str | None = None,
    input_event_id: str | None = None,
    matched_condition: str = "",
    observed_value: Any = None,
    evaluation_id: str | None = None,
    deduplicated: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    twin = store.get_twin(patient["id"])
    assert twin is not None
    existing = store.unresolved_alert_for_rule(patient["id"], rule["code"])
    if existing:
        store.create_event(
            {
                "id": new_id("evt"),
                "patient_id": patient["id"],
                "twin_id": twin["id"],
                "event_type": "alert_deduplicated",
                "occurred_at": now,
                "recorded_at": now,
                "actor_user_id": None,
                "actor_name": "Deterministic monitoring engine",
                "actor_role": "system",
                "source_type": "monitoring_rule",
                "evidence_id": evidence_id,
                "verification_status": "awaiting_review",
                "title": "Repeated rule match linked to an existing alert",
                "description": (
                    f"A new observation still met the {rule['code']} rule. "
                    f"The existing {existing['status']} alert remains active; "
                    "no duplicate alert was created."
                ),
                "payload_json": json.dumps(
                    {
                        "ruleId": rule["id"],
                        "ruleCode": rule["code"],
                        "existingAlertId": existing["id"],
                        "existingAlertStatus": existing["status"],
                        "checkinId": checkin_id,
                        "sourceId": source_id,
                        "evaluationId": evaluation_id,
                    },
                    separators=(",", ":"),
                    default=str,
                ),
                "review_status": "pending",
                "created_at": now,
            }
        )
        store.create_audit(
            {
                "id": new_id("aud"),
                "patient_id": patient["id"],
                "actor_user_id": None,
                "actor_name": "Deterministic monitoring engine",
                "actor_role": "system",
                "action": "safety_alert.deduplicated",
                "entity_type": "safety_alert",
                "entity_id": existing["id"],
                "outcome": "allowed",
                "details_json": json.dumps(
                    {
                        "ruleCode": rule["code"],
                        "checkinId": checkin_id,
                        "sourceId": source_id,
                        "evidenceId": evidence_id,
                    },
                    separators=(",", ":"),
                    default=str,
                ),
                "created_at": now,
            }
        )
        if deduplicated is not None:
            deduplicated.append(existing)
        return None

    alert = {
        "id": new_id("alr"),
        "patient_id": patient["id"],
        "checkin_id": checkin_id,
        "rule_id": rule["id"],
        "rule_version": rule.get("version", 1),
        "evaluation_id": evaluation_id,
        "input_event_id": input_event_id,
        "matched_condition": matched_condition[:500] if matched_condition else "",
        "review_status": "pending",
        "source_type": source_type,
        "source_id": source_id or checkin_id,
        "severity": rule.get("severity", "moderate"),
        "category": rule.get("code") or rule.get("name") or "monitoring_rule",
        "title": title,
        "rationale": rationale,
        "status": "open",
        "evidence_id": evidence_id,
        "created_at": now,
        "acknowledged_by_user_id": None,
        "acknowledged_by_name": None,
        "acknowledged_at": None,
        "resolution_note": None,
        "resolved_by_user_id": None,
        "resolved_by_name": None,
        "resolved_at": None,
    }
    store.create_alert(alert)
    store.create_event(
        {
            "id": new_id("evt"),
            "patient_id": patient["id"],
            "twin_id": twin["id"],
            "event_type": "safety_alert_raised",
            "occurred_at": now,
            "recorded_at": now,
            "actor_user_id": None,
            "actor_name": "Deterministic monitoring rule",
            "actor_role": "system",
            "source_type": "monitoring_rule",
            "evidence_id": evidence_id,
            "verification_status": "awaiting_review",
            "title": title,
            "description": rationale,
            "payload_json": json.dumps(
                {
                    "ruleId": rule["id"],
                    "ruleCode": rule.get("code"),
                    "ruleVersion": rule.get("version", 1),
                    "threshold": rule.get("threshold"),
                    "operator": rule.get("operator"),
                    "inputType": rule.get("input_type"),
                    "inputKey": rule.get("input_key"),
                    "observedValue": observed_value,
                    "matchedCondition": matched_condition,
                    "severity": rule.get("severity"),
                    "checkinId": checkin_id,
                    "sourceId": source_id,
                    "evaluationId": evaluation_id,
                },
                separators=(",", ":"),
                default=str,
            ),
            "review_status": "pending",
            "created_at": now,
        }
    )
    store.create_audit(
        {
            "id": new_id("aud"),
            "patient_id": patient["id"],
            "actor_user_id": None,
            "actor_name": "Deterministic monitoring engine",
            "actor_role": "system",
            "action": "safety_alert.created",
            "entity_type": "safety_alert",
            "entity_id": alert["id"],
            "outcome": "allowed",
            "details_json": json.dumps(
                {
                    "ruleCode": rule.get("code"),
                    "severity": rule.get("severity"),
                    "sourceId": source_id,
                },
                separators=(",", ":"),
                default=str,
            ),
            "created_at": now,
        }
    )
    return alert


def _default_rationale(rule: dict[str, Any], observed: Any, condition: str, source_label: str) -> tuple[str, str]:
    code = rule.get("code") or ""
    name = rule.get("name") or "Monitoring rule"
    sev = rule.get("severity") or "moderate"
    # preserve known titles/rationales for existing seeded rules to keep behavior stable
    if code == "chest_pain_severity":
        return (
            "Chest pain reported above configured threshold",
            f"Reported chest pain severity {observed}/10 meets the clinician-configured threshold of {float(rule.get('threshold', 0)):.0f}/10. This is a deterministic rule-based flag, not a diagnosis.",
        )
    if code == "breathlessness_severity":
        return (
            "Breathlessness reported above configured threshold",
            f"Reported breathlessness severity {observed}/10 meets the clinician-configured threshold of {float(rule.get('threshold', 0)):.0f}/10. This is a deterministic rule-based flag, not a diagnosis.",
        )
    if code == "fever_threshold":
        val = float(observed) if observed is not None else 0.0
        return (
            "Temperature at or above configured fever threshold",
            f"Recorded temperature {val:.1f}°C meets the clinician-configured threshold of {float(rule.get('threshold', 0)):.1f}°C. This is a deterministic rule-based flag, not a diagnosis.",
        )
    if code == "adherence_gap":
        return (
            "Medication adherence gap reported",
            f"The patient reported {observed} missed dose(s), meeting the clinician-configured threshold of {float(rule.get('threshold', 0)):.0f}. This flag supports review; it does not recommend a medication change.",
        )
    if code == "pain_escalation":
        return (
            "Pain score increased from the prior check-in",
            f"Pain increased by {observed} points from the prior check-in, meeting the configured increase threshold of {float(rule.get('threshold', 0)):.0f} points. This is a rule-based trend flag.",
        )
    if code == "checkin_gap":
        gap = float(observed) if observed is not None else 0.0
        return (
            "Patient check-in is overdue",
            f"The latest check-in is {gap:.1f} hours old, meeting the clinician-configured {float(rule.get('threshold', 0)):.0f}-hour monitoring threshold. No symptom conclusion is drawn from missing data.",
        )
    title = f"{name} triggered"
    rationale = (
        f"Deterministic rule '{name}' matched for {source_label}: {condition}. "
        f"Observed value: {observed!r}. Severity: {sev}. This is a rule-based flag for human review, not a diagnosis."
    )
    return title, rationale


def _record_evaluation(
    store: Store,
    *,
    patient_id: str,
    twin_id: str | None,
    rule: dict[str, Any],
    source_type: str,
    source_id: str,
    event_id: str | None,
    observed: Any,
    matched: bool,
    explanation: str,
    evaluated_at: str,
) -> str:
    evaluation_id = new_id("evl")
    try:
        store._insert(  # type: ignore[attr-defined]
            "monitoring_evaluations",
            {
                "id": evaluation_id,
                "patient_id": patient_id,
                "twin_id": twin_id,
                "rule_id": rule["id"],
                "rule_code": rule.get("code") or "",
                "rule_version": rule.get("version", 1),
                "source_type": source_type,
                "source_id": source_id,
                "event_id": event_id,
                "input_type": rule.get("input_type") or "",
                "input_key": rule.get("input_key") or "",
                "observed_value_json": json.dumps(observed, separators=(",", ":"), default=str),
                "operator": rule.get("operator") or "",
                "threshold_json": json.dumps(
                    {
                        "threshold": rule.get("threshold"),
                        "comparisonValue": rule.get("comparison_value"),
                    },
                    separators=(",", ":"),
                    default=str,
                ),
                "matched": 1 if matched else 0,
                "severity": rule.get("severity") or "moderate",
                "explanation": explanation[:2000],
                "evaluated_at": evaluated_at,
                "created_at": evaluated_at,
            },
        )
    except Exception:
        evaluation_id = ""
    return evaluation_id


def evaluate_checkin(
    store: Store,
    *,
    patient: dict[str, Any],
    checkin: dict[str, Any],
    prior_checkin: dict[str, Any] | None,
    evidence_id: str | None,
    event_id: str | None = None,
    now: str | None = None,
    deduplicated: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    now_iso = now or iso()
    now_dt = _now_dt(now_iso)
    twin = store.get_twin(patient["id"])
    twin_id = twin["id"] if twin else None
    created: list[dict[str, Any]] = []
    source_id = checkin.get("id")

    for rule in _rule_rows(store, patient["id"]):
        if not _should_apply_rule(rule, "checkin", "checkin"):
            continue
        if rule.get("code") == "pain_escalation" and (checkin.get("pain_score") or 0) < 6:
            continue

        observed = _value_for_checkin(
            input_type=rule.get("input_type") or "",
            input_key=rule.get("input_key") or "",
            checkin=checkin,
            prior_checkin=prior_checkin,
            now=now_dt,
        )
        matched, condition = _matches(
            rule.get("operator") or "greater_than_or_equal",
            observed,
            rule.get("threshold"),
            rule.get("comparison_value"),
        )
        evaluation_id = _record_evaluation(
            store,
            patient_id=patient["id"],
            twin_id=twin_id,
            rule=rule,
            source_type="checkin",
            source_id=source_id or "",
            event_id=event_id,
            observed=observed,
            matched=matched,
            explanation=condition,
            evaluated_at=now_iso,
        )
        if not matched:
            continue
        title, rationale = _default_rationale(rule, observed, condition, "patient check-in")
        alert = _emit_alert(
            store,
            patient=patient,
            rule=rule,
            title=title,
            rationale=rationale,
            checkin_id=source_id,
            evidence_id=evidence_id,
            now=now_iso,
            source_type="checkin",
            source_id=source_id,
            input_event_id=event_id,
            matched_condition=condition,
            observed_value=observed,
            evaluation_id=evaluation_id or None,
            deduplicated=deduplicated,
        )
        if alert is not None:
            created.append(alert)
    return created


def evaluate_observation(
    store: Store,
    *,
    patient: dict[str, Any],
    observation: dict[str, Any],
    evidence_id: str | None,
    event_id: str | None = None,
    now: str | None = None,
    deduplicated: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    now_iso = now or iso()
    now_dt = _now_dt(now_iso)
    twin = store.get_twin(patient["id"])
    twin_id = twin["id"] if twin else None
    created: list[dict[str, Any]] = []
    source_id = observation.get("id")

    for rule in _rule_rows(store, patient["id"]):
        if not _should_apply_rule(rule, "observation", "observation"):
            continue
        observed = _value_for_checkin(
            input_type=rule.get("input_type") or "",
            input_key=rule.get("input_key") or "",
            checkin=observation,
            prior_checkin=None,
            now=now_dt,
        )
        matched, condition = _matches(
            rule.get("operator") or "greater_than_or_equal",
            observed,
            rule.get("threshold"),
            rule.get("comparison_value"),
        )
        evaluation_id = _record_evaluation(
            store,
            patient_id=patient["id"],
            twin_id=twin_id,
            rule=rule,
            source_type="observation",
            source_id=source_id or "",
            event_id=event_id,
            observed=observed,
            matched=matched,
            explanation=condition,
            evaluated_at=now_iso,
        )
        if not matched:
            continue
        title, rationale = _default_rationale(rule, observed, condition, "caregiver observation")
        alert = _emit_alert(
            store,
            patient=patient,
            rule=rule,
            title=title,
            rationale=rationale,
            checkin_id=None,
            evidence_id=evidence_id,
            now=now_iso,
            source_type="observation",
            source_id=source_id,
            input_event_id=event_id,
            matched_condition=condition,
            observed_value=observed,
            evaluation_id=evaluation_id or None,
            deduplicated=deduplicated,
        )
        if alert is not None:
            created.append(alert)
    return created


def run_monitoring_sweep(
    store: Store, *, patient: dict[str, Any], clinician: dict[str, Any]
) -> dict[str, Any]:
    now_dt = utc_now()
    now_iso = iso(now_dt)
    rules = _rule_rows(store, patient["id"])
    created: list[dict[str, Any]] = []
    checkins = store.list_checkins(patient["id"], limit=1)
    latest = checkins[0] if checkins else None
    gap_hours: float | None = None

    if latest:
        gap_hours = max(
            0.0,
            (now_dt - parse_iso(latest["submitted_at"])).total_seconds() / 3600,
        )
        evidence_id = latest.get("evidence_id")
    else:
        discharged = parse_iso(f"{patient['discharged_on']}T09:00:00+00:00")
        gap_hours = max(0.0, (now_dt - discharged).total_seconds() / 3600)
        evidence = next(
            (
                item
                for item in store.list_evidence(patient["id"])
                if item["source_type"] == "discharge_document"
            ),
            None,
        )
        evidence_id = evidence["id"] if evidence else None

    for rule in rules:
        if not _should_apply_rule(rule, "checkin", "sweep"):
            continue
        observed = _value_for_sweep(
            input_type=rule.get("input_type") or "",
            input_key=rule.get("input_key") or "",
            patient=patient,
            latest_checkin=latest,
            now=now_dt,
        )
        if observed is None and (
            rule.get("code") == "checkin_gap" or rule.get("input_type") == "checkin_gap_hours"
        ):
            observed = gap_hours
        matched, condition = _matches(
            rule.get("operator") or "greater_than_or_equal",
            observed,
            rule.get("threshold"),
            rule.get("comparison_value"),
        )
        evaluation_id = _record_evaluation(
            store,
            patient_id=patient["id"],
            twin_id=(store.get_twin(patient["id"]) or {}).get("id"),
            rule=rule,
            source_type="sweep",
            source_id=patient["id"],
            event_id=None,
            observed=observed,
            matched=matched,
            explanation=condition,
            evaluated_at=now_iso,
        )
        if not matched:
            continue
        title, rationale = _default_rationale(rule, observed, condition, "monitoring sweep")
        alert = _emit_alert(
            store,
            patient=patient,
            rule=rule,
            title=title,
            rationale=rationale,
            checkin_id=None,
            evidence_id=evidence_id,
            now=now_iso,
            source_type="sweep",
            source_id=patient["id"],
            matched_condition=condition,
            observed_value=observed,
            evaluation_id=evaluation_id or None,
        )
        if alert is not None:
            created.append(alert)

    twin = store.get_twin(patient["id"])
    if twin:
        store.create_event(
            {
                "id": new_id("evt"),
                "patient_id": patient["id"],
                "twin_id": twin["id"],
                "event_type": "monitoring_sweep_completed",
                "occurred_at": now_iso,
                "recorded_at": now_iso,
                "actor_user_id": clinician["id"],
                "actor_name": clinician["name"],
                "actor_role": clinician["role"],
                "source_type": "clinician_note",
                "evidence_id": None,
                "verification_status": "clinician_verified",
                "title": "Deterministic monitoring sweep",
                "description": (
                    f"{len(rules)} rule(s) evaluated; {len(created)} new alert(s) created."
                ),
                "payload_json": json.dumps(
                    {
                        "rulesEvaluated": len(rules),
                        "alertsCreated": len(created),
                        "checkinGapHours": round(gap_hours, 1) if gap_hours is not None else None,
                    },
                    separators=(",", ":"),
                ),
                "review_status": "not_required",
                "created_at": now_iso,
            }
        )

    store.create_audit(
        {
            "id": new_id("aud"),
            "patient_id": patient["id"],
            "actor_user_id": clinician["id"],
            "actor_name": clinician["name"],
            "actor_role": clinician["role"],
            "action": "monitoring_sweep.completed",
            "entity_type": "patient",
            "entity_id": patient["id"],
            "outcome": "allowed",
            "details_json": json.dumps(
                {"alertsCreated": len(created), "rulesEvaluated": len(rules)},
                separators=(",", ":"),
            ),
            "created_at": now_iso,
        }
    )

    return {
        "evaluatedAt": now_iso,
        "alertsCreated": created,
        "rulesEvaluated": len(rules),
        "checkinGapHours": round(gap_hours, 1) if gap_hours is not None else None,
        "message": (
            "Monitoring sweep completed. Alerts are rule-based and require human review."
            if created
            else "Monitoring sweep completed. No new deterministic rule alerts were created."
        ),
    }
