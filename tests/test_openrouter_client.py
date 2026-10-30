import json

import httpx
import pytest

from app.config import Settings
from app.llm.base import LLMError
from app.llm.factory import get_llm_client
from app.llm.mock_client import MockLLMClient
from app.llm.openrouter_client import OpenRouterClient

VALID_CONTENT = json.dumps(
    {
        "suggestions": [
            {
                "title": "Omelette",
                "short_description": "Fluffy.",
                "missing_ingredients": [],
                "estimated_time_minutes": 10,
                "difficulty": "easy",
            },
        ]
    }
)


def _completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _client(handler) -> OpenRouterClient:
    http = httpx.Client(
        base_url="https://openrouter.test/api/v1", transport=httpx.MockTransport(handler)
    )
    return OpenRouterClient(api_key="test", model="test/model", base_url="", http_client=http)


def test_sends_json_mode_request_and_parses():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return _completion(f"```json\n{VALID_CONTENT}\n```")

    suggestions = _client(handler).suggest_recipes(["eggs"])

    assert [s.title for s in suggestions] == ["Omelette"]
    [body] = requests
    assert body["model"] == "test/model"
    assert body["response_format"] == {"type": "json_object"}
    assert "eggs" in body["messages"][1]["content"]


def test_retries_once_on_invalid_json():
    responses = iter([_completion("sorry, here you go"), _completion(VALID_CONTENT)])
    assert len(_client(lambda r: next(responses)).suggest_recipes(["eggs"])) == 1


def test_gives_up_after_two_invalid_responses():
    with pytest.raises(LLMError):
        _client(lambda r: _completion("nope")).suggest_recipes(["eggs"])


def test_http_error_becomes_llm_error():
    with pytest.raises(LLMError):
        _client(lambda r: httpx.Response(401, json={"error": "bad key"})).suggest_recipes(["eggs"])


def _settings(provider, key=None):
    return Settings("db", provider, key, "test/model", "https://openrouter.test/api/v1")


def test_factory_selects_backend():
    assert isinstance(get_llm_client(_settings("mock")), MockLLMClient)
    assert isinstance(get_llm_client(_settings("openrouter", "k")), OpenRouterClient)
    with pytest.raises(ValueError):
        get_llm_client(_settings("openrouter"))
    with pytest.raises(ValueError):
        get_llm_client(_settings("gpt"))
