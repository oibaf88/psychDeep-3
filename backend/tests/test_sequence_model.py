"""Tests for the time-aware single-patient sequence model."""

from app.services.sequence_model import (
    ChangeSignalDraft,
    PatientEvent,
    TimeAwareSequenceModel,
)


def _event(day: int, source: str = "diary") -> PatientEvent:
    from datetime import datetime, timedelta, timezone

    return PatientEvent(
        id=f"event-{day}",
        source=source,
        happened_at=datetime.now(timezone.utc) - timedelta(days=day),
        content=f"check-in day {day}",
        recipient="patient",
        source_refs=(),
    )


def test_looks_better_than_its_own_baseline():
    model = TimeAwareSequenceModel(min_points=3)
    events = [_event(3), _event(2), _event(1), _event(0)]
    drafts = model.analyse("p1", events, "consent", "corr", prompt_text="s", user_id="u1")
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.effect > 0.5
    assert draft.algorithm_version == "patient-sequence-v1"
    assert draft.correlation_id == "corr"
    assert draft.explanation.startswith("cambio")


def test_requires_min_points():
    model = TimeAwareSequenceModel(min_points=3)
    events = [_event(2), _event(1)]
    assert model.analyse("p1", events, "consent", "corr", prompt_text="s", user_id="u1") == []


def test_does_not_anchor_to_other_patients():
    model = TimeAwareSequenceModel()
    events = [_event(1, "diary"), _event(1, "check_in"), _event(1, "chat")]
    drafts = model.analyse("p-single", events, "consent", "corr", prompt_text="s", user_id="u-single")
    for d in drafts:
        assert d.patient_id == "p-single"


def test_drops_events_with_external_clinical_refs():
    from dataclasses import replace

    model = TimeAwareSequenceModel(min_points=3)
    events = [_event(3), _event(2), _event(1)]
    events.append(replace(_event(0), source_refs=("diary_entry:0", "clinical_document:abc")))
    drafts = model.analyse("p1", events, "consent", "corr", prompt_text="s", user_id="u1")
    # The uploaded report is not app input: the latest app event is day 1.
    assert all(d.event_id != "event-0" for d in drafts)


def test_effect_is_bounded_and_one_draft_per_run():
    model = TimeAwareSequenceModel(min_points=3)
    events = [_event(day) for day in range(10, -1, -1)]
    drafts = model.analyse("p1", events, "consent", "corr", prompt_text="s", user_id="u1")
    assert len(drafts) <= 1
    for d in drafts:
        assert 0.0 <= d.effect <= 1.0
        assert 0.0 <= d.confidence <= 0.95


def test_no_signal_without_spacing_in_baseline():
    model = TimeAwareSequenceModel(min_points=3)
    events = [_event(1, "diary"), _event(1, "check_in"), _event(0, "chat")]
    assert model.analyse("p1", events, "consent", "corr", prompt_text="s", user_id="u1") == []
