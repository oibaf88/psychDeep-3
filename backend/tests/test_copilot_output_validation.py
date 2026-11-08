"""Agent 3 (professional copilot) output validation (G3).

The copilot answer is checked before the clinician sees it. A "no risk"
claim, an invented contact number or an excluded technique withholds the
model text, replaces it with server-owned copy and writes an audit row with
rule codes only. Stated engine levels and patient-reported quantities stay
allowed for a professional reader.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.models import AuditLog, TherapistCopilotMessage
from app.models_vnext import ModelRun
from app.services import clinical_copilot, output_validation
from app.services.llm.base import ProviderMetadata, StructuredAnalysisError
from tests.test_clinical_copilot import COPILOT_MODEL, _fake_provider, _patient, _populated_db, _professional


def codes(text):
    return output_validation.validate_copilot_output(text).violations


class CopilotRuleTests(unittest.TestCase):
    def test_ordinary_clinical_summaries_pass(self):
        for text in (
            "Según el motor determinista, el nivel de alerta actual es 2 (regla R-07).",
            "Refiere haber consumido 2 ml de GHB el sábado; conviene explorarlo en sesión.",
            "El craving medio sube frente a su referencia personal; la evidencia es parcial.",
            "Si hay crisis, los recursos aprobados son la Línea 024 y el 112.",
            "",
        ):
            with self.subTest(text=text):
                self.assertEqual(codes(text), [])

    def test_no_risk_claims_are_blocked(self):
        for text in (
            "El paciente no presenta riesgo.",
            "No hay riesgo en este momento.",
            "No está en riesgo.",
            "Riesgo nulo según lo que cuenta.",
            "Sin riesgo aparente.",
        ):
            with self.subTest(text=text):
                self.assertIn("no_risk_claim", codes(text))

    def test_invented_contacts_are_blocked(self):
        self.assertIn("unapproved_contact", codes("Puede derivarle al 900 123 456."))
        self.assertIn("unapproved_contact", codes("Puede llamar al 016 si lo necesita."))
        self.assertEqual(codes("Recuérdale el 024 y el 112."), [])

    def test_excluded_techniques_are_blocked(self):
        self.assertIn("forbidden_technique", codes("Sugiérele sumergir la cara en agua helada."))
        self.assertIn("forbidden_technique", codes("Puede usar una goma elástica en la muñeca."))

    def test_agent1_rules_are_unchanged(self):
        self.assertIn("risk_level_claim", output_validation.validate_agent1_output("Tu nivel de riesgo es bajo.").violations)
        self.assertIn("dosage_instruction", output_validation.validate_agent1_output("Toma 50 mg.").violations)

    def test_version_is_recorded(self):
        check = output_validation.validate_copilot_output("No hay riesgo.")
        self.assertEqual(check.validator_version, output_validation.COPILOT_VALIDATOR_VERSION)


class _AskHarness:
    def _ask(self, reply):
        db = _populated_db()
        patient = _patient()
        with patch.object(clinical_copilot, "build_provider", return_value=_fake_provider(reply)):
            answer = clinical_copilot.ask(
                db, professional=_professional(), patient=patient, question="¿Cómo está?"
            )
        return db, patient, answer


class CopilotAskTests(_AskHarness, unittest.TestCase):
    def test_unsafe_answer_is_withheld_and_replaced(self):
        unsafe = "El paciente no presenta riesgo; que llame al 900 123 456."
        db, _patient_, answer = self._ask(unsafe)
        self.assertEqual(answer.content, clinical_copilot.COPILOT_OUTPUT_BLOCKED_MESSAGE)
        self.assertEqual(answer.error_kind, output_validation.AUDIT_ACTION)
        stored = [row.content for row in db.added if isinstance(row, TherapistCopilotMessage)]
        self.assertNotIn(unsafe, stored)

    def test_withheld_answer_is_audited_by_code_only(self):
        unsafe = "El paciente no presenta riesgo; que llame al 900 123 456."
        db, patient, answer = self._ask(unsafe)
        audits = [row for row in db.added if isinstance(row, AuditLog)]
        self.assertEqual(len(audits), 1)
        row = audits[0]
        self.assertEqual(row.action, "llm_output_blocked")
        self.assertEqual(row.entity_type, "therapist_copilot_message")
        self.assertEqual(row.entity_id, str(answer.id))
        self.assertEqual(row.extra["violations"], ["no_risk_claim", "unapproved_contact"])
        self.assertEqual(row.extra["validator_version"], output_validation.COPILOT_VALIDATOR_VERSION)
        self.assertEqual(row.extra["audience"], "professional")
        self.assertEqual(row.extra["patient_id"], str(patient.id))
        self.assertNotIn("presenta", str(row.extra))
        self.assertNotIn("900", str(row.extra))

    def test_safe_answer_passes_without_audit(self):
        db, _patient_, answer = self._ask("Nivel de alerta 2 según el motor; evidencia parcial.")
        self.assertEqual(answer.content, "Nivel de alerta 2 según el motor; evidencia parcial.")
        self.assertIsNone(answer.error_kind)
        self.assertFalse([row for row in db.added if isinstance(row, AuditLog)])

    def test_validation_never_writes_clinical_records(self):
        # ModelRun is model-governance metadata (codes and hashes), not a
        # clinical record.
        db, _patient_, _answer = self._ask("No hay riesgo.")
        for row in db.added:
            self.assertIsInstance(row, (TherapistCopilotMessage, AuditLog, ModelRun))


def _stored(run) -> str:
    return " ".join(str(getattr(run, column.key, "")) for column in ModelRun.__table__.columns)


class CopilotModelRunTests(_AskHarness, unittest.TestCase):
    """Validated copilot answers write succeeded or output_withheld. Provider
    failures write an existing failure status and leave the explained turn."""

    def _run(self, db):
        runs = [row for row in db.added if isinstance(row, ModelRun)]
        self.assertEqual(len(runs), 1)
        return runs[0]

    def _assert_no_dossier_text(self, run):
        stored = _stored(run)
        for fragment in ("presenta", "900", "¿Cómo está?", "Paciente Demo", "mal día", "provider down", "empty_reply"):
            self.assertNotIn(fragment, stored)

    def test_withheld_answer_records_output_withheld_run(self):
        unsafe = "El paciente no presenta riesgo; que llame al 900 123 456."
        db, patient, answer = self._ask(unsafe)
        run = self._run(db)
        self.assertEqual(run.status, "output_withheld")
        self.assertEqual(run.purpose, "agent3_copilot")
        self.assertEqual(run.audience, "professional")
        self.assertEqual(run.user_id, patient.id)
        self.assertEqual(run.correlation_id, answer.id)
        self.assertEqual(run.prompt_version, clinical_copilot.AGENT3_PROMPT_VERSION)
        self.assertEqual(run.output_validator_version, output_validation.COPILOT_VALIDATOR_VERSION)
        self.assertEqual(run.output_violation_codes, ["no_risk_claim", "unapproved_contact"])
        self.assertEqual(len(run.input_hash), 64)
        stored = " ".join(str(getattr(run, col.key, "")) for col in ModelRun.__table__.columns)
        for fragment in ("presenta", "900", "¿Cómo está?", "Paciente Demo", "mal día"):
            self.assertNotIn(fragment, stored)

    def test_clean_answer_records_succeeded_run(self):
        db, _patient_, answer = self._ask("Nivel de alerta 2 según el motor; evidencia parcial.")
        run = self._run(db)
        self.assertEqual(run.status, "succeeded")
        self.assertEqual(run.output_violation_codes, [])
        self.assertIsNone(answer.error_kind)

    def test_provider_failure_records_provider_error_and_keeps_the_explained_turn(self):
        def _boom(*_args, **_kwargs):
            raise RuntimeError("provider down")

        db, patient, answer = self._ask(_boom)
        self.assertEqual(answer.error_kind, "RuntimeError")
        self.assertIn("No he podido generar la respuesta", answer.content)
        self.assertIn("(error del proveedor: RuntimeError)", answer.content)
        self.assertIn("check-ins, diario, chat", answer.content)
        self.assertNotIn("provider down", answer.content)
        self.assertEqual(answer.provider, clinical_copilot.llm_config.resolve(db).provider)
        run = self._run(db)
        self.assertEqual(run.status, "provider_error")
        self.assertEqual(run.purpose, "agent3_copilot")
        self.assertEqual(run.audience, "professional")
        self.assertEqual(run.user_id, patient.id)
        self.assertEqual(run.correlation_id, answer.id)
        self.assertEqual(run.prompt_version, clinical_copilot.AGENT3_PROMPT_VERSION)
        self.assertEqual(run.deployment_alias, f"direct-{answer.provider}")
        self.assertEqual(run.provider_type, answer.provider)
        self.assertEqual(run.model_id, COPILOT_MODEL)
        self.assertRegex(run.input_hash, r"^[0-9a-f]{64}$")
        self.assertIsNone(run.output_validator_version)
        self.assertIsNone(run.output_violation_codes)
        self._assert_no_dossier_text(run)

    def test_configuration_error_uses_exception_metadata_not_the_stored_turn(self):
        def _boom(*_args, **_kwargs):
            raise StructuredAnalysisError(
                "configuration_error",
                metadata=ProviderMetadata(
                    provider="anthropic",
                    requested_model="claude-test",
                    base_url="https://secret-tunnel.example/v1",
                    request_id="req-do-not-store",
                    latency_ms=17,
                ),
                error_code="http_401",
            )

        db, _patient_, answer = self._ask(_boom)
        self.assertEqual(answer.error_kind, "StructuredAnalysisError")
        self.assertIn("(error del proveedor: StructuredAnalysisError)", answer.content)
        self.assertNotIn("http_401", answer.content)
        self.assertNotIn("secret-tunnel", answer.content)
        self.assertEqual(answer.provider, clinical_copilot.llm_config.resolve(db).provider)
        run = self._run(db)
        self.assertEqual(run.status, "configuration_error")
        self.assertEqual(run.deployment_alias, "direct-anthropic")
        self.assertEqual(run.provider_type, "anthropic")
        self.assertEqual(run.model_id, "claude-test")
        self.assertEqual(run.latency_ms, 17)
        stored = _stored(run)
        for fragment in ("http_401", "secret-tunnel", "req-do-not-store", "Paciente Demo", "mal día"):
            self.assertNotIn(fragment, stored)

    def test_empty_reply_records_invalid_output_and_keeps_the_explained_turn(self):
        db, _patient_, answer = self._ask("   ")
        self.assertEqual(answer.error_kind, "RuntimeError")
        self.assertIn("No he podido generar la respuesta", answer.content)
        self.assertNotIn("empty_reply", answer.content)
        run = self._run(db)
        self.assertEqual(run.status, "invalid_output")
        self.assertIsNone(run.output_validator_version)
        self.assertIsNone(run.output_violation_codes)
        self.assertNotIn("empty_reply", _stored(run))
        self._assert_no_dossier_text(run)

    def test_provider_construction_failure_records_configuration_error(self):
        db = _populated_db()
        with patch.object(
            clinical_copilot,
            "build_provider",
            side_effect=RuntimeError("LOCAL_ENDPOINT_HOST_NOT_APPROVED"),
        ):
            answer = clinical_copilot.ask(
                db, professional=_professional(), patient=_patient(), question="¿Cómo está?"
            )
        self.assertEqual(answer.error_kind, "RuntimeError")
        self.assertIn("No he podido generar la respuesta", answer.content)
        self.assertNotIn("LOCAL_ENDPOINT_HOST_NOT_APPROVED", answer.content)
        run = self._run(db)
        self.assertEqual(run.status, "configuration_error")
        self.assertEqual(run.deployment_alias, f"direct-{answer.provider}")
        active = clinical_copilot.llm_config.resolve(db)
        configured = (active.chat_model or active.copilot_model or "").strip()
        self.assertEqual(run.model_id, configured or "unknown")
        self.assertNotIn("LOCAL_ENDPOINT_HOST_NOT_APPROVED", _stored(run))
        self._assert_no_dossier_text(run)

    def test_recording_failure_keeps_the_explained_turn(self):
        def _boom(*_args, **_kwargs):
            raise RuntimeError("provider down")

        with patch("app.services.reply_model_run.get_settings", side_effect=RuntimeError("db down")):
            db, _patient_, answer = self._ask(_boom)
        self.assertEqual(answer.error_kind, "RuntimeError")
        self.assertIn("No he podido generar la respuesta", answer.content)
        self.assertNotIn("db down", answer.content)
        self.assertNotIn("provider down", answer.content)
        self.assertEqual([row for row in db.added if isinstance(row, ModelRun)], [])

    def test_local_access_denial_writes_no_failure_run(self):
        db = _populated_db()
        professional = _professional()
        professional.local_llm_approved = False
        local_config = SimpleNamespace(provider="openai_compatible", is_local=True, chat_model="lm")
        with patch.object(clinical_copilot.llm_config, "resolve", return_value=local_config):
            answer = clinical_copilot.ask(
                db, professional=professional, patient=_patient(), question="¿Cómo está?"
            )
        self.assertEqual(answer.error_kind, "LocalLlmAccessDenied")
        self.assertIn("administrador clínico", answer.content)
        self.assertEqual([row for row in db.added if isinstance(row, ModelRun)], [])


if __name__ == "__main__":
    unittest.main()
