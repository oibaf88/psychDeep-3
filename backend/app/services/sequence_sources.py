"""Refs the time-aware sequence may follow.

Check-in, diary, chat and confirmed facts are app input. A scan, a lab, or a
report from another centre is not, even if the patient uploads the PDF and
even if `clinical_document_analysis` is granted. The encoder must drop those
refs before it follows them. It must not write alert_level from them.
"""
from __future__ import annotations

EXTERNAL_CLINICAL_PREFIX = "clinical_document:"


def is_external_clinical_ref(ref: object) -> bool:
    return str(ref or "").startswith(EXTERNAL_CLINICAL_PREFIX)


def sequence_refs(refs) -> list[str]:
    """Keep only refs the longitudinal sequence is allowed to follow."""
    kept: list[str] = []
    for ref in refs or []:
        text = str(ref).strip()
        if text and not is_external_clinical_ref(text):
            kept.append(text)
    return kept


def is_external_clinical_doc(doc: dict) -> bool:
    """A chronology row built from an uploaded report, not from the app."""
    if str(doc.get("kind") or "") == "professional_clinical_document":
        return True
    return any(is_external_clinical_ref(ref) for ref in (doc.get("source_refs") or []))
