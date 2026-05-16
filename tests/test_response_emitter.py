"""Regression coverage for WebsocketCopilotResponseEmitter's IOLoop dispatch.

#264: streaming, finishing, and run_ui_command used to call
``self.websocket_handler.write_message`` directly. From the Claude /
MCP worker threads, that path mutates Tornado's bytearray write buffer
across IOLoop boundaries and raises
``BufferError: Existing exports of data: object cannot be re-sized``.

These tests pin the contract that the emitter marshals every write
through the IOLoop's ``call_soon_threadsafe`` so the bug can't regress.
"""

from unittest.mock import MagicMock, patch

import pytest

from notebook_intelligence import extension
from notebook_intelligence.api import BackendMessageType
from notebook_intelligence.extension import WebsocketCopilotResponseEmitter


def _make_emitter() -> tuple[WebsocketCopilotResponseEmitter, MagicMock, MagicMock]:
    websocket = MagicMock()
    chat_history = MagicMock()
    io_loop = MagicMock()
    io_loop.asyncio_loop = MagicMock()
    with patch.object(extension.tornado.ioloop.IOLoop, "current", return_value=io_loop):
        emitter = WebsocketCopilotResponseEmitter(
            chatId="cid",
            messageId="mid",
            websocket_handler=websocket,
            chat_history=chat_history,
        )
    return emitter, websocket, io_loop


def test_stream_dispatches_through_ioloop_not_direct_write():
    emitter, websocket, io_loop = _make_emitter()
    payload = MagicMock()
    payload.to_dict.return_value = {"content": "hi", "type": "markdown"}

    emitter.stream(payload)

    # The direct write would mutate Tornado's bytearray from a worker
    # thread and trip BufferError. Assert we did NOT take that path.
    websocket.write_message.assert_not_called()
    # And we DID hand off via call_soon_threadsafe.
    call_soon = io_loop.asyncio_loop.call_soon_threadsafe
    assert call_soon.call_count == 1
    callback, message = call_soon.call_args[0]
    assert callback is websocket.write_message
    assert message["id"] == "mid"
    assert message["type"] == BackendMessageType.StreamMessage


def test_finish_dispatches_through_ioloop_not_direct_write():
    emitter, websocket, io_loop = _make_emitter()

    emitter.finish()

    websocket.write_message.assert_not_called()
    call_soon = io_loop.asyncio_loop.call_soon_threadsafe
    assert call_soon.call_count == 1
    callback, message = call_soon.call_args[0]
    assert callback is websocket.write_message
    assert message["type"] == BackendMessageType.StreamEnd


def test_send_async_path_targets_websocket_write_message():
    # run_ui_command shares the _send_async helper with stream/finish.
    # Rather than spin up an event loop to exercise the awaitable, pin
    # the helper directly: it must route through call_soon_threadsafe
    # with the websocket.write_message bound method as the callback.
    emitter, websocket, io_loop = _make_emitter()

    payload = {"type": "demo", "data": {"x": 1}}
    emitter._send_async(payload)

    websocket.write_message.assert_not_called()
    call_soon = io_loop.asyncio_loop.call_soon_threadsafe
    callback, message = call_soon.call_args[0]
    assert callback is websocket.write_message
    assert message is payload
