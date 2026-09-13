from app.services.deterministic_safety_text import classify_explicit_declaration


def test_explicit_first_person_intent_is_detected_without_llm():
    result = classify_explicit_declaration("Quiero suicidarme")
    assert result is not None
    assert result.category == "ideation_active"
    assert result.rule_id.startswith("SAFETY_TEXT_DIRECT_")


def test_explicit_plan_is_detected_without_llm():
    result = classify_explicit_declaration("Tengo un plan para quitarme la vida")
    assert result is not None
    assert result.category == "planning"


def test_negated_statement_is_not_promoted_to_fact():
    assert classify_explicit_declaration("No quiero suicidarme") is None


def test_quoted_third_party_statement_is_not_promoted_to_fact():
    assert classify_explicit_declaration("En la noticia dice quiero suicidarme") is None


def test_ambiguous_distress_does_not_become_confirmed_suicidal_fact():
    assert classify_explicit_declaration("No puedo más con esta semana") is None
