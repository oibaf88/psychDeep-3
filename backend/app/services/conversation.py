"""
Conversation orchestration: wires Agent 2 (linguistic analysis) -> the
deterministic Risk Engine -> Agent 1 (conversational reply) together,
per the "flujo de respuesta" in doc 20.

Critical safety property, implemented here rather than left to prompting
alone: at alert_level 3 and 4 the server-owned static templates in
app/content/safety_resources.py are ALWAYS appended to the reply, and the
emergency resources are always returned alongside it. The LLM cannot
suppress, rewrite or shorten that block, and if its call fails, times out
or is refused by the safety classifiers, the fixed message is still
returned in full. The crisis path never depends on the LLM succeeding.

What the LLM *may* do at those levels is keep accompanying the person:
Agent 1 still answers with the real conversation history, under the
tightened AGENT1_CRISIS_INSTRUCTION (short, present-focused, one concrete
grounding offer, no resources of its own, no dissuading from calling for
help). Raising an alert and staying present are treated as complementary,
not mutually exclusive -- the alert and the professional notification are
decided beforehand by the deterministic risk engine and are unaffected by
anything the model says.
"""
import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.context_budget import fit_recent_messages

from app.content.prompts import (
    AGENT1_CRISIS_INSTRUCTION,
    AGENT1_CONTEXT_VERSION,
    AGENT1_PROMPT_VERSION,
    AGENT1_SYSTEM_PROMPT,
    ANALYZER_SYSTEM_PROMPT,
    ANALYZER_TOOL_SCHEMA,
)
from app.content.safety_resources import (
    ANALYSIS_RATIONALE_WITHHELD,
    AGENT1_OUTPUT_BLOCKED_MESSAGE,
    CRISIS_RESOURCES,
    LEVEL3_PATIENT_MESSAGE,
    LEVEL3_PATIENT_MESSAGE_WITH_PROFESSIONAL,
    LEVEL4_PATIENT_MESSAGE,
    SAFETY_PROTOCOL_VERSION,
)
from app.models import AlfaSignal, ChatMessage, PatientProfessionalAssignment, User
from app.services import agent1_context, clinical_memory, llm_config, profile as profile_service, psychosocial, risk_engine
from app.services import agent2_trace, audit, output_validation, reply_model_run
from app.services.llm import ChatResult, ProviderMetadata, StructuredAnalysisError, get_llm_provider

logger = logging.getLogger("psychapp.conversation")

MAX_HISTORY_MESSAGES = 12


class LinguisticAnalysis(BaseModel):
    """Strict boundary between untrusted model output and the risk engine."""

    model_config = ConfigDict(extra="forbid", strict=True)

    rumination_score: float = Field(ge=0, le=1)
    negative_valence: float = Field(ge=0, le=1)
    urgency_level: float = Field(ge=0, le=1)
    ideation_indirect: bool
    ideation_direct: bool
    consumption_crisis: bool
    ambivalence: float = Field(ge=0, le=1)
    emotional_complexity: Literal["low", "medium", "high"]
    short_rationale: str = Field(min_length=1, max_length=500)
    # How this reading sits against the patient's own history, as the model
    # judged it. Defaulted rather than required so a provider that has not
    # seen the new schema — or a stored signal written before it existed —
    # still validates: absent means "no comparison was made", which is
    # exactly what those cases mean.
    deviation_from_own_baseline: Literal[
        "unknown", "much_lower", "lower", "typical", "higher", "much_higher"
    ] = "unknown"
    is_typical_for_patient: bool = True


@dataclass(frozen=True)
class AnalysisOutcome:
    correlation_id: uuid.UUID
    trace_id: uuid.UUID | None
    signal_id: uuid.UUID | None
    status: str
    value: dict | None
    # The psychosocial half of the same call. Empty when the text was too
    # short to carry social context, or when only that half failed to
    # validate — which is why it is reported separately from `status`.
    observation_ids: list[uuid.UUID] = field(default_factory=list)
    psychosocial_status: str = "not_attempted"


def analyze_text_and_store(
    db: Session,
    user_id,
    text: str,
    *,
    source_type: str,
    source_id: uuid.UUID,
    correlation_id: uuid.UUID,
    observed_at: datetime | None = None,
    provider_override: str | None = None,
) -> AnalysisOutcome:
    """Analyse one piece of patient text, once, and persist both readings.

    This used to be two provider calls over the same text — Agent 2 for the
    linguistic markers, Agent 4 for the social determinants — each with its
    own trace. They never disagreed about anything, because their schemas
    were disjoint by construction; they simply cost twice. Now one call
    returns both blocks under one trace.

    Never raises to the patient-facing flow. If the trace cannot be
    committed first, no external request is made and the deterministic
    engine proceeds without a fresh signal.
    """
    try:
        trace = agent2_trace.start(
            db,
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            correlation_id=correlation_id,
            agent_role=agent2_trace.ANALYZER_ROLE,
        )
    except agent2_trace.TracePersistenceError:
        logger.error("Analysis skipped because its trace could not be persisted")
        return AnalysisOutcome(correlation_id, None, None, "trace_persistence_error", None)
    except Exception as exc:
        # Resolving the connection can fail before a trace exists. That must
        # not abort the turn: the deterministic risk engine still has to run.
        from app.services.personal_llm import LocalModelUnavailable

        if not isinstance(exc, (LocalModelUnavailable, RuntimeError)):
            raise
        logger.error("Analysis skipped because the inference connection is unavailable: %s", type(exc).__name__)
        return AnalysisOutcome(correlation_id, None, None, "inference_unavailable", None)

    # Who the analyser is reading. Read-only, and read without creating: a
    # patient with no profile is analysed exactly as before this existed.
    patient_profile = profile_service.get(db, user_id)
    system_prompt = ANALYZER_SYSTEM_PROMPT + profile_service.analyzer_context_block(patient_profile)
    system_prompt += clinical_memory.formulation_for_analyzer(db, user_id)

    try:
        provider_result = get_llm_provider(db, provider_override=provider_override).analyze_structured(
            system_prompt,
            text,
            ANALYZER_TOOL_SCHEMA,
        )
        value = provider_result.value
        if not isinstance(value, dict):
            raise ValueError("analyzer returned a non-object")
        result = LinguisticAnalysis.model_validate(value.get("linguistic")).model_dump()
        prose_check = _withhold_unsafe_analysis_prose(result, value)
    except Exception as exc:  # noqa: BLE001
        # Persist only an allow-listed category and class name.  Raw SDK
        # error messages can echo request data and therefore never enter
        # the database or Render logs.
        agent2_trace.mark_failed(db, trace, exc)
        logger.error("Analysis failed safely: %s", type(exc).__name__)
        return AnalysisOutcome(correlation_id, trace.id, None, trace.status, None)

    # The psychosocial half is built separately and is allowed to fail on its
    # own. Losing a linguistic signal because an observation quote came back
    # malformed would trade a safety-critical input for a contextual one.
    rows, psychosocial_status = _psychosocial_rows(
        db,
        trace,
        value.get("psychosocial"),
        user_id=user_id,
        text=text,
        source_type=source_type,
        source_id=source_id,
        correlation_id=correlation_id,
        observed_at=observed_at,
    )

    # Preserve the validated extractor answer even when it yielded no
    # grounded observations. Zero rows alone cannot establish "no content".
    # Failed/skipped blocks, like historic signals without this field, stay
    # unknown. This metadata is descriptive and never a risk-engine input.
    psychosocial_block = value.get("psychosocial")
    psychosocial_content = psychosocial_block.get("has_psychosocial_content") if isinstance(psychosocial_block, dict) else None
    result["has_psychosocial_content"] = (
        psychosocial_content
        if psychosocial_status == "succeeded" and isinstance(psychosocial_content, bool)
        else None
    )

    signal = AlfaSignal(
        user_id=user_id,
        signal_type="linguistic_analysis",
        value=result,
        confidence_band=None,
        agent2_trace_id=trace.id,
    )
    try:
        agent2_trace.mark_succeeded(trace, provider_result.metadata)
        if psychosocial_status == "invalid_block":
            # The call succeeded; one block of it did not. Recorded on the
            # trace rather than in the status, which stays the outcome of
            # the call itself.
            trace.error_code = "psychosocial_block_invalid"
        db.add(trace)
        db.add(signal)
        for row in rows:
            db.add(row)
        db.commit()
        db.refresh(signal)
    except Exception:  # noqa: BLE001
        db.rollback()
        agent2_trace.mark_failed(
            db,
            trace,
            StructuredAnalysisError("provider_error", error_code="result_persistence_failed"),
        )
        logger.error("Analysis result could not be persisted")
        return AnalysisOutcome(correlation_id, trace.id, None, trace.status, None)
    if prose_check.blocked:
        _log_blocked_analysis_prose(
            db,
            user_id,
            prose_check,
            trace=trace,
            source_type=source_type,
            correlation_id=correlation_id,
            metadata=provider_result.metadata,
        )
    # Fold what was learned about the person back in, after the analysis is
    # safely committed. A failure here costs the profile update only; it must
    # never roll back the signal the risk engine is about to read, and it must
    # never raise — this function's whole contract is that the patient-facing
    # flow survives whatever the analytic layer does.
    try:
        profile_service.apply_analyzer_update(db, user_id, value.get("profile_update"))
        profile_service.refresh_linguistic_baseline(db, user_id)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("Profile refresh skipped safely: %s", type(exc).__name__)

    return AnalysisOutcome(
        correlation_id,
        trace.id,
        signal.id,
        "succeeded",
        result,
        observation_ids=[row.id for row in rows],
        psychosocial_status=psychosocial_status,
    )


@dataclass(frozen=True)
class AnalysisProseCheck:
    """Which Agent 2 prose fields were withheld, and by which rules."""

    fields: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return bool(self.fields)


def _withhold_unsafe_analysis_prose(result: dict, value: dict) -> AnalysisProseCheck:
    """Check the analyser's prose fields and withhold the ones that fail.

    Mutates ``result`` and ``value`` in place. A failing
    ``short_rationale`` is replaced by server-owned copy; a failing
    portrait becomes "no change"; if any open thread fails, the whole
    thread list becomes "no change" (the model returns the full list, so
    dropping one item would silently close a thread). Numeric and boolean
    signals are never touched.
    """
    fields: list[str] = []
    violations: list[str] = []

    def _check(name: str, text) -> bool:
        if not isinstance(text, str) or not text.strip():
            return False
        check = output_validation.validate_analysis_prose(text)
        if check.blocked:
            fields.append(name)
            violations.extend(v for v in check.violations if v not in violations)
        return check.blocked

    if _check("short_rationale", result.get("short_rationale")):
        result["short_rationale"] = ANALYSIS_RATIONALE_WITHHELD

    update = value.get("profile_update")
    if isinstance(update, dict):
        if _check("portrait", update.get("portrait")):
            update["portrait"] = ""
        threads = update.get("open_threads")
        if isinstance(threads, list):
            thread_text = " \n".join(
                f"{item.get('topic') or ''}. {item.get('note') or ''}"
                for item in threads
                if isinstance(item, dict)
            )
            if _check("open_threads", thread_text):
                update["open_threads"] = []

    return AnalysisProseCheck(fields=tuple(fields), violations=tuple(violations))


def _log_blocked_analysis_prose(
    db: Session,
    user_id,
    check: AnalysisProseCheck,
    *,
    trace,
    source_type: str,
    correlation_id: uuid.UUID,
    metadata: ProviderMetadata | None,
) -> None:
    """Record withheld analyser prose: field names and rule codes, never text."""
    logger.warning(
        "Analysis prose withheld by %s: fields=%s rules=%s",
        output_validation.ANALYSIS_VALIDATOR_VERSION,
        ",".join(check.fields),
        ",".join(check.violations),
    )
    try:
        audit.log(
            db,
            actor_id=user_id,
            actor_role="system",
            action=output_validation.AUDIT_ACTION,
            entity_type="agent2_analysis_trace",
            entity_id=trace.id,
            extra={
                "validator_version": output_validation.ANALYSIS_VALIDATOR_VERSION,
                "violations": list(check.violations),
                "fields": list(check.fields),
                "audience": "analysis",
                "source_type": source_type,
                "correlation_id": str(correlation_id),
                "provider": getattr(metadata, "provider", None),
                "model": (getattr(metadata, "response_model", None) or getattr(metadata, "requested_model", None)),
            },
        )
    except Exception as exc:  # noqa: BLE001
        # The prose is still withheld; only the audit row is lost.
        logger.error("Could not audit withheld analysis prose: %s", type(exc).__name__)
        db.rollback()


def _psychosocial_rows(
    db: Session,
    trace,
    block,
    *,
    user_id,
    text: str,
    source_type: str,
    source_id: uuid.UUID,
    correlation_id: uuid.UUID,
    observed_at: datetime | None,
):
    """Build the psychosocial rows, or explain why there are none.

    Returns ``(rows, status)``. Never raises: a bad psychosocial block must
    not cost the linguistic signal that came back in the same response.
    """
    if not text or len(text.strip()) < psychosocial.MIN_TEXT_CHARS_FOR_EXTRACTION:
        return [], "skipped_short_text"
    if not isinstance(block, dict):
        logger.warning("Analyzer returned no usable psychosocial block")
        return [], "invalid_block"
    try:
        rows = psychosocial.build_observation_rows(
            block,
            user_id=user_id,
            text=text,
            source_type=source_type,
            source_id=source_id,
            correlation_id=correlation_id,
            trace_id=trace.id,
            observed_at=observed_at,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Psychosocial block rejected (%s); linguistic half kept", type(exc).__name__)
        return [], "invalid_block"
    return rows, "succeeded"


def _has_active_professional(db: Session, user_id) -> bool:
    return (
        db.query(PatientProfessionalAssignment)
        .filter(PatientProfessionalAssignment.patient_id == user_id, PatientProfessionalAssignment.status == "active")
        .count()
        > 0
    )


def _recent_messages(db: Session, user_id) -> list[dict[str, str]]:
    """Return only recent turns that fit the configured token budget.

    Stored history is never deleted. The LLM sees a bounded working window,
    with the newest user turn having priority when the budget is tight.
    """
    settings = get_settings()
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(max(MAX_HISTORY_MESSAGES, settings.conversation_max_history_messages))
        .all()
    )
    messages = [
        {"role": m.role, "content": m.content}
        for m in reversed(history)
        if m.role in ("user", "assistant")
    ]
    result = fit_recent_messages(
        messages,
        settings.conversation_history_budget_tokens,
        max_messages=settings.conversation_max_history_messages,
    )
    if result.truncated:
        logger.info(
            "Conversation history bounded: estimated_tokens=%s budget=%s messages=%s",
            result.estimated_tokens,
            settings.conversation_history_budget_tokens,
            len(result.messages),
        )
    return result.messages


def _reply_provenance(
    db: Session,
    *,
    from_model: bool,
    metadata: ProviderMetadata | None = None,
    system_instruction: str | None = None,
    context_block: str | None = None,
) -> dict:
    """Which model produced an assistant turn, for the stored message.

    A turn built entirely from the server-owned safety templates has no
    model behind it, and says so by storing nothing — that distinction is
    exactly what someone re-reading a crisis conversation needs.

    Prefers the metadata the call itself came back with: that names the
    model the server said answered, where re-resolving the configuration
    only names the model the app would ask for now. On a local runtime
    those differ whenever the loaded weights are not the configured ones.
    """
    if not from_model:
        return {}
    contract = {}
    if system_instruction is not None and context_block is not None:
        contract = {
            "prompt_version": AGENT1_PROMPT_VERSION,
            "prompt_sha256": hashlib.sha256(system_instruction.encode("utf-8")).hexdigest(),
            "context_version": AGENT1_CONTEXT_VERSION,
            "context_sha256": hashlib.sha256(context_block.encode("utf-8")).hexdigest(),
        }
    if metadata is not None:
        return {
            "provider": metadata.provider,
            "model": metadata.response_model or metadata.requested_model,
            "provider_base_url": metadata.base_url,
            **contract,
        }
    active = llm_config.resolve(db)
    return {
        "provider": active.provider,
        "model": active.chat_model,
        "provider_base_url": active.base_url,
        **contract,
    }


def _agent1_crisis_accompaniment(
    db: Session, user_id, system_prompt: str, messages: list[dict[str, str]] | None = None
) -> ChatResult | None:
    """Agent 1's turn during an alert-level 3/4 conversation.

    The model keeps accompanying the person with the real conversation
    history, under a tightened instruction (short, present-focused, one
    concrete grounding offer, no resources of its own). The caller always
    appends the server-owned safety copy afterwards, so this returning
    None -- on a provider error, a refusal, or an empty reply -- costs the
    user nothing but the accompanying sentences.
    """
    try:
        provider = get_llm_provider(db)
        result = provider.chat(
            system_prompt,
            messages if messages is not None else _recent_messages(db, user_id),
            max_tokens=400,
        )
        return result if result.text.strip() else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Agent1 crisis accompaniment failed; using fixed safety copy only: %s", type(exc).__name__)
        return None


def _log_blocked_output(
    db: Session,
    user_id,
    check: "output_validation.OutputValidation",
    *,
    level: int,
    correlation_id: uuid.UUID,
    source_message_id,
    metadata: ProviderMetadata | None,
) -> None:
    """Record that a model reply was withheld: rule codes, never the text."""
    logger.warning(
        "Agent1 output withheld by %s: %s", check.validator_version, ",".join(check.violations)
    )
    try:
        audit.log(
            db,
            actor_id=user_id,
            actor_role="system",
            action=output_validation.AUDIT_ACTION,
            entity_type="chat_message",
            entity_id=source_message_id,
            extra=check.audit_extra(
                alert_level=level,
                correlation_id=str(correlation_id),
                provider=getattr(metadata, "provider", None),
                model=(getattr(metadata, "response_model", None) or getattr(metadata, "requested_model", None)),
            ),
        )
    except Exception as exc:  # noqa: BLE001
        # The reply is still withheld; only the audit row is lost.
        logger.error("Could not audit withheld Agent1 output: %s", type(exc).__name__)
        db.rollback()


def get_reply(
    db: Session,
    user: User,
    user_message: str,
    *,
    provider_override: str | None = None,
) -> dict:
    # 1. Persist the user's message.
    correlation_id = uuid.uuid4()
    source_message = ChatMessage(user_id=user.id, role="user", content=user_message)
    db.add(source_message)
    db.commit()
    db.refresh(source_message)

    # 2. Analyse the free text: linguistic markers and social determinants
    #    in one call, both stored BEFORE the risk engine runs, so a sentence
    #    like "me he ido unos días a casa de un colega" is already on the
    #    record when the level is decided. Failures never reach the patient.
    analysis = analyze_text_and_store(
        db,
        user.id,
        user_message,
        source_type="chat_message",
        source_id=source_message.id,
        correlation_id=correlation_id,
        observed_at=source_message.created_at,
        provider_override=provider_override,
    )

    # 3. Deterministic risk engine: the ONLY place alert_level is decided.
    assessment = risk_engine.run_and_persist(
        db,
        user.id,
        correlation_id=correlation_id,
        agent2_trace_id=analysis.trace_id,
        linguistic_signal_id=analysis.signal_id,
    )
    level = assessment.alert_level

    # 4. Build the reply.
    #
    #    Levels 3/4 keep the conversation open: Agent 1 still answers, with
    #    the real history, under AGENT1_CRISIS_INSTRUCTION. The server-owned
    #    safety copy is then APPENDED, never replaced -- so the fixed
    #    message and the emergency resources are guaranteed to reach the
    #    user whatever the model does, including when it fails or refuses.
    #    Alerting and professional notification are unaffected: they were
    #    already decided in step 3 by the deterministic engine.
    # The context Agent 1 answers with. This used to be the Python repr of
    # the engine's entire input dictionary — thresholds, formulas, z-scores
    # and the patient's own quotes — inside a prompt that forbids revealing
    # any of it. It is now prose containing only what the agent can act on,
    # and it finally includes the two things its own instructions require:
    # the confirmed facts it must not contradict, and whether a safety plan
    # exists to suggest reviewing.
    context_block = agent1_context.build(
        db, user.id, assessment, in_crisis=assessment.alert_level >= 3, query=user_message
    )
    agent1_instruction = AGENT1_SYSTEM_PROMPT + (
        AGENT1_CRISIS_INSTRUCTION if level >= 3 else ""
    )
    agent1_system_prompt = agent1_instruction + "\n\n" + context_block

    # Set by whichever branch actually reached a model, so the stored turn
    # records what answered rather than what the resolver would say now.
    reply_metadata: ProviderMetadata | None = None

    def _record_model_run(db_, user_id_, check_, metadata_, system_prompt_, messages_) -> None:
        """Canonical ModelRun for this validated reply: succeeded or output_withheld."""
        reply_model_run.record_validated_reply(
            db_,
            check=check_,
            metadata=metadata_,
            purpose="agent1_chat",
            audience="patient",
            user_id=user_id_,
            prompt_version=AGENT1_PROMPT_VERSION,
            system_prompt=system_prompt_,
            messages=messages_,
            correlation_id=correlation_id,
        )

    def _checked_accompaniment(db_, user_id_, system_prompt_) -> ChatResult | None:
        """Crisis prose that breaks an output rule is dropped; the fixed copy stays."""
        try:
            messages_ = _recent_messages(db_, user_id_)
        except Exception as exc:  # noqa: BLE001
            # Same outcome as a failed accompaniment: fixed crisis copy only.
            logger.warning("Agent1 crisis history unavailable; using fixed safety copy only: %s", type(exc).__name__)
            return None
        result_ = _agent1_crisis_accompaniment(db_, user_id_, system_prompt_, messages_)
        if result_ is None:
            return None
        check_ = output_validation.validate_agent1_output(result_.text)
        _record_model_run(db_, user_id_, check_, result_.metadata, system_prompt_, messages_)
        if check_.blocked:
            _log_blocked_output(
                db_, user_id_, check_, level=level, correlation_id=correlation_id,
                source_message_id=source_message.id, metadata=result_.metadata,
            )
            return None
        return result_

    if level == 4:
        accompaniment = _checked_accompaniment(db, user.id, agent1_system_prompt)
        prose = accompaniment.text.strip() if accompaniment else ""
        reply_text = (prose + "\n\n" if prose else "") + LEVEL4_PATIENT_MESSAGE
        ui_mode = "crisis"
        resources = CRISIS_RESOURCES
        protocol_version = SAFETY_PROTOCOL_VERSION
        reply_from_model = accompaniment is not None
        reply_metadata = accompaniment.metadata if accompaniment else None
    elif level == 3:
        has_prof = _has_active_professional(db, user.id)
        fixed = LEVEL3_PATIENT_MESSAGE_WITH_PROFESSIONAL if has_prof else LEVEL3_PATIENT_MESSAGE
        accompaniment = _checked_accompaniment(db, user.id, agent1_system_prompt)
        prose = accompaniment.text.strip() if accompaniment else ""
        reply_text = (prose + "\n\n" if prose else "") + fixed
        ui_mode = "support"
        resources = None
        protocol_version = SAFETY_PROTOCOL_VERSION
        reply_from_model = accompaniment is not None
        reply_metadata = accompaniment.metadata if accompaniment else None
    else:
        # Levels 0-2: normal, open conversation via Agent 1, with the risk
        # context injected as READ-ONLY structured context (never the raw
        # number, per doc 8: "Nunca presentes esa información como un
        # diagnóstico").
        messages = _recent_messages(db, user.id)
        failed = False
        try:
            provider = get_llm_provider(db)
            result = provider.chat(agent1_system_prompt, messages)
            reply_metadata = result.metadata
            reply_text = result.text
            check = output_validation.validate_agent1_output(reply_text)
            _record_model_run(db, user.id, check, reply_metadata, agent1_system_prompt, messages)
            if check.blocked:
                _log_blocked_output(
                    db, user.id, check, level=level, correlation_id=correlation_id,
                    source_message_id=source_message.id, metadata=reply_metadata,
                )
                # Deterministic, server-owned support replaces the model text,
                # which is not stored or shown. Not "from the model" any more.
                reply_text = AGENT1_OUTPUT_BLOCKED_MESSAGE
                reply_metadata = None
                failed = True
        except Exception as exc:  # noqa: BLE001
            failed = True
            logger.warning("Agent1 chat failed safely: %s", type(exc).__name__)
            if isinstance(exc, StructuredAnalysisError):
                code = exc.error_code or exc.safe_kind
                messages = {
                    "api_key_not_configured": "La API del proveedor LLM no está configurada en el servidor.",
                    "http_400": "El proveedor rechazó la solicitud (HTTP 400). Revisa el modelo o los parámetros configurados.",
                    "http_401": "El proveedor rechazó la autenticación (HTTP 401). Revisa la clave API del servidor.",
                    "http_403": "El proveedor denegó el acceso (HTTP 403). Revisa la autorización de la clave API.",
                    "cloudflare_challenge": "Cloudflare ha interceptado la petición al modelo local antes de llegar a LM Studio.",
                    "http_404": "El modelo o la ruta de la API no existe (HTTP 404). Comprueba que el modelo esté cargado en el ordenador.",
                    "timeout": "El proveedor no respondió dentro del tiempo configurado.",
                    "network_error": "No se pudo establecer conexión con el proveedor LLM.",
                    "empty_output": "El proveedor respondió sin contenido utilizable.",
                }
                reply_text = messages.get(
                    code,
                    "El proveedor LLM no pudo generar la respuesta. Tus datos y check-ins se han guardado con normalidad.",
                )
                if code not in messages and isinstance(exc, RuntimeError):
                    reply_text = (
                        "Ahora mismo no puedo generar una respuesta conversacional. "
                        "El fallo queda registrado de forma segura y tus datos y check-ins "
                        "se han guardado con normalidad."
                    )
                if code in messages:
                    reply_text += " Tus datos y check-ins se han guardado con normalidad."
            else:
                from app.services.local_llm_access import LocalLlmAccessDenied
                from app.services.personal_llm import LocalModelUnavailable
                if isinstance(exc, LocalModelUnavailable):
                    reply_text = f"{exc} Tus datos y check-ins se han guardado con normalidad."
                elif isinstance(exc, LocalLlmAccessDenied):
                    reply_text = (
                        "Ahora mismo no puedo generar una respuesta conversacional. "
                        "El fallo queda registrado de forma segura y tus datos y check-ins "
                        "se han guardado con normalidad."
                    )
                elif isinstance(exc, RuntimeError) and str(exc) == "OPENAI_API_KEY_NOT_CONFIGURED":
                    reply_text = (
                        "La API de OpenAI no está configurada en Render (falta OPENAI_API_KEY). "
                        "Tus datos y check-ins se han guardado con normalidad."
                    )
                else:
                    reply_text = (
                        "Ahora mismo no puedo generar una respuesta conversacional. "
                        "El fallo queda registrado de forma segura y tus datos y check-ins "
                        "se han guardado con normalidad."
                    )
        ui_mode = "normal"
        resources = None
        # No fixed safety copy at levels 0-2, so no pack to name.
        protocol_version = None
        reply_from_model = not failed

    db.add(
        ChatMessage(
            user_id=user.id,
            role="assistant",
            content=reply_text,
            ui_mode=ui_mode,
            # Which server-owned pack supplied the fixed LEVEL3/LEVEL4 copy and
            # resources in this turn, so it can be reproduced after a pack change.
            safety_protocol_version=protocol_version,
            **_reply_provenance(
                db,
                from_model=reply_from_model,
                metadata=reply_metadata,
                system_instruction=agent1_instruction,
                context_block=context_block,
            ),
        )
    )
    db.commit()

    clinical_memory.commit_turn(
        db,
        user_id=user.id,
        text=user_message,
        channel="chat",
        source_id=source_message.id,
        correlation_id=correlation_id,
        alert_level=level,
    )

    return {
        "reply": reply_text,
        "ui_mode": ui_mode,
        "resources": resources,
        "safety_protocol_version": protocol_version,
        "correlation_id": correlation_id,
    }
