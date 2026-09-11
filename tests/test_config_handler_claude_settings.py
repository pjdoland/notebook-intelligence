# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""ConfigHandler.post merges ``claude_settings`` onto the stored value.

The Claude settings panel posts a fixed set of keys on mount. Replacing the
stored dict with that payload erased any key the panel does not render, such
as ``jupyter_ui_tools_external``, which is set by hand in config.json.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from notebook_intelligence.feature_flags import POLICY_FORCE_OFF


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


def _post(config, body, feature_policies=None, string_overrides=None):
    from notebook_intelligence.extension import ConfigHandler

    handler = MagicMock(spec=ConfigHandler)
    handler.request = MagicMock()
    handler.request.body = json.dumps(body).encode()
    handler.feature_policies = feature_policies or {}
    handler.string_overrides = string_overrides or {}
    config.set_feature_policies(handler.feature_policies, handler.string_overrides)
    manager = SimpleNamespace(
        nbi_config=config,
        default_chat_participant=None,
        update_models_from_config=MagicMock(),
        restart_acp_client=MagicMock(),
    )
    with patch("notebook_intelligence.extension.ai_service_manager", manager), \
         patch("notebook_intelligence.extension.perf.configure"):
        ConfigHandler.post(handler)
    return config.user_config["claude_settings"]


class TestClaudeSettingsPostMergesStoredKeys:
    def test_a_hand_set_key_survives_the_panel_payload(self, mock_nbi_config):
        mock_nbi_config.user_config["claude_settings"] = {
            "enabled": True,
            "jupyter_ui_tools_external": True,
        }

        stored = _post(mock_nbi_config, {"claude_settings": PANEL_PAYLOAD})

        assert stored["jupyter_ui_tools_external"] is True

    def test_posted_keys_still_override_stored_values(self, mock_nbi_config):
        mock_nbi_config.user_config["claude_settings"] = {
            "chat_model": "claude-old",
            "show_turn_usage": True,
        }

        stored = _post(mock_nbi_config, {
            "claude_settings": {**PANEL_PAYLOAD, "chat_model": "claude-new"},
        })

        assert stored["chat_model"] == "claude-new"
        assert stored["show_turn_usage"] is False

    def test_a_policy_still_clamps_the_merged_value(self, mock_nbi_config):
        """A stored value the POST does not mention must not slip past a
        forced policy just because it came from the stored side."""
        mock_nbi_config.user_config["claude_settings"] = {
            "enabled": True,
            "continue_conversation": True,
        }
        body = {"claude_settings": {"enabled": True}}

        stored = _post(
            mock_nbi_config, body,
            feature_policies={"claude_continue_conversation": POLICY_FORCE_OFF},
        )

        assert stored["continue_conversation"] is False

    def test_env_api_key_still_scrubs_a_stale_stored_key(self, mock_nbi_config):
        """The merge must not resurrect a stored credential that the
        ANTHROPIC_API_KEY override keeps out of config.json."""
        mock_nbi_config.user_config["claude_settings"] = {"api_key": "sk-stale"}
        body = {"claude_settings": {"enabled": True}}

        stored = _post(
            mock_nbi_config, body, string_overrides={"claude_api_key": "sk-env"},
        )

        assert stored["api_key"] == ""
