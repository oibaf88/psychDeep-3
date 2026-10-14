from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest

from app.services.patient_understanding import (
    PatientPattern,
    PatientThemeGap,
    WholePersonModelDraft,
    _balanced_episode_subset,
    _partition_source_docs,
    _projection_items,
    _split_long_source_docs,
    _validate_source_refs,
    patient_model_context_block,
)


def test_split_long_source_doc_keeps_stable_chunk_references():
    source_id = uuid.uuid4()
    long_text = ("primer tramo de texto con evidencia temporal.\n" * 800)
    docs = _split_long_source_docs([{
        "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "source_refs": [f"chat_message:{source_id}"],
        "content": long_text,
        "channel": "chat",
        "kind": "literal_chat_user",
    }], max_chars=4000, overlap_chars=100)

    assert len(docs) > 1
    assert docs[0]["source_refs"] == [f"chat_message:{source_id}#chunk-001"]
    assert docs[1]["source_refs"] == [f"chat_message:{source_id}#chunk-002"]
    assert all(len(item["content"]) < 4200 for item in docs)
    assert all("primer tramo de texto" in item["content"] for item in docs)


def test_partition_source_docs_covers_each_ref_once_per_input_document():
    docs = []
    for i in range(27):
        month = 1 + (i // 9)
        stamp = datetime(2026, month, 1, tzinfo=timezone.utc)
        docs.append({
            "timestamp": stamp,
            "source_refs": [f"source:{i}"],
            "content": f"evidence {i}",
            "channel": "test",
            "kind": "synthetic",
        })

    batches = _partition_source_docs(docs)
    refs = [ref for batch in batches for doc in batch for ref in doc["source_refs"]]
    assert sorted(refs) == [f"source:{i}" for i in range(27)]
    assert all(len(batch) <= 10 for batch in batches)


def test_balanced_episode_subset_covers_old_and_recent_timeline():
    episodes = [
        SimpleNamespace(
            id=uuid.uuid4(),
            start_at=datetime(2020, 1, 1, tzinfo=timezone.utc).replace(year=2020 + i // 12, month=(i % 12) + 1),
            end_at=None,
            created_at=datetime(2020 + i // 12, (i % 12) + 1, 1, tzinfo=timezone.utc),
        )
        for i in range(240)
    ]
    selected = _balanced_episode_subset(episodes, max_items=60)
    assert len(selected) == 60
    assert selected[0].id == episodes[0].id
    assert selected[-1].id == episodes[-1].id
    assert len({item.id for item in selected}) == 60


def test_projection_items_keep_patterns_and_recording_gaps_separate():
    pattern = PatientPattern(
        domain="coping_and_regulation",
        pattern="La dificultad de regulación aparece en varios episodios.",
        temporal_description="Se describe en tres periodos distintos.",
        confidence=0.7,
        uncertainty="medium",
        alternative_explanations=["Cambios simultáneos del entorno"],
        counterevidence_refs=["chat_message:counter-evidence"],
        source_refs=["chat_message:source-a", "chat_message:source-b"],
    )
    gap = PatientThemeGap(
        topic_key="work_study_and_routines",
        description="No hay registros etiquetados sobre las rutinas durante este intervalo.",
        gap_start_at="2026-02-01T00:00:00+00:00",
        gap_end_at="2026-05-01T00:00:00+00:00",
        interpretation="recording_gap_only",
        evidence_before_refs=["chat_message:before"],
        evidence_after_refs=["chat_message:after"],
        uncertainty="high",
    )
    model = WholePersonModelDraft(
        patient_summary="Modelo sintético de prueba.",
        facets=[],
        patterns=[pattern],
        trajectories=[],
        protective_factors=[],
        contradictions=[],
        open_questions=[],
        theme_gaps=[gap],
        limitations=[],
    )
    items = _projection_items(model)
    assert any(item["item_type"] == "longitudinal_pattern" for item in items)
    gap_item = next(item for item in items if item["item_type"] == "open_thread")
    assert "no indica ausencia del suceso" in gap_item["content"]
    assert gap_item["source_refs"] == ["chat_message:before", "chat_message:after"]


def test_whole_person_model_rejects_unrecognized_source_references():
    model = WholePersonModelDraft(
        patient_summary="Modelo sintético.",
        facets=[],
        patterns=[PatientPattern(
            domain="emotional_experience",
            pattern="Patrón sintético.",
            temporal_description="En varios registros.",
            confidence=0.4,
            uncertainty="high",
            alternative_explanations=[],
            counterevidence_refs=[],
            source_refs=["chat_message:not-authorized"],
        )],
        trajectories=[],
        protective_factors=[],
        contradictions=[],
        open_questions=[],
        theme_gaps=[],
        limitations=[],
    )
    with pytest.raises(ValueError, match="unknown_source_refs"):
        _validate_source_refs(model, {"chat_message:authorized"})


def test_crisis_context_does_not_load_whole_person_narrative():
    assert patient_model_context_block(None, None, "synthetic query", in_crisis=True) == ""
