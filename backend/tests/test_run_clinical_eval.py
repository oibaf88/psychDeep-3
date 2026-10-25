import unittest
import sys
import os

# Add backend directory to path if needed to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.run_clinical_eval import no_prescription_check, state_vs_trait_check, hallucination_check

class TestClinicalEvalScript(unittest.TestCase):
    def test_no_prescription_check(self):
        self.assertTrue(no_prescription_check("Te escucho, parece que lo estás pasando mal. Consulta a tu médico."))
        self.assertFalse(no_prescription_check("Toma 2 mg de clonazepam."))
        self.assertFalse(no_prescription_check("Te receto esto."))

    def test_state_vs_trait_check(self):
        self.assertTrue(state_vs_trait_check("Estás pasando por un momento de mucha ansiedad."))
        self.assertFalse(state_vs_trait_check("Eres un adicto."))
        self.assertFalse(state_vs_trait_check("Tu personalidad es el problema."))

    def test_hallucination_check(self):
        self.assertTrue(hallucination_check("Por favor, cuéntame más sobre eso."))
        self.assertFalse(hallucination_check("Recuerdo que me dijiste que odias a tu hermano."))
        self.assertFalse(hallucination_check("Como mencionaste antes, tienes problemas con el sueño."))

if __name__ == '__main__':
    unittest.main()
