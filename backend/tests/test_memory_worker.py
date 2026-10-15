from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import memory_pipeline


class _Row:
    def __init__(self, value=None):
        self.value = value

    def mappings(self):
        return self

    def first(self):
        return self.value


def test_job_without_linguistic_consent_is_cancelled_without_model(monkeypatch):
    db = MagicMock()
    db.execute.return_value = _Row({
        "id": "job-1", "user_id": "user-1", "job_type": "longitudinal_analysis",
        "source_table": "memory_event_ledger", "source_id": "source-1",
    })
    with patch("app.services.memory_pipeline.claim_next_memory_job", return_value={
        "id": "job-1", "user_id": "user-1", "job_type": "longitudinal_analysis",
        "source_table": "memory_event_ledger", "source_id": "source-1",
    }), patch("app.services.consent.is_granted", return_value=False), \
         patch("app.services.model_gateway.get_model_gateway") as gateway:
        memory_pipeline.run_memory_worker_once(db)
    gateway.assert_not_called()
    sql = [str(call.args[0]) for call in db.execute.call_args_list]
    assert any("status = 'cancelled'" in statement for statement in sql)


def test_longitudinal_checkpoint_is_idempotently_coalesced_per_day():
    db = MagicMock()
    with patch.object(memory_pipeline, "enqueue_memory_job", return_value=False) as enqueue:
        memory_pipeline._enqueue_longitudinal_checkpoint(
            db,
            "user-synthetic",
            {"source_id": "source-synthetic", "source_table": "memory_event_ledger"},
        )
    enqueue.assert_called_once()
    kwargs = enqueue.call_args.kwargs
    assert kwargs["job_type"] == "longitudinal_analysis"
    assert kwargs["idempotency_key"].startswith("patient-model:daily:user-synthetic:")


def test_longitudinal_checkpoint_uses_stable_source_reference_and_daily_key():
    db = MagicMock()
    with patch.object(memory_pipeline, "enqueue_memory_job", return_value=True) as enqueue:
        memory_pipeline._enqueue_longitudinal_checkpoint(
            db,
            "user-synthetic",
            {"source_id": "source-synthetic", "source_table": "memory_event_ledger"},
        )
    enqueue.assert_called_once_with(
        db,
        user_id="user-synthetic",
        job_type="longitudinal_analysis",
        source_table="memory_event_ledger",
        source_id="source-synthetic",
        idempotency_key=enqueue.call_args.kwargs["idempotency_key"],
    )
    assert enqueue.call_args.kwargs["idempotency_key"].startswith("patient-model:daily:user-synthetic:")


def test_longitudinal_retrieval_does_not_query_when_consent_is_absent():
    db = MagicMock()
    with patch("app.services.consent.is_granted", return_value=False):
        result = memory_pipeline.retrieve_longitudinal_context(
            db,
            user_id="user-synthetic",
            query="tema sintético",
            budget_tokens=100,
        )
    db.execute.assert_not_called()
    assert result.evidence_refs == ()


def test_document_docx_rejects_uncompressed_payload_over_limit():
    import io
    import zipfile

    from fastapi import HTTPException
    from app.routers.memory import MAX_DOCX_XML_BYTES, _extract_clinical_document

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"x" * (MAX_DOCX_XML_BYTES + 1))
    with pytest.raises(HTTPException) as raised:
        _extract_clinical_document("report.docx", payload.getvalue())
    assert raised.value.status_code == 413
