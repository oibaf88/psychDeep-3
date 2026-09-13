"""Compatibility writers from established UX records to vNext observations.

During expand-and-migrate the legacy tables remain readable/authoritative for
existing endpoints while every new self-report is also represented in the
canonical Observation stream. The original row is never mutated.
"""
from __future__ import annotations

from datetime import timezone

from sqlalchemy.orm import Session

from app.models import CheckIn, DiaryEntry
from app.models_vnext import Observation


def _utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def record_checkin(db: Session, checkin: CheckIn) -> None:
    occurred = _utc(checkin.created_at)
    rows = [
        ("mood", checkin.mood, "0-10"),
        ("craving", checkin.craving, "0-10"),
        ("sleep_hours", checkin.sleep_hours, "hours"),
        ("self_efficacy", checkin.self_efficacy, "0-10"),
    ]
    for field, value, unit in rows:
        db.add(Observation(
            user_id=checkin.user_id,
            source="self_report",
            type=field,
            value={"value": value},
            unit=unit,
            occurred_at=occurred,
            quality={"compatibility_dual_write": True},
            legacy_source_table="check_ins",
            legacy_source_id=checkin.id,
            legacy_source_field=field,
        ))
    if checkin.notes and checkin.notes.strip():
        db.add(Observation(
            user_id=checkin.user_id,
            source="self_report",
            type="checkin_context",
            value={"text": checkin.notes},
            occurred_at=occurred,
            quality={"compatibility_dual_write": True},
            legacy_source_table="check_ins",
            legacy_source_id=checkin.id,
            legacy_source_field="notes",
        ))
    db.commit()


def record_diary(db: Session, entry: DiaryEntry) -> None:
    db.add(Observation(
        user_id=entry.user_id,
        source="self_report",
        type="diary_text",
        value={"text": entry.content},
        occurred_at=_utc(entry.created_at),
        quality={"compatibility_dual_write": True},
        legacy_source_table="diary_entries",
        legacy_source_id=entry.id,
        legacy_source_field="content",
    ))
    db.commit()
