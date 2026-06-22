from __future__ import annotations

import asyncio
import curses
import logging
from pathlib import Path

from xiaoai_bridge.config import Settings
from xiaoai_bridge.mina_client import MiNAClient, MiNADevice
from xiaoai_bridge.xiaomi_auth import XiaomiAuthenticator

LOGGER = logging.getLogger(__name__)
ENV_PATH = Path(".env")


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

    selected = curses.wrapper(
        choose_devices,
        devices,
        settings.speaker_sn_values(),
        settings.speaker_mac_values(),
    )
    if selected is None:
        print("已取消选择。")
        return
    if not selected:
        print("未选择任何小爱音箱，.env 未修改。")
        return

    update_env_selection(ENV_PATH, selected)
    print("已更新 .env：")
    for device in selected:
        print(f"- {device.display_name}: sn={device.serial_number}, mac={device.mac}")


def choose_devices(
    screen: curses.window,
    devices: list[MiNADevice],
    selected_sns: list[str],
    selected_macs: list[str],
) -> list[MiNADevice] | None:
    curses.curs_set(0)
    current = 0
    selected = {
        index
        for index, device in enumerate(devices)
        if device.matches_any(selected_sns, selected_macs)
    }

    while True:
        screen.erase()
        screen.addstr(0, 0, "选择要监听的小爱音箱：↑/↓ 移动，空格多选，a 全选/全不选")
        screen.addstr(1, 0, "Enter 保存，q 取消")
        for index, device in enumerate(devices):
            marker = "●" if index in selected else "○"
            cursor = "➜" if index == current else " "
            line = (
                f"{cursor} {marker} {device.display_name}  "
                f"SN={device.serial_number or device.device_sn_profile or '<empty>'}  "
                f"MAC={device.mac or '<empty>'}  HW={device.hardware or '<empty>'}"
            )
            attr = curses.A_REVERSE if index == current else curses.A_NORMAL
            screen.addstr(index + 3, 0, line[: curses.COLS - 1], attr)
        screen.refresh()

        key = screen.getch()
        if key in (curses.KEY_UP, ord("k")):
            current = (current - 1) % len(devices)
        elif key in (curses.KEY_DOWN, ord("j")):
            current = (current + 1) % len(devices)
        elif key == ord(" "):
            if current in selected:
                selected.remove(current)
            else:
                selected.add(current)
        elif key in (ord("a"), ord("A")):
            selected = set() if len(selected) == len(devices) else set(range(len(devices)))
        elif key in (curses.KEY_ENTER, 10, 13):
            return [devices[index] for index in sorted(selected)]
        elif key in (ord("q"), ord("Q"), 27):
            return None


def update_env_selection(path: Path, devices: list[MiNADevice]) -> None:
    sn_value = ",".join(device.serial_number for device in devices if device.serial_number)
    mac_value = ",".join(device.mac for device in devices if device.mac)

    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = set_or_append_env(lines, "MI_SPEAKER_SN", sn_value)
    lines = set_or_append_env(lines, "MI_SPEAKER_MAC", mac_value)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_or_append_env(lines: list[str], key: str, value: str) -> list[str]:
    replacement = f'{key}="{value}"'
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = replacement
            return lines
    lines.append(replacement)
    return lines


if __name__ == "__main__":
    main()
