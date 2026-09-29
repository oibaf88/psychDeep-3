"""SQLAlchemy mappings for PsychDeep vNext canonical expand-only tables."""
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JSON_DOC = JSON().with_variant(JSONB, "postgresql")


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSON_DOC, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(48))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    timezone: Mapped[str | None] = mapped_column(String(64))
    quality: Mapped[dict] = mapped_column(JSON_DOC, nullable=False, default=dict)
    consent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user_consents.id", ondelete="SET NULL"))
    legacy_source_table: Mapped[str | None] = mapped_column(String(64))
    legacy_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    legacy_source_field: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FeatureDefinition(Base):
    __tablename__ = "feature_definitions"

    id: Mapped[uuid.UUID] = uuid_pk()
    feature_key: Mapped[str] = mapped_column(String(96), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(48))
    window_spec: Mapped[dict] = mapped_column(JSON_DOC, nullable=False, default=dict)
    missingness_policy: Mapped[str] = mapped_column(Text, nullable=False)
    valid_range: Mapped[dict | None] = mapped_column(JSON_DOC)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FeatureValue(Base):
    __tablename__ = "feature_values"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_key: Mapped[str] = mapped_column(String(96), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict] = mapped_column(JSON_DOC, nullable=False)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observation_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    quality_flags: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BaselineVersion(Base):
    __tablename__ = "baseline_versions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_key: Mapped[str | None] = mapped_column(String(96))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stats: Mapped[dict] = mapped_column(JSON_DOC, nullable=False)
    exclusions: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    stability: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    data_coverage: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="provisional")
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_baseline_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChangeSignal(Base):
    __tablename__ = "change_signals"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String(96), nullable=False)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_value: Mapped[float | None] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(32), nullable=False)
    uncertainty: Mapped[dict] = mapped_column(JSON_DOC, nullable=False, default=dict)
    evidence_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    contradictions: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    baseline_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("baseline_versions.id", ondelete="SET NULL"))
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Inference(Base):
    __tablename__ = "inferences"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(96), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_DOC, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    contradictions: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    uncertainty: Mapped[dict] = mapped_column(JSON_DOC, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    legacy_signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class InterventionEvent(Base):
    __tablename__ = "intervention_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_id: Mapped[str] = mapped_column(String(96), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    authority: Mapped[str] = mapped_column(String(48), nullable=False)
    burden: Mapped[str | None] = mapped_column(String(24))
    usefulness: Mapped[int | None] = mapped_column(SmallInteger)
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class KnowledgeItem(Base):
    """Versioned, curated content registry; not yet wired into model prompts."""

    __tablename__ = "knowledge_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    topic: Mapped[str] = mapped_column(String(96), nullable=False)
    population: Mapped[str] = mapped_column(String(96), nullable=False)
    objective: Mapped[str] = mapped_column(String(128), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="es-ES")
    evidence_level: Mapped[str] = mapped_column(String(48), nullable=False)
    contraindications: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_version: Mapped[str] = mapped_column(String(64), nullable=False)
    review_due: Mapped[date | None] = mapped_column(Date)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    purpose: Mapped[str] = mapped_column(String(96), nullable=False)
    audience: Mapped[str] = mapped_column(String(32), nullable=False)
    deployment_alias: Mapped[str] = mapped_column(String(96), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(48), nullable=False)
    model_id: Mapped[str] = mapped_column(String(192), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(192))
    prompt_version: Mapped[str | None] = mapped_column(String(96))
    policy_version: Mapped[str] = mapped_column(String(96), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_schema: Mapped[str | None] = mapped_column(String(96))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MobileInferenceEvent(Base):
    __tablename__ = "mobile_inference_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    deployment_alias: Mapped[str] = mapped_column(String(96), nullable=False, default="mobile-local")
    model_id: Mapped[str] = mapped_column(String(192), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(192))
    prompt_version: Mapped[str | None] = mapped_column(String(96))
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output: Mapped[dict] = mapped_column(JSON_DOC, nullable=False)
    output_schema: Mapped[str | None] = mapped_column(String(96))
    client_platform: Mapped[str] = mapped_column(String(32), nullable=False, default="android")
    client_app_version: Mapped[str | None] = mapped_column(String(64))
    inference_engine: Mapped[str | None] = mapped_column(String(64))
    client_model_checksum: Mapped[str | None] = mapped_column(String(128))
    client_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
