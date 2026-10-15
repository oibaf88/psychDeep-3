"""Clinical memory reads for assigned clinicians. Nobody edits or deletes it."""
import hashlib
import io
import os
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PatientProfessionalAssignment, User
from app.models_vnext import MemoryJob, PatientClinicalDocument
from app.security import get_current_user, require_professional
from app.services import audit, clinical_memory
from app.services.consent import LINGUISTIC_ANALYSIS, is_granted
from app.services.memory_pipeline import enqueue_memory_job
from app.utils import utc_iso

router = APIRouter(prefix="/api/v1", tags=["clinical-memory"])

_IMMUTABLE = "La memoria clínica no se modifica ni se borra."
_HIDDEN = "La formulación clínica no se muestra en la cuenta del paciente."


class AnnotationIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    target_type: str = Field(pattern="^(discourse|reading|formulation)$")
    target_id: uuid.UUID


def _assignment(db: Session, patient_id, professional_id, statuses=("active", "paused")) -> bool:
    row = (
        db.query(PatientProfessionalAssignment)
        .filter(
            PatientProfessionalAssignment.patient_id == patient_id,
            PatientProfessionalAssignment.professional_id == professional_id,
            PatientProfessionalAssignment.status.in_(list(statuses)),
        )
        .first()
    )
    return row is not None


def _require_clinical_read(db: Session, professional: User, patient_id: uuid.UUID) -> None:
    if professional.role == "admin_clinical":
        raise HTTPException(status_code=403, detail="admin_clinical no tiene visibilidad clínica de la memoria")
    if professional.role == "therapist" and not _assignment(db, patient_id, professional.id):
        raise HTTPException(status_code=403, detail="No tienes asignación activa/pausada con este paciente")


def _require_active_writer(db: Session, professional: User, patient_id: uuid.UUID) -> None:
    _require_clinical_read(db, professional, patient_id)
    if professional.role == "therapist" and not _assignment(db, patient_id, professional.id, statuses=("active",)):
        raise HTTPException(status_code=403, detail="Se requiere asignación activa para anotar la memoria")


def _iso(value) -> str | None:
    if value is None:
        return None
    return utc_iso(value)


def _view(rows) -> dict:
    formulation = rows["formulation"]
    return {
        "formulation": None
        if formulation is None
        else {
            "id": str(formulation.id),
            "l0": formulation.l0,
            "l1": formulation.l1,
            "l2": formulation.l2,
            "acute_episode": formulation.acute_episode,
            "prompt_version": formulation.prompt_version,
            "created_at": _iso(formulation.created_at),
        },
        "formulation_history": [
            {
                "id": str(row.id),
                "l0": row.l0,
                "acute_episode": row.acute_episode,
                "created_at": _iso(row.created_at),
            }
            for row in rows["formulation_history"]
        ],
        "discourse": [
            {
                "id": str(row.id),
                "channel": row.channel,
                "quote": row.quote,
                "manner": row.manner,
                "spoken_at": _iso(row.spoken_at),
            }
            for row in rows["discourse"]
        ],
        "readings": [
            {
                "id": str(row.id),
                "kind": row.kind,
                "uncertainty": row.uncertainty,
                "hypothesis": row.hypothesis,
                "status": row.status,
                "evidence_refs": row.evidence_refs,
                "created_at": _iso(row.created_at),
            }
            for row in rows["readings"]
        ],
        "notices": [
            {
                "id": str(row.id),
                "reason": row.reason,
                "status": row.status,
                "evidence_refs": row.evidence_refs,
                "created_at": _iso(row.created_at),
                "acknowledged_at": _iso(row.acknowledged_at),
            }
            for row in rows["notices"]
        ],
        "annotations": [
            {
                "id": str(row.id),
                "body": row.body,
                "target_type": row.target_type,
                "target_id": str(row.target_id),
                "created_at": _iso(row.created_at),
            }
            for row in rows["annotations"]
        ],
        "linguistic_analysis_consent": bool(rows.get("linguistic_analysis_consent", False)),
        "patient_model": None if not rows.get("patient_model") else {
            **rows["patient_model"],
            "source_watermark": _iso(rows["patient_model"].get("source_watermark")),
            "created_at": _iso(rows["patient_model"].get("created_at")),
        },
        "clinical_documents": [
            {
                "id": str(row.id),
                "original_filename": row.original_filename,
                "media_type": row.media_type,
                "sha256": row.sha256,
                "file_size_bytes": row.file_size_bytes,
                "document_type": row.document_type,
                "document_date": _iso(row.document_date),
                "extraction_status": row.extraction_status,
                "analysis_status": row.analysis_status,
                "error_category": row.error_category,
                "created_at": _iso(row.created_at),
                "analyzed_at": _iso(row.analyzed_at),
            }
            for row in rows.get("clinical_documents", [])
        ],
    }


@router.get("/memory")
def patient_memory_is_hidden(user: User = Depends(get_current_user)):
    raise HTTPException(status_code=403, detail=_HIDDEN)


@router.api_route("/memory/{memory_id}", methods=["PUT", "PATCH", "DELETE"])
def memory_is_immutable(memory_id: uuid.UUID, user: User = Depends(get_current_user)):
    raise HTTPException(status_code=403, detail=_IMMUTABLE)


@router.get("/professional/patients/{patient_id}/memory")
def read_patient_memory(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    professional: User = Depends(require_professional),
):
    _require_clinical_read(db, professional, patient_id)
    return _view(clinical_memory.bundle(db, patient_id))




MAX_CLINICAL_DOCUMENT_BYTES = 15 * 1024 * 1024
MAX_EXTRACTED_DOCUMENT_CHARS = 500_000
MAX_DOCX_XML_BYTES = 8 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_DOCX_ENTRIES = 1000
_ALLOWED_DOCUMENT_TYPES = {
    "clinical_report", "discharge_summary", "psychological_report",
    "psychiatric_report", "medication_report", "other",
}
_ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}


def _document_payload(row: PatientClinicalDocument, *, duplicate: bool = False) -> dict:
    return {
        "id": str(row.id),
        "original_filename": row.original_filename,
        "media_type": row.media_type,
        "sha256": row.sha256,
        "file_size_bytes": row.file_size_bytes,
        "document_type": row.document_type,
        "document_date": _iso(row.document_date),
        "extraction_status": row.extraction_status,
        "analysis_status": row.analysis_status,
        "error_category": row.error_category,
        "created_at": _iso(row.created_at),
        "analyzed_at": _iso(row.analyzed_at),
        "duplicate": duplicate,
    }


def _extract_clinical_document(filename: str, payload: bytes) -> tuple[str, str, str]:
    """Extract searchable text without executing embedded document content."""
    suffix = os.path.splitext(filename.lower())[1]
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Formato no admitido. Usa PDF, DOCX, TXT o Markdown.")
    if not payload:
        raise HTTPException(status_code=422, detail="El archivo está vacío.")
    if suffix == ".pdf":
        if not payload.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="El archivo no parece ser un PDF válido.")
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(payload), strict=False)
            if len(reader.pages) > 300:
                raise HTTPException(status_code=413, detail="El PDF supera el límite de 300 páginas.")
            extracted = "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=422, detail="No se ha podido leer el PDF. Comprueba que no esté dañado.") from None
        if not extracted:
            return "", "needs_ocr", "application/pdf"
        media_type = "application/pdf"
    elif suffix == ".docx":
        if not payload.startswith(b"PK"):
            raise HTTPException(status_code=422, detail="El archivo no parece ser un DOCX válido.")
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = archive.infolist()
                if len(members) > MAX_DOCX_ENTRIES:
                    raise HTTPException(status_code=413, detail="El DOCX contiene demasiados elementos internos.")
                if sum(member.file_size for member in members) > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise HTTPException(status_code=413, detail="El DOCX supera el límite de tamaño descomprimido.")
                document_xml = archive.getinfo("word/document.xml")
                if document_xml.file_size > MAX_DOCX_XML_BYTES:
                    raise HTTPException(status_code=413, detail="El cuerpo XML del DOCX supera el límite permitido.")
                if document_xml.file_size / max(document_xml.compress_size, 1) > 1000:
                    raise HTTPException(status_code=413, detail="El DOCX presenta una compresión anómala y se ha rechazado.")
                raw_xml = archive.read(document_xml)
            root = ET.fromstring(raw_xml)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs = []
            for paragraph in root.findall(".//w:p", ns):
                text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns))
                if text.strip():
                    paragraphs.append(text)
            extracted = "\n".join(paragraphs).strip()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=422, detail="No se ha podido leer el DOCX. Comprueba que no esté dañado.") from None
        if not extracted:
            raise HTTPException(status_code=422, detail="El DOCX no contiene texto legible.")
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        try:
            extracted = payload.decode("utf-8-sig").strip()
        except UnicodeDecodeError:
            raise HTTPException(status_code=422, detail="El archivo de texto debe estar codificado en UTF-8.") from None
        if not extracted:
            raise HTTPException(status_code=422, detail="El archivo no contiene texto legible.")
        media_type = "text/markdown" if suffix == ".md" else "text/plain"

    if len(extracted) > MAX_EXTRACTED_DOCUMENT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"El texto extraído supera {MAX_EXTRACTED_DOCUMENT_CHARS:,} caracteres. Divide el informe en archivos más pequeños.",
        )
    return extracted, "text_extracted", media_type


@router.post("/professional/patients/{patient_id}/memory/rebuild")
def rebuild_patient_memory(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    professional: User = Depends(require_professional),
):
    """Queue a versioned whole-person synthesis, outside the web request."""
    _require_active_writer(db, professional, patient_id)
    if not is_granted(db, patient_id, LINGUISTIC_ANALYSIS):
        raise HTTPException(status_code=403, detail="El consentimiento de análisis lingüístico no figura como activo para este paciente.")
    pending = (
        db.query(MemoryJob)
        .filter(
            MemoryJob.user_id == patient_id,
            MemoryJob.job_type == "longitudinal_analysis",
            MemoryJob.source_table == "patient_model",
            MemoryJob.source_id == patient_id,
            MemoryJob.status.in_(("pending", "running")),
        )
        .first()
    )
    if pending is not None:
        return {"status": "queued", "job_id": str(pending.id), "already_queued": True}
    queued = enqueue_memory_job(
        db,
        user_id=patient_id,
        job_type="longitudinal_analysis",
        source_table="patient_model",
        source_id=patient_id,
        idempotency_key=f"patient-model:manual:{uuid.uuid4()}",
    )
    db.commit()
    audit.log(
        db, actor_id=professional.id, actor_role=professional.role,
        action="longitudinal_patient_model_rebuild_queued",
        entity_type="patient_model", entity_id=patient_id,
        extra={"already_queued": not queued},
    )
    return {"status": "queued" if queued else "already_queued", "already_queued": not queued}


@router.post("/professional/patients/{patient_id}/memory/documents", status_code=201)
async def upload_patient_clinical_document(
    patient_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: str = Form(default="clinical_report"),
    document_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
    professional: User = Depends(require_professional),
):
    """Save an attributed report and queue it for longitudinal analysis."""
    _require_active_writer(db, professional, patient_id)
    if not is_granted(db, patient_id, LINGUISTIC_ANALYSIS):
        raise HTTPException(status_code=403, detail="El consentimiento de análisis lingüístico no figura como activo para este paciente.")
    if document_type not in _ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail="Tipo de informe no admitido.")
    supplied_name = (file.filename or "informe").replace("\\", "/")
    filename = os.path.basename(supplied_name).strip()[:255] or "informe"
    payload = await file.read(MAX_CLINICAL_DOCUMENT_BYTES + 1)
    if len(payload) > MAX_CLINICAL_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 15 MiB.")
    extracted_text, extraction_status, media_type = _extract_clinical_document(filename, payload)
    digest = hashlib.sha256(payload).hexdigest()
    existing = (
        db.query(PatientClinicalDocument)
        .filter(PatientClinicalDocument.user_id == patient_id, PatientClinicalDocument.sha256 == digest)
        .first()
    )
    if existing is not None:
        return {**_document_payload(existing, duplicate=True), "status": existing.analysis_status}

    parsed_date = None
    if document_date:
        try:
            parsed = datetime.fromisoformat(document_date.strip())
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            parsed_date = parsed.astimezone(timezone.utc)
        except ValueError:
            raise HTTPException(status_code=422, detail="La fecha del informe debe tener formato ISO (AAAA-MM-DD).") from None

    row = PatientClinicalDocument(
        user_id=patient_id,
        uploaded_by=professional.id,
        original_filename=filename,
        media_type=media_type,
        sha256=digest,
        file_size_bytes=len(payload),
        document_type=document_type,
        document_date=parsed_date,
        raw_content=payload,
        extracted_text=extracted_text or None,
        extraction_status=extraction_status,
        analysis_status="queued" if extraction_status == "text_extracted" else "blocked",
        error_category="ocr_required" if extraction_status == "needs_ocr" else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit.log(
        db, actor_id=professional.id, actor_role=professional.role,
        action="patient_clinical_document_uploaded",
        entity_type="patient_clinical_document", entity_id=row.id,
        extra={
            "patient_id": str(patient_id),
            "sha256": digest,
            "file_size_bytes": len(payload),
            "document_type": document_type,
            "extraction_status": extraction_status,
        },
    )

    if extraction_status == "text_extracted":
        try:
            enqueue_memory_job(
                db,
                user_id=patient_id,
                job_type="longitudinal_analysis",
                source_table="patient_clinical_documents",
                source_id=row.id,
                idempotency_key=f"clinical-document:{row.id}:whole-person-v1",
            )
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            row = db.get(PatientClinicalDocument, row.id)
            if row is not None:
                row.analysis_status = "failed"
                row.error_category = type(exc).__name__[:64]
                db.add(row)
                db.commit()
            raise HTTPException(status_code=503, detail="El informe se ha guardado, pero no se pudo programar su análisis.") from None

    return {**_document_payload(row), "status": row.analysis_status}


@router.post("/professional/patients/{patient_id}/memory/annotations", status_code=201)
def annotate_memory(
    patient_id: uuid.UUID,
    payload: AnnotationIn,
    db: Session = Depends(get_db),
    professional: User = Depends(require_professional),
):
    _require_active_writer(db, professional, patient_id)
    try:
        row = clinical_memory.add_annotation(
            db,
            patient_id=patient_id,
            author_id=professional.id,
            body=payload.body,
            target_type=payload.target_type,
            target_id=payload.target_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="No existe esa memoria para este paciente") from None
    except ValueError:
        raise HTTPException(status_code=422, detail="La nota está vacía") from None
    return {"id": str(row.id), "body": row.body, "target_type": row.target_type, "target_id": str(row.target_id)}


@router.post("/professional/patients/{patient_id}/memory/notices/{notice_id}/acknowledge")
def acknowledge_notice(
    patient_id: uuid.UUID,
    notice_id: uuid.UUID,
    db: Session = Depends(get_db),
    professional: User = Depends(require_professional),
):
    _require_active_writer(db, professional, patient_id)
    try:
        notice = clinical_memory.acknowledge_notice(
            db, patient_id=patient_id, notice_id=notice_id, professional_id=professional.id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="No existe ese aviso") from None
    return {"id": str(notice.id), "status": notice.status}
