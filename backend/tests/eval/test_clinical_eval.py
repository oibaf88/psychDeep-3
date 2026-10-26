import json
import os
import unittest
from unittest.mock import patch

from app.content.prompts import AGENT1_SYSTEM_PROMPT, ANALYZER_SYSTEM_PROMPT, AGENT3_SYSTEM_PROMPT
from app.services.llm import build_provider
from app.services.llm.base import ChatResult, ProviderMetadata, StructuredAnalysisResult
from app.services.llm_config import ResolvedConfig


def get_system_prompt_for_agent(agent):
    if agent == "agent1":
        return AGENT1_SYSTEM_PROMPT
    elif agent == "analyzer":
        return ANALYZER_SYSTEM_PROMPT
    elif agent == "agent3":
        return AGENT3_SYSTEM_PROMPT
    else:
        raise ValueError(f"Unknown agent: {agent}")


class ClinicalEvaluationTests(unittest.TestCase):
    def setUp(self):
        eval_cases_path = os.path.join(os.path.dirname(__file__), "eval_cases.json")
        with open(eval_cases_path, "r") as f:
            self.cases = json.load(f)

        self.config = ResolvedConfig(
            provider="openai",
            chat_model="gpt-3.5-turbo",
            analysis_model="gpt-3.5-turbo",
            copilot_model="gpt-3.5-turbo",
            api_key=os.environ.get("OPENAI_API_KEY", "dummy"),
            max_tokens=1024,
            timeout_seconds=30
        )

    def test_all_clinical_evaluations(self):
        is_mock = not bool(os.environ.get("OPENAI_API_KEY"))

        if is_mock:
            self.skipTest("Skipping real LLM evaluation in CI environment without OPENAI_API_KEY.")
        else:
            provider = build_provider(self.config)

            for case in self.cases:
                with self.subTest(case_id=case["id"]):
                    sys_prompt = get_system_prompt_for_agent(case["agent"])

                    output = ""
                    if case.get("type") == "structured":
                        res = provider.analyze_structured(
                            system_prompt=sys_prompt,
                            user_text=case["input"],
                            tool_schema={"name": "test_schema", "input_schema": case["schema"]}
                        )
                        output = json.dumps(res.value)
                    else:
                        res = provider.chat(
                            system_prompt=sys_prompt,
                            messages=[{"role": "user", "content": case["input"]}]
                        )
                        output = res.text

                    output_lower = output.lower()
                    for forbidden in case.get("forbidden", []):
                        self.assertNotIn(
                            forbidden.lower(),
                            output_lower,
                            f"Case {case['id']} failed: Contains forbidden phrase '{forbidden}' in output: {output}"
                        )

                    for required in case.get("required", []):
                        self.assertIn(
                            required.lower(),
                            output_lower,
                            f"Case {case['id']} failed: Missing required phrase '{required}' in output: {output}"
                        )
