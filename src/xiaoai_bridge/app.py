from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import AsyncIterable, Iterable
from pathlib import Path
from typing import Any

from xiaoai_bridge.audio_server import AudioFileServer, is_http_url, maybe_audio_result
from xiaoai_bridge.config import Settings
from xiaoai_bridge.handler import handler
from xiaoai_bridge.mina_client import MiNAClient, MiNADevice
from xiaoai_bridge.poller import ConversationPoller, ConversationRecord
from xiaoai_bridge.xiaomi_auth import XiaomiAuthenticator

LOGGER = logging.getLogger(__name__)


def main() -> None:
    asyncio.run(run())


async def run() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("xiaoai_bridge").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings()
    settings.validate_required_credentials()
    LOGGER.info("Starting xiaoai-bridge with %s", settings.redacted_summary())

    authenticator = XiaomiAuthenticator(
        account=settings.xiaomi_account,
        password=settings.xiaomi_password,
        cache_path=settings.token_cache_path,
        user_id=settings.xiaomi_user_id,
        pass_token=settings.xiaomi_pass_token,
    )
    audio_server = AudioFileServer(
        host=settings.file_server_host,
        port=settings.file_server_port,
        public_base_url=settings.public_base_url,
    )

    await audio_server.start()
    try:
        async with MiNAClient(authenticator) as mina:
            devices = await mina.resolve_devices(
                settings.speaker_sn_values(),
                settings.speaker_mac_values(),
            )
            pollers = [ConversationPoller(mina, device) for device in devices]
            for poller in pollers:
                await poller.initialize()
            await poll_loop(settings, mina, pollers, audio_server)
    finally:
        await audio_server.stop()


async def poll_loop(
    settings: Settings,
    mina: MiNAClient,
    pollers: list[ConversationPoller],
    audio_server: AudioFileServer,
) -> None:
    names = ", ".join(poller.device.display_name for poller in pollers)
    LOGGER.info(
        "Polling XiaoAi conversations from [%s] every %.2fs",
        names,
        settings.poll_interval_seconds,
    )
    while True:
        try:
            for poller in pollers:
                records = await poller.fetch_new_questions()
                for record in records:
                    await process_record(mina, poller.device, audio_server, record)
        except KeyboardInterrupt:
            raise
        except Exception:
            LOGGER.exception("Polling iteration failed; will retry on next tick")
        await asyncio.sleep(settings.poll_interval_seconds)


async def process_record(
    mina: MiNAClient,
    device: MiNADevice,
    audio_server: AudioFileServer,
    record: ConversationRecord,
) -> None:
    LOGGER.info("New question from %s: %s", device.display_name, record.question)
    try:
        result = await call_handler(record.question, device)
    except Exception:
        LOGGER.exception("handler() failed for question: %s", record.question)
        return

    await play_handler_result(mina, device, audio_server, result)


async def play_handler_result(
    mina: MiNAClient,
    device: MiNADevice,
    audio_server: AudioFileServer,
    result: Any,
) -> None:
    if result is None:
        LOGGER.info("handler() returned None; no reply")
        return
    if is_async_iterable(result):
        await play_text_stream(mina, device, result)
        return
    if is_sync_iterable(result):
        await play_text_stream(mina, device, sync_to_async_iterable(result))
        return
    await play_single_reply(mina, device, audio_server, result)


async def play_single_reply(
    mina: MiNAClient,
    device: MiNADevice,
    audio_server: AudioFileServer,
    result: Any,
) -> None:
    reply = str(result).strip()
    if not reply:
        LOGGER.info("handler() returned empty reply; no reply")
        return

    if maybe_audio_result(reply):
        url = reply if is_http_url(reply) else audio_server.register(Path(reply))
        LOGGER.info("Playing audio URL: %s", url)
        await mina.play_url(device, url)
        return

    LOGGER.info("Speaking text reply: %s", reply)
    await mina.play_tts(device, reply)


async def play_text_stream(
    mina: MiNAClient,
    device: MiNADevice,
    chunks: AsyncIterable[Any],
) -> None:
    index = 0
    async for chunk in chunks:
        text = str(chunk).strip()
        if not text:
            continue
        index += 1
        LOGGER.info("Speaking stream chunk %d from %s: %s", index, device.display_name, text)
        await mina.play_tts(device, text)


async def sync_to_async_iterable(chunks: Iterable[Any]) -> AsyncIterable[Any]:
    for chunk in chunks:
        yield chunk


def is_async_iterable(value: Any) -> bool:
    return hasattr(value, "__aiter__")


def is_sync_iterable(value: Any) -> bool:
    return not isinstance(value, str | bytes | bytearray | Path) and isinstance(value, Iterable)


async def call_handler(question: str, device: MiNADevice) -> Any:
    try:
        result = handler(question, device)
    except TypeError:
        result = handler(question)
    if inspect.isawaitable(result):
        return await result
    return result


if __name__ == "__main__":
    main()
