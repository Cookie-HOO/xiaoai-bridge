from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from xiaoai_bridge.app import call_handler, resolve_handler_spec
from xiaoai_bridge.config import Settings


@pytest.mark.asyncio
async def test_call_handler_with_question_and_speaker() -> None:
    speaker = SimpleNamespace(display_name="Desk XiaoAi")

    def handler(question, device):
        return f"{device.display_name}: {question}"

    result = await call_handler(handler, "hello", speaker)

    assert result == "Desk XiaoAi: hello"


@pytest.mark.asyncio
async def test_call_handler_falls_back_to_question_only() -> None:
    speaker = SimpleNamespace(display_name="Desk XiaoAi")

    def handler(question):
        return f"question only: {question}"

    result = await call_handler(handler, "hello", speaker)

    assert result == "question only: hello"


@pytest.mark.asyncio
async def test_call_handler_awaits_async_result() -> None:
    speaker = SimpleNamespace(display_name="Desk XiaoAi")

    async def handler(question, device):
        return f"async: {device.display_name}: {question}"

    result = await call_handler(handler, "hello", speaker)

    assert result == "async: Desk XiaoAi: hello"


@pytest.mark.asyncio
async def test_call_handler_returns_sync_generator() -> None:
    speaker = SimpleNamespace(display_name="Desk XiaoAi")

    def handler(question, device):
        yield f"{device.display_name}: {question}"
        yield "done"

    result = await call_handler(handler, "hello", speaker)

    assert list(result) == ["Desk XiaoAi: hello", "done"]


@pytest.mark.asyncio
async def test_call_handler_returns_async_generator() -> None:
    speaker = SimpleNamespace(display_name="Desk XiaoAi")

    async def handler(question, device) -> AsyncIterator[str]:
        yield f"{device.display_name}: {question}"
        yield "done"

    result = await call_handler(handler, "hello", speaker)

    chunks = []
    async for chunk in result:
        chunks.append(chunk)
    assert chunks == ["Desk XiaoAi: hello", "done"]


@pytest.mark.asyncio
async def test_call_handler_returns_none() -> None:
    speaker = SimpleNamespace(display_name="Desk XiaoAi")

    def handler(question, device):
        return None

    result = await call_handler(handler, "hello", speaker)

    assert result is None


def test_resolve_handler_spec_prefers_cli() -> None:
    settings = Settings(MI_HANDLER="env_handler:handler")

    assert resolve_handler_spec("cli_handler:handler", settings) == "cli_handler:handler"


def test_resolve_handler_spec_uses_settings() -> None:
    settings = Settings(MI_HANDLER="env_handler:handler")

    assert resolve_handler_spec(None, settings) == "env_handler:handler"


def test_resolve_handler_spec_uses_default() -> None:
    settings = Settings(_env_file=None)

    assert resolve_handler_spec(None, settings) == "xiaoai_bridge.handler:handler"
