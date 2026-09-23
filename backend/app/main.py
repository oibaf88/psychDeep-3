import logging
import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import models_vnext as _models_vnext  # noqa: F401 - register canonical metadata
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import (
    admin_users,
    assignments,
    audit,
    auth,
    chat,
    checkins,
    consents,
    diary,
    facts,
    llm_settings,
    mobile,
    notifications,
    professional,
    safety,
    timeline,
    vnext,
)
from app.services.model_gateway import ModelUnavailable, get_model_gateway
from app.services.risk_engine import MODEL_VERSION as RISK_ENGINE_VERSION

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("psychapp")

settings = get_settings()

app = FastAPI(
    title="PsychDeep vNext API",
    description=(
        "Cloud-first longitudinal self-regulation platform. Clinical state and "
        "deterministic safety remain independent of the replaceable LLM deployment."
    ),
    version="0.3.1-vnext",
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
_cors_kwargs: dict = {
    "allow_origins": origins or ["http://localhost:5173"],
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": ["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
}
if settings.app_env in ("local", "dev", "development"):
    _cors_kwargs["allow_origin_regex"] = (
        r"^https?://("
        r"localhost|127\.0\.0\.1|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
        r")(:\d+)?$"
    )
app.add_middleware(CORSMiddleware, **_cors_kwargs)


def _wait_for_db(max_attempts: int = 30, delay_seconds: float = 2.0) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection established.")
            return
        except OperationalError:
            logger.info("Database not ready yet (attempt %s/%s), retrying...", attempt, max_attempts)
            time.sleep(delay_seconds)
    raise RuntimeError("Could not connect to the database after multiple attempts.")


def _verify_production_schema() -> None:
    """Fail before serving if required legacy/vNext migrations or hardening are incomplete."""
    required_columns = {
        # Legacy longitudinal memory remains part of the supported product and
        # must still exist after the vNext expand-and-migrate cutover.
        ("patient_profiles", "id"),
        ("agent2_analysis_traces", "id"),
        ("alfa_signals", "agent2_trace_id"),
        ("risk_assessments", "correlation_id"),
        ("risk_assessments", "calculation_trace"),
        ("risk_assessments", "rule_set_version"),
        ("users", "auth_version"),
        # Canonical vNext model.
        ("observations", "id"),
        ("baseline_versions", "id"),
        ("change_signals", "id"),
        ("inferences", "id"),
        ("model_runs", "id"),
        ("intervention_events", "id"),
        ("model_deployments", "alias"),
    }
    canonical_tables = {
        "observations",
        "feature_definitions",
        "feature_values",
        "baseline_versions",
        "change_signals",
        "model_runs",
        "inferences",
        "intervention_events",
        "knowledge_items",
        "fine_tune_runs",
        "model_deployments",
    }
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema()"
            )
        ).all()
        # Fetch the schema catalogue once and filter in Python. Avoid binding a
        # Python list to PostgreSQL ANY(), whose adaptation varies by driver.
        hardened = conn.execute(
            text(
                "SELECT relation.relname, owner_role.rolname, relation.relrowsecurity, relation.relforcerowsecurity "
                "FROM pg_class relation "
                "JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace "
                "JOIN pg_roles owner_role ON owner_role.oid = relation.relowner "
                "WHERE namespace.nspname = current_schema() AND relation.relkind = 'r'"
            )
        ).all()
        policies = conn.execute(
            text(
                "SELECT tablename, roles FROM pg_policies "
                "WHERE schemaname = current_schema() AND policyname = 'backend_full_access'"
            )
        ).all()

    available = {(row[0], row[1]) for row in rows}
    missing = sorted(required_columns - available)
    if missing:
        raise RuntimeError(
            "Production schema is missing a required migration: "
            + ", ".join(f"{table}.{column}" for table, column in missing)
        )

    hardening_by_table = {row[0]: tuple(row[1:]) for row in hardened if row[0] in canonical_tables}
    bad_hardening = sorted(
        table
        for table in canonical_tables
        if hardening_by_table.get(table) != ("psychdeep_backend", True, True)
    )
    if bad_hardening:
        raise RuntimeError("vNext canonical RLS hardening incomplete: " + ", ".join(bad_hardening))

    policy_tables = {
        row[0]
        for row in policies
        if row[0] in canonical_tables and "psychdeep_backend" in (row[1] or [])
    }
    missing_policies = sorted(canonical_tables - policy_tables)
    if missing_policies:
        raise RuntimeError("vNext backend RLS policies missing: " + ", ".join(missing_policies))


@app.on_event("startup")
def on_startup():
    _wait_for_db()
    if settings.is_production:
        _verify_production_schema()
        logger.info("Production vNext database migration contract verified.")
    else:
        # Development/test convenience only. Product documentation does not
        # support a second local clinical database or bidirectional sync.
        Base.metadata.create_all(bind=engine)
        logger.info("Development database schema ensured.")

    from app.maintenance.refresh_risk_v14 import run_configured_startup_refresh

    run_configured_startup_refresh()

    from app.services.agent2_trace import mark_stale_started_as_abandoned

    db = SessionLocal()
    try:
        abandoned = mark_stale_started_as_abandoned(db)
        if abandoned:
            logger.warning("Marked %s interrupted analysis trace(s) as abandoned.", abandoned)
    finally:
        db.close()

    if settings.seed_demo_data:
        from app.seed import seed_demo_data

        db = SessionLocal()
        try:
            seed_demo_data(db)
        finally:
            db.close()

    try:
        deployment = get_model_gateway().deployment()
        if not deployment.configured:
            logger.warning(
                "Selected model deployment %s is not configured. Core data and deterministic safety remain available.",
                deployment.alias,
            )
    except ModelUnavailable as exc:
        logger.warning("Model deployment configuration rejected safely: %s", exc)


@app.get("/api/v1/health")
def health():
    try:
        deployment = get_model_gateway().deployment()
        model = {
            "deployment_alias": deployment.alias,
            "configured": deployment.configured,
            "policy_version": deployment.policy_version,
        }
    except ModelUnavailable:
        model = {"deployment_alias": None, "configured": False, "policy_version": settings.model_policy_version}
    return {
        "status": "ok",
        "architecture": "cloud-first-vnext",
        "clinical_source_of_truth": "cloud",
        "model": model,
        "risk_engine_version": RISK_ENGINE_VERSION,
        "risk_explanation_schema": "risk-explanation-v1",
        "release": (os.getenv("RENDER_GIT_COMMIT") or os.getenv("APP_RELEASE") or "local")[:64],
    }


app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(consents.router)
app.include_router(checkins.router)
app.include_router(diary.router)
app.include_router(timeline.router)
app.include_router(chat.router)
app.include_router(safety.router)
app.include_router(facts.router)
app.include_router(assignments.router)
app.include_router(professional.router)
app.include_router(notifications.router)
app.include_router(audit.router)
app.include_router(llm_settings.router)
app.include_router(mobile.router)
app.include_router(vnext.router)
