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
    _episode_context_node,
    _group_episode_nodes,
    _render_episode_digest_input,
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


def test_hierarchical_episode_groups_are_bounded_and_lossless():
    from app.services.patient_understanding import _group_episode_nodes

    nodes = [
        {
            "ref": f"memory_episode:{i}",
            "node_type": "episode",
            "start_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "end_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "source_refs": [f"chat_message:{i}"],
        }
        for i in range(1003)
    ]
    groups = _group_episode_nodes(nodes, group_size=12)
    assert all(1 <= len(group) <= 12 for group in groups)
    assert [node["ref"] for group in groups for node in group] == [node["ref"] for node in nodes]
    assert len({node["ref"] for group in groups for node in group}) == 1003


def test_hierarchical_digest_input_carries_node_and_provenance_references():
    from app.services.patient_understanding import _render_episode_digest_input

    nodes = [{
        "ref": "memory_summary:digest-1",
        "node_type": "summary",
        "title": "Síntesis de episodios",
        "start_at": datetime(2023, 1, 1, tzinfo=timezone.utc),
        "end_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "l0": "Cambio longitudinal descrito.",
        "l1": "Resumen sintético con matices.",
        "themes": ["relaciones", "afrontamiento"],
        "transitions": ["cambio de rutina"],
        "source_refs": ["memory_episode:e1", "memory_episode:e2"],
        "uncertainty": "medium",
        "level": 1,
    }]
    rendered = _render_episode_digest_input(nodes, level=2)
    assert "memory_summary:digest-1" in rendered
    assert "memory_episode:e1" in rendered
    assert "Cambio longitudinal descrito." in rendered
    assert "Nivel de síntesis: 2" in rendered


def test_episode_context_node_preserves_hierarchical_child_refs():
    from app.services.patient_understanding import _episode_context_node

    item = _episode_context_node({
        "ref": "memory_summary:digest-2",
        "node_type": "summary",
        "title": "Síntesis de etapa",
        "start_at": datetime(2021, 1, 1, tzinfo=timezone.utc),
        "end_at": datetime(2022, 1, 1, tzinfo=timezone.utc),
        "l0": "Resumen breve",
        "l1": "Resumen con evidencia y contradicciones",
        "themes": ["rutinas"],
        "transitions": ["reorientación"],
        "source_refs": ["memory_episode:old-a", "memory_episode:old-b"],
        "uncertainty": "medium",
        "level": 2,
    })
    assert item.ref == "memory_summary:digest-2"
    assert item.item_type == "longitudinal_pattern"
    assert "Resumen con evidencia" in item.text
    assert item.source_refs == ("memory_episode:old-a", "memory_episode:old-b")


def test_fulltext_retrieval_is_user_scoped_and_returns_source_evidence(monkeypatch):
    from app.services import consent
    from app.services.memory_pipeline import retrieve_longitudinal_context

    user_id = uuid.uuid4()
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    calls = []

    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

        def first(self):
            return self.rows[0] if self.rows else None

    class FakeResult:
        def __init__(self, rows=()):
            self.rows = rows

        def mappings(self):
            return FakeMappings(self.rows)

    class FakeNested:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeDB:
        def begin_nested(self):
            return FakeNested()

        def execute(self, statement, params):
            sql = str(statement)
            calls.append((sql, params))
            if "insert into psychdeep_v12.memory_retrieval_runs" in sql:
                return FakeResult()
            if "from psychdeep_v12.memory_items mi" in sql:
                return FakeResult([{
                    "id": uuid.uuid4(), "item_type": "preference",
                    "perspective": "user_report", "attribution": "user",
                    "content": "La persona refiere que los cambios de rutina preceden a su malestar.",
                    "uncertainty": "unknown", "confidence": None,
                    "created_at": now, "source_refs": ["chat_message:source-1"],
                    "relevance": 0.2,
                }])
            if "from documents e cross join q" in sql:
                return FakeResult([{
                    "id": uuid.uuid4(), "title": "Episodio longitudinal",
                    "l0": "Cambio de rutina", "l1": "Resumen del episodio",
                    "themes": ["rutina"], "transitions": [],
                    "source_refs": ["chat_message:source-2"],
                    "uncertainty": "medium", "start_at": now, "end_at": now,
                    "created_at": now, "relevance": 0.25,
                }])
            if "from documents s cross join q" in sql:
                return FakeResult([{
                    "id": uuid.uuid4(), "scope_type": "time_window",
                    "scope_key": "episode-digest:l1:synthetic",
                    "l0": "Digest L0", "l1": "Digest L1",
                    "source_refs": ["memory_episode:source-3"],
                    "source_watermark": now, "created_at": now, "relevance": 0.2,
                }])
            if "from psychdeep_v12.discourse_facts f" in sql:
                return FakeResult([{
                    "id": uuid.uuid4(), "channel": "chat",
                    "quote": "Literalmente contó el cambio de rutina.",
                    "spoken_at": now, "chat_message_id": uuid.uuid4(),
                    "diary_entry_id": None, "relevance": 0.4,
                }])
            if "from psychdeep_v12.chat_messages m" in sql:
                return FakeResult([{
                    "id": uuid.uuid4(), "content": "Mensaje original sobre cambios de rutina.",
                    "created_at": now, "relevance": 0.3,
                    "excerpt": "Mensaje original ⟦cambios de rutina⟧.",
                }])
            if "from psychdeep_v12.diary_entries d" in sql:
                return FakeResult([{
                    "id": uuid.uuid4(), "content": "Entrada de diario sobre cambios de rutina.",
                    "created_at": now, "relevance": 0.3,
                    "excerpt": "Diario ⟦cambios de rutina⟧.",
                }])
            if "from psychdeep_v12.memory_summary_versions" in sql:
                return FakeResult([{
                    "id": uuid.uuid4(), "l0": "Resumen global",
                    "l1": "Resumen longitudinal global con contexto.",
                    "source_refs": ["memory_episode:root"],
                    "source_watermark": now, "created_at": now,
                }])
            raise AssertionError("Unexpected SQL retrieval query: " + sql[:150])

        def rollback(self):
            pass

    seen_consent_identities = []
    def fake_is_granted(db, candidate_user_id, purpose):
        seen_consent_identities.append(candidate_user_id)
        return True

    monkeypatch.setattr(consent, "is_granted", fake_is_granted)
    result = retrieve_longitudinal_context(
        FakeDB(),
        user_id=str(user_id),
        query="cambios de rutina y malestar",
        task_type="conversation",
        budget_tokens=1100,
    )
    assert result.text
    assert "RETRIEVED MEMORY" in result.text
    assert "chat_message:source-1" in result.text or "source-1" in result.text
    assert "chat_message:" in result.text
    assert all(params.get("user_id") == str(user_id) for _sql, params in calls)
    telemetry = [params for sql, params in calls if "insert into psychdeep_v12.memory_retrieval_runs" in sql]
    assert telemetry and telemetry[0]["query_hash"]
    assert telemetry[0]["estimated_tokens"] == result.estimated_tokens
    assert seen_consent_identities == [user_id]


def test_hierarchical_episode_groups_are_bounded_and_lossless():
    nodes = [
        {
            "ref": f"memory_episode:{i}",
            "node_type": "episode",
            "start_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "end_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "source_refs": [f"chat_message:{i}"],
        }
        for i in range(1003)
    ]
    groups = _group_episode_nodes(nodes, group_size=12)
    assert all(1 <= len(group) <= 12 for group in groups)
    assert [node["ref"] for group in groups for node in group] == [node["ref"] for node in nodes]
    assert len({node["ref"] for group in groups for node in group}) == 1003


def test_hierarchical_digest_input_carries_node_and_provenance_references():
    nodes = [{
        "ref": "memory_summary:digest-1",
        "node_type": "summary",
        "title": "Síntesis de episodios",
        "start_at": datetime(2023, 1, 1, tzinfo=timezone.utc),
        "end_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "l0": "Cambio longitudinal descrito.",
        "l1": "Resumen sintético con matices.",
        "themes": ["relaciones", "afrontamiento"],
        "transitions": ["cambio de rutina"],
        "source_refs": ["memory_episode:e1", "memory_episode:e2"],
        "uncertainty": "medium",
        "level": 1,
    }]
    rendered = _render_episode_digest_input(nodes, level=2)
    assert "memory_summary:digest-1" in rendered
    assert "memory_episode:e1" in rendered
    assert "Cambio longitudinal descrito." in rendered
    assert "Nivel de síntesis: 2" in rendered


def test_episode_context_node_preserves_hierarchical_child_refs():
    item = _episode_context_node({
        "ref": "memory_summary:digest-2",
        "node_type": "summary",
        "title": "Síntesis de etapa",
        "start_at": datetime(2021, 1, 1, tzinfo=timezone.utc),
        "end_at": datetime(2022, 1, 1, tzinfo=timezone.utc),
        "l0": "Resumen breve",
        "l1": "Resumen con evidencia y contradicciones",
        "themes": ["rutinas"],
        "transitions": ["reorientación"],
        "source_refs": ["memory_episode:old-a", "memory_episode:old-b"],
        "uncertainty": "medium",
        "level": 2,
    })
    assert item.ref == "memory_summary:digest-2"
    assert item.item_type == "longitudinal_pattern"
    assert "Resumen con evidencia" in item.text
    assert item.source_refs == ("memory_episode:old-a", "memory_episode:old-b")
