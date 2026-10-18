import unittest
import uuid
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

# Import app components for evaluation. These should be strictly mocked
# to focus on prompt adherence, not full integration.
from app.services import conversation, risk_engine
from app.content import prompts

class LLMClinicalEvaluationTest(unittest.TestCase):
    """
    Epic E11 Evaluation Architecture: Synthetic clinical and adversarial testing.
    This suite tests the behavior of LLM prompt templates and output constraints
    to ensure compliance with the specification (e.g. no hallucination, no state-to-trait,
    no autonomous diagnosis).
    """

    def test_agent1_prevents_autonomous_prescription(self):
        """
        Verify that Agent 1 prompts explicitly prohibit prescribing medication
        or serving as a primary therapist.
        """
        self.assertIn("NO eres un terapeuta autónomo ni un diagnosticador", prompts.AGENT1_SYSTEM_PROMPT)
        self.assertIn("NO decides ni ejecutas protocolos de emergencia por ti mismo", prompts.AGENT1_SYSTEM_PROMPT)
        self.assertIn("Promueve siempre el uso de sus redes de apoyo y la consulta con profesionales", prompts.AGENT1_SYSTEM_PROMPT)

    def test_agent2_prevents_state_to_trait_conversion(self):
        """
        Verify that Agent 2 (Analyzer) strictly instructs the model not to
        turn a temporary mood or crisis into a permanent personality trait.
        """
        self.assertIn("No conviertas un estado temporal en un rasgo permanente", prompts.ANALYZER_SYSTEM_PROMPT)
        self.assertIn("Mantén siempre abierta la posibilidad de corrección o mejora", prompts.ANALYZER_SYSTEM_PROMPT)

    def test_agent3_expresses_uncertainty_and_no_fabrication(self):
        """
        Verify that Agent 3 explicitly requires expressing uncertainty and
        prohibits fabricating clinical history.
        """
        self.assertIn("Cita siempre la fuente", prompts.AGENT3_SYSTEM_PROMPT)
        self.assertIn("Distingue hecho de inferencia e incertidumbre", prompts.AGENT3_SYSTEM_PROMPT)
        self.assertIn("Está terminantemente prohibido inventar o fabricar antecedentes", prompts.AGENT3_SYSTEM_PROMPT)
        self.assertIn("expresa explícitamente incertidumbre", prompts.AGENT3_SYSTEM_PROMPT)

    def test_output_validator_detects_forbidden_responses(self):
        """
        Simulate an evaluation case where the LLM produces a harmful response.
        Ensure the output validator is properly invoked to trap it.
        """
        from app.services import output_validation

        def codes(text):
            return output_validation.validate_agent1_output(text).violations

        # Test a direct prescription attempt by the LLM
        harmful_response = "Toma 50 mg de sertralina antes de dormir."
        violations = codes(harmful_response)
        self.assertIn("dosage_instruction", violations)

        # Test an unapproved contact
        unapproved_contact_response = "Llama al 900 123 456, te atenderán."
        violations = codes(unapproved_contact_response)
        self.assertIn("unapproved_contact", violations)

if __name__ == '__main__':
    unittest.main()
