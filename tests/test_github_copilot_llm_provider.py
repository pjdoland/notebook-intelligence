from unittest.mock import patch, MagicMock

import pytest

from notebook_intelligence import github_copilot as gh_copilot
from notebook_intelligence.llm_providers.github_copilot_llm_provider import GitHubCopilotLLMProvider


@pytest.fixture(autouse=True)
def _reset_models_cache():
    gh_copilot.invalidate_copilot_models_cache()
    yield
    gh_copilot.invalidate_copilot_models_cache()


def test_chat_models_include_recent_github_copilot_models():
    provider = GitHubCopilotLLMProvider()

    models = {model.id: model for model in provider.chat_models}

    assert models["gpt-5.3-codex"].name == "GPT-5.3-Codex"
    assert models["claude-haiku-4.5"].name == "Claude Haiku 4.5"
    assert models["claude-sonnet-4.6"].name == "Claude Sonnet 4.6"
    assert models["claude-opus-4.6"].name == "Claude Opus 4.6"
    assert models["gemini-3.1-pro"].name == "Gemini 3.1 Pro"

    assert all(model.supports_tools for model in models.values())


def test_chat_models_use_dynamic_cache_when_populated():
    gh_copilot.copilot_models_cache.extend([
        {"id": "future-model-1", "name": "Future 1", "context_window": 200000},
        {"id": "future-model-2", "name": "Future 2", "context_window": 4096},
    ])

    provider = GitHubCopilotLLMProvider()
    ids = [m.id for m in provider.chat_models]

    assert ids == ["future-model-1", "future-model-2"]
    by_id = {m.id: m for m in provider.chat_models}
    assert by_id["future-model-1"].context_window == 200000
    assert by_id["future-model-2"].name == "Future 2"


def test_fetch_copilot_models_returns_empty_without_token():
    gh_copilot.github_auth["token"] = None
    assert gh_copilot.fetch_copilot_models() == []


def test_fetch_copilot_models_floors_zero_context_window_to_default():
    gh_copilot.github_auth["token"] = "fake-bearer-token"
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "data": [
            {
                "id": "no-limits-model",
                "name": "No Limits",
                "model_picker_enabled": True,
                "capabilities": {"type": "chat"},
            }
        ]
    }
    with patch("notebook_intelligence.github_copilot.requests.get", return_value=response):
        result = gh_copilot.fetch_copilot_models()

    assert result == [{
        "id": "no-limits-model",
        "name": "No Limits",
        "context_window": 4096,
    }]


def test_fetch_copilot_models_preserves_cache_on_empty_response():
    gh_copilot.github_auth["token"] = "fake-bearer-token"
    gh_copilot.copilot_models_cache.append({
        "id": "previously-cached",
        "name": "Cached",
        "context_window": 100000,
    })
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"data": []}

    with patch("notebook_intelligence.github_copilot.requests.get", return_value=response):
        result = gh_copilot.fetch_copilot_models()

    assert [m["id"] for m in result] == ["previously-cached"]
    assert [m["id"] for m in gh_copilot.copilot_models_cache] == ["previously-cached"]


def test_fetch_copilot_models_preserves_cache_on_http_failure():
    gh_copilot.github_auth["token"] = "fake-bearer-token"
    gh_copilot.copilot_models_cache.append({
        "id": "previously-cached",
        "name": "Cached",
        "context_window": 100000,
    })
    response = MagicMock(status_code=503, text="upstream down")

    with patch("notebook_intelligence.github_copilot.requests.get", return_value=response):
        result = gh_copilot.fetch_copilot_models()

    assert [m["id"] for m in result] == ["previously-cached"]
    assert [m["id"] for m in gh_copilot.copilot_models_cache] == ["previously-cached"]


def test_fetch_copilot_models_filters_to_picker_enabled_chat_models():
    gh_copilot.github_auth["token"] = "fake-bearer-token"
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "data": [
            {
                "id": "gpt-foo",
                "name": "GPT Foo",
                "model_picker_enabled": True,
                "capabilities": {
                    "type": "chat",
                    "limits": {"max_context_window_tokens": 64000},
                },
            },
            {
                "id": "gpt-foo-internal",
                "name": "GPT Foo Internal",
                "model_picker_enabled": False,
                "capabilities": {"type": "chat"},
            },
            {
                "id": "text-embed",
                "model_picker_enabled": True,
                "capabilities": {"type": "embedding"},
            },
            {
                "id": "gpt-foo",  # duplicate id is dropped
                "name": "GPT Foo Dup",
                "model_picker_enabled": True,
                "capabilities": {"type": "chat"},
            },
            {
                "id": "claude-bar",
                "model_picker_enabled": True,
                "capabilities": {
                    "type": "chat",
                    "limits": {"max_prompt_tokens": 128000},
                },
            },
        ]
    }

    with patch("notebook_intelligence.github_copilot.requests.get", return_value=response):
        result = gh_copilot.fetch_copilot_models()

    assert [m["id"] for m in result] == ["gpt-foo", "claude-bar"]
    assert result[0]["context_window"] == 64000
    assert result[1]["context_window"] == 128000
    # Falls back to id when name is missing.
    assert result[1]["name"] == "claude-bar"


def test_fetch_copilot_models_swallows_http_failure():
    gh_copilot.github_auth["token"] = "fake-bearer-token"
    response = MagicMock(status_code=500, text="oops")

    with patch("notebook_intelligence.github_copilot.requests.get", return_value=response):
        assert gh_copilot.fetch_copilot_models() == []
