# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""ConfigHandler.post merges ``claude_settings`` onto the stored value.

The Claude settings panel posts a fixed set of keys on mount. Replacing the
stored dict with that payload erased any key the panel does not render, such
as ``jupyter_ui_tools_external``, which is set by hand in config.json.
"""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from notebook_intelligence.feature_flags import (
    CLAUDE_CODE_TOOLS_ID,
    JUPYTER_UI_TOOLS_ID,
    POLICY_FORCE_OFF,
    POLICY_FORCE_ON,
)


# What the Claude settings tab sends when it mounts (settings-panel.tsx).
PANEL_PAYLOAD = {
    "enabled": True,
    "chat_model": "",
    "inline_chat_model": "",
    "inline_completion_model": "",
    "api_key": "",
    "base_url": "",
    "setting_sources": ["user"],
    "tools": [],
    "continue_conversation": False,
    "show_turn_usage": False,
}


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


@pytest.fixture
def config(mock_nbi_config, tmp_path):
    """Point every file NBIConfig.load() reads into tmp_path, so the handler's
    reload sees only what a test writes."""
    mock_nbi_config.env_config_file = str(tmp_path / "env" / "config.json")
    mock_nbi_config.env_mcp_file = str(tmp_path / "env" / "mcp.json")
    mock_nbi_config.deprecated_env_config_file = str(tmp_path / "deprecated-env.json")
    mock_nbi_config.deprecated_user_config_file = str(tmp_path / "deprecated-user.json")
    return mock_nbi_config


def _store(config, **user_config):
    """Write the user's config.json, as a hand edit would."""
    _write_json(config.user_config_file, user_config)


def _post(config, body, feature_policies=None, string_overrides=None):
    """POST ``body`` and return the ``claude_settings`` written to disk."""
    from notebook_intelligence.extension import ConfigHandler

    handler = MagicMock(spec=ConfigHandler)
    handler.request = MagicMock()
    handler.request.body = json.dumps(body).encode()
    handler.feature_policies = feature_policies or {}
    handler.string_overrides = string_overrides or {}
    manager = SimpleNamespace(
        nbi_config=config,
        default_chat_participant=None,
        update_models_from_config=MagicMock(),
        restart_acp_client=MagicMock(),
    )
    with patch("notebook_intelligence.extension.ai_service_manager", manager), \
         patch("notebook_intelligence.extension.perf.configure"):
        ConfigHandler.post(handler)
    handler.finish.assert_called_once_with("{}")
    with open(config.user_config_file) as f:
        return json.load(f)["claude_settings"]


class TestClaudeSettingsPostMergesStoredKeys:
    def test_a_hand_set_key_survives_the_panel_payload(self, config):
        _store(config, claude_settings={
            "enabled": True,
            "jupyter_ui_tools_external": True,
            "show_turn_usage": True,
        })

        stored = _post(config, {"claude_settings": PANEL_PAYLOAD})

        assert stored["jupyter_ui_tools_external"] is True
        assert stored["show_turn_usage"] is False

    def test_a_hand_edit_made_while_the_server_runs_survives(self, config):
        """The handler saves its whole in-memory config, so it has to reload
        config.json first or a stale copy overwrites the edit."""
        config.user_config = {"claude_settings": {"enabled": True}}
        _store(config, claude_settings={
            "enabled": True,
            "jupyter_ui_tools_external": True,
        })

        stored = _post(config, {"claude_settings": PANEL_PAYLOAD})

        assert stored["jupyter_ui_tools_external"] is True

    def test_posted_keys_still_override_stored_values(self, config):
        _store(config, claude_settings={
            "chat_model": "claude-old",
            "show_turn_usage": True,
        })

        stored = _post(config, {
            "claude_settings": {**PANEL_PAYLOAD, "chat_model": "claude-new"},
        })

        assert stored["chat_model"] == "claude-new"
        assert stored["show_turn_usage"] is False

    def test_a_posted_list_replaces_the_stored_list(self, config):
        """The merge is shallow, so unchecking a tool in the panel sticks."""
        _store(config, claude_settings={
            "tools": [CLAUDE_CODE_TOOLS_ID, JUPYTER_UI_TOOLS_ID],
            "setting_sources": ["user", "project"],
        })

        stored = _post(config, {"claude_settings": {
            **PANEL_PAYLOAD,
            "tools": [CLAUDE_CODE_TOOLS_ID],
            "setting_sources": ["user"],
        }})

        assert stored["tools"] == [CLAUDE_CODE_TOOLS_ID]
        assert stored["setting_sources"] == ["user"]

    def test_a_partial_post_keeps_the_stored_lists(self, config):
        """apply_claude_policies always writes tools and setting_sources, so
        the merge has to run before it or a POST without them empties both."""
        _store(config, claude_settings={
            "enabled": True,
            "tools": [CLAUDE_CODE_TOOLS_ID],
            "setting_sources": ["user", "project"],
        })

        stored = _post(config, {"claude_settings": {"show_turn_usage": True}})

        assert stored["tools"] == [CLAUDE_CODE_TOOLS_ID]
        assert stored["setting_sources"] == ["user", "project"]
        assert stored["show_turn_usage"] is True

    def test_a_forced_tool_is_added_to_the_stored_tools(self, config):
        _store(config, claude_settings={
            "enabled": True,
            "tools": [CLAUDE_CODE_TOOLS_ID],
        })

        stored = _post(
            config, {"claude_settings": {"enabled": True}},
            feature_policies={"claude_jupyter_ui_tools": POLICY_FORCE_ON},
        )

        assert stored["tools"] == [CLAUDE_CODE_TOOLS_ID, JUPYTER_UI_TOOLS_ID]

    def test_a_policy_still_clamps_a_stored_value(self, config):
        """Policies apply to the merged dict, so a stored value the POST does
        not mention cannot slip past a forced policy."""
        _store(config, claude_settings={
            "enabled": True,
            "continue_conversation": True,
        })

        stored = _post(
            config, {"claude_settings": {"enabled": True}},
            feature_policies={"claude_continue_conversation": POLICY_FORCE_OFF},
        )

        assert stored["continue_conversation"] is False

    def test_env_api_key_still_scrubs_a_stale_stored_key(self, config):
        """The ANTHROPIC_API_KEY scrub applies to the merged dict, so a stored
        credential is still kept out of config.json."""
        _store(config, claude_settings={"api_key": "sk-stale"})

        stored = _post(
            config, {"claude_settings": {"enabled": True}},
            string_overrides={"claude_api_key": "sk-env"},
        )

        assert stored["api_key"] == ""

    def test_a_key_from_the_environment_config_is_kept(self, config):
        """With no user value, NBIConfig.get falls back to the environment
        config, so the first POST copies its keys into the user config rather
        than dropping them."""
        _write_json(config.env_config_file, {
            "claude_settings": {"jupyter_ui_tools_external": True},
        })

        stored = _post(config, {"claude_settings": PANEL_PAYLOAD})

        assert stored["jupyter_ui_tools_external"] is True

    def test_acp_taking_over_keeps_a_hand_set_key(self, config):
        _store(
            config,
            claude_settings={"enabled": True, "jupyter_ui_tools_external": True},
            acp_settings={"enabled": False},
        )

        stored = _post(config, {
            "claude_settings": PANEL_PAYLOAD,
            "acp_settings": {"enabled": True},
        })

        assert stored["enabled"] is False
        assert stored["jupyter_ui_tools_external"] is True

    def test_a_null_stored_value_is_replaced_by_the_post(self, config):
        _store(config, claude_settings=None)

        stored = _post(config, {"claude_settings": PANEL_PAYLOAD})

        assert stored["show_turn_usage"] is False

    def test_a_null_post_does_not_raise(self, config):
        _store(config, claude_settings={"enabled": True})

        _post(config, {"claude_settings": None})
