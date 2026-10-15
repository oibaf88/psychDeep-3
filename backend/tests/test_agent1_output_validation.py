"""Agent 1 output validation (G3): unsafe model text is withheld, replaced by
server-owned support and audited by rule code only.
"""
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.content.safety_resources import (
    AGENT1_OUTPUT_BLOCKED_MESSAGE,
    LEVEL3_PATIENT_MESSAGE,
    LEVEL4_PATIENT_MESSAGE,
)
from app.models import AuditLog
from app.services import conversation, output_validation, risk_engine
from app.services.conversation import AnalysisOutcome
from app.services.llm.base import ChatResult, ProviderMetadata


def codes(text):
    return output_validation.validate_agent1_output(text).violations


class ValidatorRuleTests(unittest.TestCase):
    def test_ordinary_supportive_replies_pass(self):
        for text in (
            "Te leo. Parece que hoy ha sido un día largo. ¿Quieres contarme qué pasó?",
            "Puedes probar la respiración 4-7-8 durante 10 minutos, a unas 6 respiraciones por minuto.",
            "Romper el hielo con alguien nuevo cuesta. ¿Qué te ayudaría ahora?",
            "Si lo necesitas, la Línea 024 está disponible las 24 horas, y el 112 para emergencias.",
            "",
        ):
            with self.subTest(text=text):
                self.assertEqual(codes(text), [])

    def test_risk_level_claims_are_blocked(self):
        for text in (
            "Tu nivel de riesgo ahora es bajo.",
            "Por lo que cuentas, no hay riesgo.",
            "No estás en riesgo, tranquilo.",
            "Esto sería una alerta nivel 3.",
            "Tu riesgo es moderado.",
            "Sin ningún riesgo por ahora.",
        ):
            with self.subTest(text=text):
                self.assertIn("risk_level_claim", codes(text))

    def test_phone_numbers_outside_server_resources_are_blocked(self):
        self.assertIn("unapproved_contact", codes("Llama al 900 123 456, te atenderán."))
        self.assertIn("unapproved_contact", codes("Puedes llamar al 016 cuando quieras."))
        self.assertIn("unapproved_contact", codes("Escribe al +34 612 345 678."))
        self.assertEqual(codes("Llama al 024 o al 112."), [])

    def test_doses_are_blocked(self):
        self.assertIn("dosage_instruction", codes("Con 1,5 ml sería suficiente."))
        self.assertIn("dosage_instruction", codes("Toma 50 mg antes de dormir."))
        self.assertIn("dosage_instruction", codes("No pases de 2 gramos."))

    def test_excluded_techniques_are_blocked(self):
        self.assertIn("forbidden_technique", codes("Prueba a ponerte hielo en la cara."))
        self.assertIn("forbidden_technique", codes("Sumerge las manos en agua helada."))
        self.assertIn("forbidden_technique", codes("Haz chasquear una goma elástica."))

    def test_audit_payload_carries_codes_not_text(self):
        check = output_validation.validate_agent1_output("Tu nivel de riesgo es bajo.")
        extra = check.audit_extra(alert_level=0)
        self.assertEqual(extra["violations"], ["risk_level_claim"])
        self.assertEqual(extra["validator_version"], output_validation.VALIDATOR_VERSION)
        self.assertNotIn("Tu nivel", str(extra))


def _db():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    def assign_primary_key(instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()

    db.refresh.side_effect = assign_primary_key
    return db


def _provider(text):
    return SimpleNamespace(
        chat=MagicMock(
            return_value=ChatResult(
                text=text,
                metadata=ProviderMetadata(provider="openai_compatible", requested_model="m", response_model="m"),
            )
        )
    )


class GetReplyIntegrationTests(unittest.TestCase):
    def _reply(self, level, model_text, has_professional=False):
        db = _db()
        assessment = SimpleNamespace(alert_level=level, assessment_reason="synthetic", input_signals={})
        analysis = AnalysisOutcome(uuid.uuid4(), None, None, "succeeded", None)
        with (
            patch.object(conversation, "analyze_text_and_store", return_value=analysis),
            patch.object(risk_engine, "run_and_persist", return_value=assessment),
            patch.object(conversation, "get_llm_provider", return_value=_provider(model_text)),
            patch.object(conversation, "_has_active_professional", return_value=has_professional),
            patch.object(conversation.agent1_context, "build", return_value="CONTEXTO SINTÉTICO"),
        ):
            reply = conversation.get_reply(db, SimpleNamespace(id=uuid.uuid4()), "mensaje sintético")
        added = [call.args[0] for call in db.add.call_args_list]
        audits = [row for row in added if isinstance(row, AuditLog)]
        assistant = [row for row in added if getattr(row, "role", None) == "assistant"]
        return reply, audits, assistant

    def test_unsafe_normal_reply_is_replaced_and_audited(self):
        reply, audits, assistant = self._reply(0, "Tranquilo, no hay riesgo. Toma 1 ml y llama al 600 111 222.")
        self.assertEqual(reply["reply"], AGENT1_OUTPUT_BLOCKED_MESSAGE)
        self.assertEqual(reply["ui_mode"], "normal")
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0].action, output_validation.AUDIT_ACTION)
        self.assertEqual(
            audits[0].extra["violations"], ["risk_level_claim", "unapproved_contact", "dosage_instruction"]
        )
        self.assertEqual(audits[0].extra["alert_level"], 0)
        self.assertNotIn("600 111 222", str(audits[0].extra))
        # The stored turn is the server-owned copy and claims no model provenance.
        self.assertEqual(len(assistant), 1)
        self.assertEqual(assistant[0].content, AGENT1_OUTPUT_BLOCKED_MESSAGE)
        self.assertIsNone(getattr(assistant[0], "model", None))

    def test_safe_normal_reply_passes_untouched(self):
        reply, audits, _ = self._reply(1, "Te leo. ¿Qué ha sido lo más difícil hoy?")
        self.assertEqual(reply["reply"], "Te leo. ¿Qué ha sido lo más difícil hoy?")
        self.assertEqual(audits, [])

    def test_level4_unsafe_prose_is_dropped_but_fixed_crisis_copy_stays(self):
        reply, audits, _ = self._reply(4, "Tu nivel de riesgo es alto. Llama al 900 000 000.")
        self.assertEqual(reply["reply"], LEVEL4_PATIENT_MESSAGE)
        self.assertEqual(reply["ui_mode"], "crisis")
        self.assertTrue(reply["resources"])
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0].extra["alert_level"], 4)

    def test_level3_unsafe_prose_is_dropped_but_fixed_copy_stays(self):
        reply, audits, _ = self._reply(3, "Ponte hielo en la cara un rato.")
        self.assertEqual(reply["reply"], LEVEL3_PATIENT_MESSAGE)
        self.assertEqual(audits[0].extra["violations"], ["forbidden_technique"])

    def test_level4_safe_prose_is_kept_before_fixed_copy(self):
        reply, audits, _ = self._reply(4, "Estoy aquí contigo.")
        self.assertEqual(reply["reply"], "Estoy aquí contigo.\n\n" + LEVEL4_PATIENT_MESSAGE)
        self.assertEqual(audits, [])


if __name__ == "__main__":
    unittest.main()
