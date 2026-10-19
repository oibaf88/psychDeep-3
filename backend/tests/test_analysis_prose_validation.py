"""Agent 2 prose fields pass deterministic output validation (G3).

The analyser never talks to the patient, but its ``short_rationale`` is
read by clinicians and the copilot, and its portrait / open threads reach
the clinician profile and Agent 1's context. A stated risk level, an
invented contact or an excluded technique in that prose is withheld; the
numeric and boolean signals the risk engine reads are never changed.
"""
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.content.safety_resources import ANALYSIS_RATIONALE_WITHHELD
from app.models import AlfaSignal
from app.services import conversation, output_validation
from app.services.llm.base import ProviderMetadata, StructuredAnalysisResult

LINGUISTIC = {
    "rumination_score": 0.7,
    "negative_valence": 0.6,
    "urgency_level": 0.5,
    "ideation_indirect": True,
    "ideation_direct": False,
    "consumption_crisis": False,
    "ambivalence": 0.4,
    "emotional_complexity": "medium",
    "short_rationale": "Da vueltas a la discusión con su pareja y expresa desesperanza.",
}


class ValidateAnalysisProseTests(unittest.TestCase):
    def test_descriptive_rationale_passes(self):
        check = output_validation.validate_analysis_prose(LINGUISTIC["short_rationale"])
        self.assertFalse(check.blocked)
        self.assertEqual(check.validator_version, output_validation.ANALYSIS_VALIDATOR_VERSION)

    def test_reported_quantity_passes(self):
        """The analyser describes what was said; quantities are not dosing advice."""
        check = output_validation.validate_analysis_prose("Refiere haber tomado 2 ml de GHB anoche.")
        self.assertFalse(check.blocked)

    def test_stated_risk_level_is_blocked(self):
        for text in ("Riesgo bajo, sin ideación.", "No hay riesgo en este texto.", "Nivel de alerta 3."):
            with self.subTest(text=text):
                check = output_validation.validate_analysis_prose(text)
                self.assertEqual(check.violations, ["risk_level_claim"])

    def test_invented_contact_is_blocked_and_server_numbers_pass(self):
        self.assertEqual(
            output_validation.validate_analysis_prose("Debería llamar al 600 123 456.").violations,
            ["unapproved_contact"],
        )
        self.assertFalse(output_validation.validate_analysis_prose("Menciona que llamó al 024.").blocked)

    def test_excluded_technique_is_blocked(self):
        check = output_validation.validate_analysis_prose("Le ayudaría sujetar cubitos de hielo.")
        self.assertEqual(check.violations, ["forbidden_technique"])

    def test_empty_text_passes(self):
        self.assertFalse(output_validation.validate_analysis_prose("").blocked)


class AnalyzeTextAndStoreProseTests(unittest.TestCase):
    def _run(self, *, linguistic=None, profile_update=None):
        value = {
            "linguistic": dict(linguistic or LINGUISTIC),
            "psychosocial": {"has_psychosocial_content": False, "observations": []},
        }
        if profile_update is not None:
            value["profile_update"] = profile_update
        result = StructuredAnalysisResult(
            value=value, metadata=ProviderMetadata(provider="anthropic", requested_model="stub")
        )
        provider = SimpleNamespace(analyze_structured=lambda *_a, **_k: result)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        trace = SimpleNamespace(id=uuid.uuid4(), status="started", error_code=None)
        audits, updates = [], []
        with patch.object(conversation.agent2_trace, "start", return_value=trace), \
             patch.object(conversation.agent2_trace, "mark_succeeded", lambda *_a, **_k: None), \
             patch.object(conversation.agent2_trace, "mark_failed", lambda *_a, **_k: None), \
             patch.object(conversation, "get_llm_provider", return_value=provider), \
             patch.object(conversation.clinical_memory, "formulation_for_analyzer", return_value=""), \
             patch.object(conversation.profile_service, "get", return_value=None), \
             patch.object(conversation.profile_service, "refresh_linguistic_baseline", lambda *_a, **_k: None), \
             patch.object(conversation.profile_service, "apply_analyzer_update",
                          lambda _db, _uid, block: updates.append(block)), \
             patch.object(conversation.audit, "log", lambda _db, **kw: audits.append(kw)):
            outcome = conversation.analyze_text_and_store(
                db,
                uuid.uuid4(),
                "Llevo toda la semana dándole vueltas a lo mismo y no veo salida.",
                source_type="chat_message",
                source_id=uuid.uuid4(),
                correlation_id=uuid.uuid4(),
            )
        signals = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], AlfaSignal)]
        return outcome, signals, audits, updates, trace

    def test_clean_analysis_is_stored_unchanged_without_audit(self):
        outcome, signals, audits, _updates, _trace = self._run()
        self.assertEqual(outcome.status, "succeeded")
        self.assertEqual(signals[0].value["short_rationale"], LINGUISTIC["short_rationale"])
        self.assertEqual(audits, [])

    def test_unsafe_rationale_is_replaced_and_signals_are_kept(self):
        unsafe = dict(LINGUISTIC, short_rationale="Riesgo bajo; puede llamar al 600 123 456.")
        outcome, signals, audits, _updates, trace = self._run(linguistic=unsafe)

        self.assertEqual(outcome.status, "succeeded")
        stored = signals[0].value
        self.assertEqual(stored["short_rationale"], ANALYSIS_RATIONALE_WITHHELD)
        for key in ("rumination_score", "negative_valence", "urgency_level", "ideation_indirect",
                    "ideation_direct", "consumption_crisis", "ambivalence", "emotional_complexity"):
            self.assertEqual(stored[key], LINGUISTIC[key], key)

        self.assertEqual(len(audits), 1)
        entry = audits[0]
        self.assertEqual(entry["action"], "llm_output_blocked")
        self.assertEqual(entry["entity_type"], "agent2_analysis_trace")
        self.assertEqual(entry["entity_id"], trace.id)
        self.assertEqual(entry["extra"]["validator_version"], "analysis-output-validation-v1")
        self.assertEqual(entry["extra"]["fields"], ["short_rationale"])
        self.assertEqual(entry["extra"]["violations"], ["risk_level_claim", "unapproved_contact"])
        self.assertNotIn("600", repr(entry))

    def test_unsafe_portrait_and_threads_become_no_change(self):
        update = {
            "portrait": "Persona sin riesgo actual que trabaja de noche.",
            "open_threads": [
                {"topic": "Trabajo", "note": "Turnos de noche."},
                {"topic": "Regulación", "note": "Probar gomas elásticas en la muñeca."},
            ],
        }
        _outcome, signals, audits, updates, _trace = self._run(profile_update=update)

        self.assertEqual(signals[0].value["short_rationale"], LINGUISTIC["short_rationale"])
        self.assertEqual(updates, [{"portrait": "", "open_threads": []}])
        self.assertEqual(audits[0]["extra"]["fields"], ["portrait", "open_threads"])
        self.assertEqual(audits[0]["extra"]["violations"], ["risk_level_claim", "forbidden_technique"])
        self.assertNotIn("noche", repr(audits))

    def test_clean_profile_update_passes_through(self):
        update = {"portrait": "Trabaja de noche y vive con su hermana.",
                  "open_threads": [{"topic": "Trabajo", "note": "Turnos de noche."}]}
        _outcome, _signals, audits, updates, _trace = self._run(profile_update=dict(update))
        self.assertEqual(updates, [update])
        self.assertEqual(audits, [])

    def test_audit_failure_does_not_cost_the_signal(self):
        unsafe = dict(LINGUISTIC, short_rationale="Nivel de riesgo alto.")

        def _boom(_db, **_kw):
            raise RuntimeError("audit down")

        value = {"linguistic": unsafe, "psychosocial": {"has_psychosocial_content": False, "observations": []}}
        result = StructuredAnalysisResult(value=value, metadata=ProviderMetadata(provider="anthropic", requested_model="stub"))
        db = MagicMock()
        trace = SimpleNamespace(id=uuid.uuid4(), status="started", error_code=None)
        with patch.object(conversation.agent2_trace, "start", return_value=trace), \
             patch.object(conversation.agent2_trace, "mark_succeeded", lambda *_a, **_k: None), \
             patch.object(conversation, "get_llm_provider",
                          return_value=SimpleNamespace(analyze_structured=lambda *_a, **_k: result)), \
             patch.object(conversation.clinical_memory, "formulation_for_analyzer", return_value=""), \
             patch.object(conversation.profile_service, "get", return_value=None), \
             patch.object(conversation.profile_service, "refresh_linguistic_baseline", lambda *_a, **_k: None), \
             patch.object(conversation.profile_service, "apply_analyzer_update", lambda *_a, **_k: None), \
             patch.object(conversation.audit, "log", _boom):
            outcome = conversation.analyze_text_and_store(
                db, uuid.uuid4(), "texto de prueba suficientemente largo para analizar",
                source_type="diary_entry", source_id=uuid.uuid4(), correlation_id=uuid.uuid4(),
            )
        self.assertEqual(outcome.status, "succeeded")
        self.assertEqual(outcome.value["short_rationale"], ANALYSIS_RATIONALE_WITHHELD)


if __name__ == "__main__":
    unittest.main()
