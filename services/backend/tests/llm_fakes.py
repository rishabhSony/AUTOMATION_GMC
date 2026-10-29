"""Fake instructor client: returns canned Pass 1 / Pass 2 models instead of calling OpenAI."""

from pathlib import Path
from types import SimpleNamespace

from app.services.extractor import Pass1Extraction, Pass2Verification

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture_models() -> tuple[Pass1Extraction, Pass2Verification]:
    return (
        Pass1Extraction.model_validate_json((FIXTURES / "pass1_apex.json").read_text()),
        Pass2Verification.model_validate_json((FIXTURES / "pass2_apex.json").read_text()),
    )


class FakeCompletions:
    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[dict] = []

    def create_with_completion(self, *, response_model, messages, **kwargs):
        self.calls.append({"response_model": response_model, "messages": messages, **kwargs})
        usage = SimpleNamespace(prompt_tokens=1200, completion_tokens=300)
        return self.responses[response_model], SimpleNamespace(usage=usage)


class FakeInstructorClient:
    def __init__(self, pass1: Pass1Extraction, pass2: Pass2Verification):
        self.completions = FakeCompletions({Pass1Extraction: pass1, Pass2Verification: pass2})
        self.chat = SimpleNamespace(completions=self.completions)


def fake_client() -> FakeInstructorClient:
    return FakeInstructorClient(*load_fixture_models())
