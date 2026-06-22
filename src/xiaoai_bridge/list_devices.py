from __future__ import annotations

import asyncio
import logging

from xiaoai_bridge.config import Settings
from xiaoai_bridge.mina_client import MiNAClient
from xiaoai_bridge.xiaomi_auth import XiaomiAuthenticator

LOGGER = logging.getLogger(__name__)


def main() -> None:
    asyncio.run(run())


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
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
        devices = await mina.list_devices()
        if not devices:
            LOGGER.info("No MiNA devices found")
            return
        print("MiNA devices:", flush=True)
        for index, device in enumerate(devices, start=1):
            selected = " *" if device.matches(settings.speaker_sn, settings.speaker_mac) else ""
            print(
                f"{index}.{selected} name={device.name or '<empty>'}, "
                f"alias={device.alias or '<empty>'}, "
                f"sn={device.serial_number or device.device_sn_profile or '<empty>'}, "
                f"mac={device.mac or '<empty>'}, "
                f"hardware={device.hardware or '<empty>'}, "
                f"device_id={device.device_id or '<empty>'}, "
                f"miot_did={device.miot_did or '<empty>'}",
                flush=True,
            )


if __name__ == "__main__":
    main()
