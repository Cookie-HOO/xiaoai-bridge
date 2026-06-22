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
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("xiaoai_bridge").setLevel(logging.INFO)
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

    try:
        async with MiNAClient(authenticator) as mina:
            devices = await mina.list_devices()
            selected = [
                device
                for device in devices
                if device.matches_any(settings.speaker_sn_values(), settings.speaker_mac_values())
            ]
    except Exception as exc:
        print("❌ 小米登录态不可用，或 passToken 已过期。", flush=True)
        print(f"错误：{type(exc).__name__}: {exc}", flush=True)
        print("\n请重新获取 passToken 后更新 .env：", flush=True)
        print('MI_XIAOMI_USER_ID="..."', flush=True)
        print('MI_XIAOMI_PASS_TOKEN="..."', flush=True)
        print("\n然后运行：", flush=True)
        print("rm -f .data/token_cache.json", flush=True)
        print("uv run xiaoai-check-login", flush=True)
        raise SystemExit(1) from exc

    print("✅ 小米登录态可用", flush=True)
    print(f"✅ 找到 {len(devices)} 台小爱音箱", flush=True)
    if selected:
        print("✅ 当前监听：", flush=True)
        for device in selected:
            print(f"- {device.display_name} ({device.mac or device.serial_number})", flush=True)
    else:
        print("⚠️ 当前 .env 没有匹配到要监听的小爱音箱", flush=True)
        print("请运行：uv run whichxiaoai", flush=True)


if __name__ == "__main__":
    main()
