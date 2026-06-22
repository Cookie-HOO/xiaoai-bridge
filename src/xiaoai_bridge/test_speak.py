from __future__ import annotations

import argparse
import asyncio
import logging

from xiaoai_bridge.config import Settings
from xiaoai_bridge.mina_client import MiNAClient
from xiaoai_bridge.xiaomi_auth import XiaomiAuthenticator

DEFAULT_TEST_TEXT = "来自 xiaoai-bridge 的测试"

LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="让当前选择的小爱音箱播放一段测试 TTS")
    parser.add_argument(
        "text",
        nargs="?",
        default=DEFAULT_TEST_TEXT,
        help=f"要让小爱音箱播放的文字，默认：{DEFAULT_TEST_TEXT}",
    )
    args = parser.parse_args()
    asyncio.run(run(args.text))


async def run(text: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings()
    settings.validate_required_credentials()

    authenticator = XiaomiAuthenticator(
        account=settings.xiaomi_account,
        password=settings.xiaomi_password,
        cache_path=settings.token_cache_path,
        user_id=settings.xiaomi_user_id,
        pass_token=settings.xiaomi_pass_token,
    )

    async with MiNAClient(authenticator) as mina:
        devices = await mina.resolve_devices(
            settings.speaker_sn_values(),
            settings.speaker_mac_values(),
        )
        device = devices[0]
        LOGGER.info("Sending test TTS to %s: %s", device.display_name, text)
        await mina.play_tts(device, text)
        LOGGER.info("Test TTS request sent")


if __name__ == "__main__":
    main()
