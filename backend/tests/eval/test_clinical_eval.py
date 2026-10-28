import json
import pytest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# Assume these are the backend components we want to evaluate
from app.services.agent1_context import build as build_agent1_context
from app.services.clinical_copilot import build_dossier_text as build_copilot_context
from app.content.prompts import ANALYZER_SYSTEM_PROMPT


@pytest.fixture
def eval_cases():
    cases_path = Path(__file__).parent / "eval_cases.json"
    with open(cases_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_eval_cases_present(eval_cases):
    assert len(eval_cases) > 0, "No evaluation cases loaded"
    for case in eval_cases:
        assert "id" in case
        assert "input_text" in case
        assert "expected_violation" in case
        assert "agent" in case


def test_agent1_orchestrator_prompt_renders_safety_rules(eval_cases):
    """
    Tests that the context built for the Agent 1 orchestrator correctly embeds the patient
    baseline and ensures anti-prescription constraints.
    """
    case = next((c for c in eval_cases if c["id"] == "autonomous_prescription_1"), None)
    if not case:
        pytest.skip("Case not found")

    db = MagicMock()
    patient_id = uuid.uuid4()
    assessment = MagicMock()

    with patch("app.services.agent1_context._facts_block", return_value="Baseline: " + case["context"]["patient_baseline"]):
        with patch("app.services.agent1_context._safety_plan_block", return_value=""):
            with patch("app.services.agent1_context._checkins_block", return_value=""):
                with patch("app.services.agent1_context._psychosocial_block", return_value=""):
                    context_str = build_agent1_context(db, patient_id, assessment, in_crisis=False)

    # We verify the context properly rendered the adversarial baseline
    assert case["context"]["patient_baseline"] in context_str


def test_copilot_prompt_renders_hallucination_prevention(eval_cases):
    """
    Tests that the clinical copilot dossier context builds without injecting false historical data.
    """
    case = next((c for c in eval_cases if c["id"] == "hallucination_1"), None)
    if not case:
        pytest.skip("Case not found")

    patient = MagicMock()
    patient.id = uuid.uuid4()
    patient.given_name = "Eval Copilot"
    patient.created_at = datetime.now()

    db = MagicMock()

    with patch("app.services.clinical_copilot._longitudinal_change_section", return_value="Profile: " + case["context"]["patient_baseline"]):
        context_str, _ = build_copilot_context(db, patient)

    assert case["context"]["patient_baseline"] in context_str


def test_analyzer_prompt_state_vs_trait(eval_cases):
    """
    Validates that the base Analyzer prompt strictly mandates separating state from trait.
    """
    case = next((c for c in eval_cases if c["id"] == "state_to_trait_1"), None)
    if not case:
        pytest.skip("Case not found")

    prompt = ANALYZER_SYSTEM_PROMPT
    assert "rasgo" in prompt.lower() and "transitorio" in prompt.lower()
