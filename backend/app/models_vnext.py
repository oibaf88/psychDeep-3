"""SQLAlchemy mappings for psychDeep-vOG canonical expand-only tables."""
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, SmallInteger, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import uuid_pk

JSON_DOC = JSON().with_variant(JSONB, "postgresql")


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
    """Versioned curated content. Active, unexpired rows are copied into Agent 1 context."""

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
    # Server defaults are read back lazily (on refresh/access), not through
    # INSERT ... RETURNING, so an insert that does not set the output
    # validation columns never names them (see below).
    __mapper_args__ = {"eager_defaults": False}

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
    # Output validation (G3), migration 20261017090000. Rule codes only,
    # never patient or model text. Nullable, deferred and with a NULL server
    # default so that ModelGateway inserts and ordinary reads, which never
    # set these, do not name the columns at all: an app release that lands
    # before the migration keeps writing its other ModelRun rows.
    output_validator_version: Mapped[str | None] = mapped_column(
        String(64), deferred=True, server_default=text("NULL")
    )
    output_violation_codes: Mapped[list | None] = mapped_column(
        JSON_DOC, deferred=True, server_default=text("NULL")
    )
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


class MemoryCommit(Base):
    """One archive of a chat or diary span. Content rows point here. Nothing is rewritten."""

    __tablename__ = "memory_commits"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    archive_abstract: Mapped[str] = mapped_column(Text, nullable=False, default="")
    archive_overview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_ids: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    diff: Mapped[dict] = mapped_column(JSON_DOC, nullable=False, default=dict)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    prompt_version: Mapped[str] = mapped_column(String(96), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(96), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DiscourseFact(Base):
    """The conversation happened. The quote is the stored text, not a claim about the world."""

    __tablename__ = "discourse_facts"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    spoken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    manner: Mapped[dict] = mapped_column(JSON_DOC, nullable=False, default=dict)
    chat_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="SET NULL"))
    diary_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("diary_entries.id", ondelete="SET NULL"))
    memory_commit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_commits.id", ondelete="SET NULL"))
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PsychReading(Base):
    """Uncertain reading of why the person spoke this way. Not a diagnosis and not an alert."""

    __tablename__ = "psych_readings"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainty: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("psych_readings.id", ondelete="SET NULL"))
    memory_commit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_commits.id", ondelete="SET NULL"))
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FormulationVersion(Base):
    """Versioned longitudinal formulation. The previous version stays."""

    __tablename__ = "formulation_versions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    l0: Mapped[str] = mapped_column(Text, nullable=False)
    l1: Mapped[str] = mapped_column(Text, nullable=False)
    l2: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("formulation_versions.id", ondelete="SET NULL"))
    prompt_version: Mapped[str] = mapped_column(String(96), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(96), nullable=False)
    memory_commit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_commits.id", ondelete="SET NULL"))
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    acute_episode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MemoryAnnotation(Base):
    """Professional note. It explains a memory row and does not replace it."""

    __tablename__ = "memory_annotations"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClinicalAttentionNotice(Base):
    """A request that a human look. Separate from ProfessionalAlert and alert_level."""

    __tablename__ = "clinical_attention_notices"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence_refs: Mapped[dict] = mapped_column(JSON_DOC, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MemoryEmbedding(Base):
    """Optional vector from the already selected OpenAI-compatible deployment."""

    __tablename__ = "memory_embeddings"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    embedding: Mapped[list | None] = mapped_column(JSON_DOC)
    provider: Mapped[str] = mapped_column(String(96), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(192), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MemoryEpisode(Base):
    """Derived episode; the literal source messages remain in their canonical tables."""

    __tablename__ = "memory_episodes"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_key: Mapped[str] = mapped_column(String(192), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    l0: Mapped[str] = mapped_column(Text, nullable=False, default="")
    l1: Mapped[str] = mapped_column(Text, nullable=False, default="")
    l2: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    themes: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    transitions: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    uncertainty: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_episodes.id", ondelete="SET NULL"))
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    prompt_version: Mapped[str] = mapped_column(String(96), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MemoryRelation(Base):
    """Evidence-linked relationship between derived memories, not a causal assertion."""

    __tablename__ = "memory_relations"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    from_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_items.id", ondelete="CASCADE"), nullable=False, index=True)
    to_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_items.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="provisional")
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PatientModelVersion(Base):
    """Versioned whole-person formulation with source coverage and explicit uncertainty."""

    __tablename__ = "patient_model_versions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    model_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_json: Mapped[dict] = mapped_column(JSON_DOC, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    coverage: Mapped[dict] = mapped_column(JSON_DOC, nullable=False, default=dict)
    unresolved_contradictions: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    unanswered_questions: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    source_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_model_versions.id", ondelete="SET NULL"))
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    prompt_version: Mapped[str] = mapped_column(String(96), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="provisional")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PatientClinicalDocument(Base):
    """Private source document uploaded by an assigned therapist for analysis."""

    __tablename__ = "patient_clinical_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(240), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extraction_status: Mapped[str] = mapped_column(String(24), nullable=False, default="text_extracted")
    analysis_status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    error_category: Mapped[str | None] = mapped_column(String(64))
    patient_model_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_model_versions.id", ondelete="SET NULL"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PatientModelQuestion(Base):
    """Non-intrusive follow-up question representing a documented knowledge gap."""

    __tablename__ = "patient_model_questions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_key: Mapped[str] = mapped_column(String(160), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    evidence_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    decline_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_asked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_model_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_model_versions.id", ondelete="SET NULL"))
    resolved_by_source_ref: Mapped[str | None] = mapped_column(String(192))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class MemoryAnalysisRun(Base):
    """Auditable deep analysis result over a fixed, source-referenced evidence set."""

    __tablename__ = "memory_analysis_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_type: Mapped[str] = mapped_column(String(48), nullable=False)
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    question_label: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    result_json: Mapped[dict] = mapped_column(JSON_DOC, nullable=False, default=dict)
    limitations: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    prompt_version: Mapped[str] = mapped_column(String(96), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    estimated_input_tokens: Mapped[int | None] = mapped_column(Integer)
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    error_category: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MemoryItem(Base):
    """Atomic memory claim that always points back to its source evidence."""

    __tablename__ = "memory_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    subject_ref: Mapped[str | None] = mapped_column(String(160))
    perspective: Mapped[str] = mapped_column(String(32), nullable=False, default="user_report")
    attribution: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_key: Mapped[str | None] = mapped_column(String(256), index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[str] = mapped_column(String(16), nullable=False, default="high")
    temporal_scope: Mapped[dict] = mapped_column(JSON_DOC, nullable=False, default=dict)
    source_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_items.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sensitivity: Mapped[str] = mapped_column(String(24), nullable=False, default="clinical")
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MemoryJob(Base):
    """Persistent idempotent work item; workers may retry without repeating writes."""

    __tablename__ = "memory_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_table: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(192), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_category: Mapped[str | None] = mapped_column(String(64))
    output_refs: Mapped[list] = mapped_column(JSON_DOC, nullable=False, default=list)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_runs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
