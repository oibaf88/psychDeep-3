from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.memory_pipeline import (
    MemoryEvidence,
    compile_memory_context,
    stable_hash,
    validate_derived_item,
)


def test_stable_hash_is_deterministic_for_dict_order():
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})


def test_derived_memory_requires_sources_and_explicit_hypothesis_perspective():
    with pytest.raises(ValueError, match="source references"):
        validate_derived_item({
            "item_type": "preference",
            "perspective": "user_report",
            "content": "synthetic preference",
            "source_refs": [],
        })
    with pytest.raises(ValueError, match="hypotheses"):
        validate_derived_item({
            "item_type": "psychological_hypothesis",
            "perspective": "user_report",
            "content": "synthetic hypothesis",
            "source_refs": ["synthetic-event-1"],
        })


def test_context_compiler_deduplicates_and_keeps_attribution():
    now = datetime.now(timezone.utc)
    evidence = [
        MemoryEvidence(
            ref="event-1",
            item_type="preference",
            perspective="user_report",
            attribution="user",
            text="Prefiere respuestas breves",
            occurred_at=now,
            source_refs=("chat:1",),
            score=1.0,
        ),
        MemoryEvidence(
            ref="event-1",
            item_type="preference",
            perspective="user_report",
            attribution="user",
            text="Prefiere respuestas breves",
            occurred_at=now,
            source_refs=("chat:1",),
            score=0.5,
        ),
        MemoryEvidence(
            ref="event-2",
            item_type="psychological_hypothesis",
            perspective="assistant_hypothesis",
            attribution="assistant",
            text="Hipótesis sintética, no diagnóstico",
            occurred_at=now,
            uncertainty="high",
            source_refs=("chat:2",),
            score=0.1,
        ),
    ]
    result = compile_memory_context(
        task_type="conversation",
        evidence=evidence,
        budget_tokens=500,
        reserved_tokens=50,
    )
    assert result.budget_tokens == 450
    assert result.evidence_refs.count("event-1") == 1
    assert "perspective=user_report" in result.text
    assert "not authority" in result.text
    assert "Sources: chat:1" in result.text


def test_context_compiler_respects_zero_budget():
    result = compile_memory_context(
        task_type="crisis",
        evidence=[
            MemoryEvidence("event-1", "episode", "user_report", "user", "synthetic", score=1)
        ],
        budget_tokens=20,
        reserved_tokens=100,
    )
    assert result.budget_tokens == 0
    assert result.text == ""


def test_longitudinal_task_prioritizes_source_linked_patterns():
    evidence = [
        MemoryEvidence("pref", "preference", "user_report", "user", "Prefiere el modo oscuro", score=0.5),
        MemoryEvidence("pattern", "longitudinal_pattern", "derived_pattern", "system", "Cambios descritos en tres episodios", score=0.5, source_refs=("e1", "e2", "e3")),
    ]
    result = compile_memory_context(task_type="longitudinal_analysis", evidence=evidence, budget_tokens=600)
    assert result.evidence_refs[0] == "pattern"
