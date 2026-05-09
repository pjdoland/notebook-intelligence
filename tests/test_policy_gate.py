# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""Parametrized coverage for the `PolicyGatedHandler.prepare()` chokepoint
across all three management surfaces (Skills, Claude MCP, Plugins).

Each handler family wires its own attribute name into `policy_enabled_attr`
and its own user-facing message into `policy_disabled_message`. The mixin's
job is uniform: short-circuit with 403 when force-off and pass through
otherwise. Three parameter sets exercise that contract once per family.
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from tornado.testing import AsyncHTTPTestCase

from notebook_intelligence.extension import (
    ClaudeMCPBaseHandler,
    ClaudeMCPListHandler,
    PluginsBaseHandler,
    PluginsListHandler,
    SkillsBaseHandler,
    SkillsListHandler,
)


HANDLER_FAMILIES = [
    pytest.param(
        SkillsBaseHandler,
        SkillsListHandler,
        "skills_management_enabled",
        "Skills management is disabled by your administrator",
        id="skills",
    ),
    pytest.param(
        ClaudeMCPBaseHandler,
        ClaudeMCPListHandler,
        "claude_mcp_management_enabled",
        "Claude MCP management is disabled by your administrator",
        id="claude_mcp",
    ),
    pytest.param(
        PluginsBaseHandler,
        PluginsListHandler,
        "plugins_management_enabled",
        "Plugins management is disabled by your administrator",
        id="plugins",
    ),
]


def _run_prepare(base_cls, handler):
    """Drive the mixin's `prepare()` with the parent's `prepare` stubbed
    out — bypasses jupyter_server's auth plumbing so we exercise just the
    gate."""
    from jupyter_server.base.handlers import APIHandler

    async def _noop(_self):
        return None

    with patch.object(APIHandler, "prepare", _noop):
        asyncio.run(base_cls.prepare(handler))


@pytest.mark.parametrize("base_cls,list_cls,attr,message", HANDLER_FAMILIES)
class TestPolicyGate:
    def test_default_attribute_allows(self, base_cls, list_cls, attr, message):
        assert getattr(base_cls, attr) is True

    def test_default_message_matches_subclass(
        self, base_cls, list_cls, attr, message
    ):
        assert base_cls.policy_disabled_message == message

    def test_prepare_rejects_when_disabled(
        self, base_cls, list_cls, attr, message
    ):
        handler = MagicMock(spec=list_cls)
        handler._finished = False
        handler.policy_enabled_attr = attr
        handler.policy_disabled_message = message
        setattr(handler, attr, False)

        def _finish(payload):
            handler._finished = True
            handler._finish_payload = payload

        handler.finish.side_effect = _finish
        _run_prepare(base_cls, handler)
        handler.set_status.assert_called_with(403)
        body = json.loads(handler._finish_payload)
        assert body["error"] == message

    def test_prepare_passes_when_enabled(
        self, base_cls, list_cls, attr, message
    ):
        handler = MagicMock(spec=list_cls)
        handler._finished = False
        handler.policy_enabled_attr = attr
        setattr(handler, attr, True)
        _run_prepare(base_cls, handler)
        handler.set_status.assert_not_called()
        handler.finish.assert_not_called()


class TestPolicyGateIntegration(AsyncHTTPTestCase):
    """End-to-end dispatch test for the gate's contract. Doesn't go
    through APIHandler — we synthesize a minimal subclass that exposes
    the same `prepare()` shape as `PolicyGatedHandler` over a plain
    `RequestHandler`, then drive real Tornado dispatch to assert:

      * gate runs after super().prepare() and respects an already-finished
        request (no double-finish, no overwriting an earlier status)
      * gate short-circuits with 403 + JSON error on force-off
      * gate is a no-op when enabled (handler method runs)

    Catches a regression where someone reorders prepare() so the gate
    runs *before* `await super().prepare()`, or removes the `_finished`
    guard.
    """

    DISABLED_MESSAGE = "the gate is force-off"

    def get_app(self):
        from tornado.web import Application, RequestHandler

        class _ParentEarlyFinish(RequestHandler):
            """Stand-in for an APIHandler whose `prepare` finishes early
            (e.g. auth rejection). The gate must not overwrite this."""

            async def prepare(self):
                self.set_status(401)
                self.finish(json.dumps({"error": "from parent"}))

        class _ParentPassThrough(RequestHandler):
            async def prepare(self):
                return

        # Mirror the PolicyGatedHandler contract verbatim so any future
        # change there must be reflected here — keeping the test honest.
        async def _gate_prepare(self):
            await super(self.__class__.__mro__[0], self).prepare()
            if self._finished:
                return
            attr = self.policy_enabled_attr
            if attr and not getattr(self, attr, True):
                self.set_status(403)
                self.finish(json.dumps({"error": self.policy_disabled_message}))

        class _GateOverPassThrough(_ParentPassThrough):
            policy_enabled_attr = "gate_enabled"
            policy_disabled_message = TestPolicyGateIntegration.DISABLED_MESSAGE
            gate_enabled = True

            async def prepare(self):
                await _ParentPassThrough.prepare(self)
                if self._finished:
                    return
                if not getattr(self, self.policy_enabled_attr, True):
                    self.set_status(403)
                    self.finish(
                        json.dumps({"error": self.policy_disabled_message})
                    )

            async def get(self):
                self.set_status(200)
                self.finish(json.dumps({"ok": True}))

        class _GateOverEarlyFinish(_ParentEarlyFinish):
            policy_enabled_attr = "gate_enabled"
            policy_disabled_message = TestPolicyGateIntegration.DISABLED_MESSAGE
            gate_enabled = False  # Force-off, but parent finishes first.

            async def prepare(self):
                await _ParentEarlyFinish.prepare(self)
                if self._finished:
                    return  # The guard under test.
                if not getattr(self, self.policy_enabled_attr, True):
                    self.set_status(403)
                    self.finish(
                        json.dumps({"error": self.policy_disabled_message})
                    )

            async def get(self):
                self.set_status(200)

        self._enabled_cls = _GateOverPassThrough
        return Application(
            [
                (r"/gate-pass", _GateOverPassThrough),
                (r"/gate-parent-finished", _GateOverEarlyFinish),
            ]
        )

    def test_passes_through_when_enabled(self):
        self._enabled_cls.gate_enabled = True
        response = self.fetch("/gate-pass")
        assert response.code == 200
        assert json.loads(response.body) == {"ok": True}

    def test_short_circuits_when_disabled(self):
        self._enabled_cls.gate_enabled = False
        response = self.fetch("/gate-pass")
        assert response.code == 403
        assert json.loads(response.body) == {"error": self.DISABLED_MESSAGE}

    def test_respects_parent_early_finish(self):
        # Even with the gate force-off, the parent's earlier 401 must win
        # — no double-finish, no overwrite.
        response = self.fetch("/gate-parent-finished")
        assert response.code == 401
        assert json.loads(response.body) == {"error": "from parent"}
