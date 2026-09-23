import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.models_vnext import MobileInferenceEvent, ModelRun
from app.schemas_mobile import MobileInferenceIn, MobileInferenceOut
from app.security import require_patient

router = APIRouter(prefix="/api/v1/mobile", tags=["mobile-inference"])

@router.post("/inference-events", response_model=MobileInferenceOut, status_code=status.HTTP_202_ACCEPTED)
def ingest_mobile_inference(payload: MobileInferenceIn, idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128), db: Session = Depends(get_db), user: User = Depends(require_patient)):
    existing = db.query(MobileInferenceEvent).filter(MobileInferenceEvent.user_id == user.id, MobileInferenceEvent.idempotency_key == idempotency_key).first()
    if existing:
        if existing.event_id != payload.event_id:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_KEY_REUSED")
        if existing.model_run_id is None:
            raise HTTPException(status_code=409, detail="MOBILE_EVENT_INCOMPLETE")
        return MobileInferenceOut(event_id=existing.event_id, model_run_id=existing.model_run_id, synced_at=existing.created_at)

    model_run = ModelRun(user_id=user.id, purpose="mobile_local_inference", audience="patient",
        deployment_alias="mobile-local", provider_type="mobile_local", model_id=payload.model_id,
        model_version=payload.model_version, prompt_version=payload.prompt_version,
        policy_version="support-policy-v1", input_hash=payload.input_hash, output_schema=payload.output_schema,
        status="succeeded", correlation_id=uuid.uuid4(), latency_ms=payload.latency_ms)
    db.add(model_run)
    db.flush()
    event = MobileInferenceEvent(event_id=payload.event_id, user_id=user.id, conversation_id=payload.conversation_id,
        model_run_id=model_run.id, deployment_alias="mobile-local", model_id=payload.model_id,
        model_version=payload.model_version, prompt_version=payload.prompt_version, input_hash=payload.input_hash,
        output=payload.output, output_schema=payload.output_schema, client_platform=payload.client_platform,
        client_app_version=payload.client_app_version, inference_engine=payload.inference_engine,
        client_model_checksum=payload.client_model_checksum, client_timestamp=payload.client_timestamp,
        latency_ms=payload.latency_ms, idempotency_key=idempotency_key)
    db.add(event)
    try:
        db.commit()
    except Exception:
        db.rollback()
        retry = db.query(MobileInferenceEvent).filter(MobileInferenceEvent.user_id == user.id, MobileInferenceEvent.idempotency_key == idempotency_key).first()
        if retry and retry.model_run_id:
            return MobileInferenceOut(event_id=retry.event_id, model_run_id=retry.model_run_id, synced_at=retry.created_at)
        raise
    return MobileInferenceOut(event_id=event.event_id, model_run_id=model_run.id, synced_at=event.created_at)
