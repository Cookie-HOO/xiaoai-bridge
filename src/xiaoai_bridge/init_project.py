from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

ENV_TEMPLATE = dedent(
    """
    # Xiaomi account. Optional when using MI_XIAOMI_USER_ID + MI_XIAOMI_PASS_TOKEN.
    MI_XIAOMI_ACCOUNT=""

    # Xiaomi account password. Optional when using MI_XIAOMI_USER_ID + MI_XIAOMI_PASS_TOKEN.
    MI_XIAOMI_PASSWORD=""

    # Xiaomi userId. Recommended; copy it from account.xiaomi.com cookies/storage.
    MI_XIAOMI_USER_ID=""

    # Xiaomi passToken. Recommended; copy the full value including the V1: prefix.
    MI_XIAOMI_PASS_TOKEN=""

    # XiaoAi speaker SN values to listen to. Multiple values are comma-separated.
    # You can fill these automatically by running xiaoai-select.
    MI_SPEAKER_SN=""

    # XiaoAi speaker MAC values to listen to. Multiple values are comma-separated.
    # Values should match MI_SPEAKER_SN order.
    MI_SPEAKER_MAC=""

    # Your project-local handler. Supports module:callable and ./file.py:callable.
    MI_HANDLER="./handler.py:handler"

    # Poll interval in seconds. Smaller values respond faster but make more requests.
    MI_POLL_INTERVAL_SECONDS="1"

    # Cached Xiaomi serviceToken path. Delete this file to force a fresh login.
    MI_TOKEN_CACHE_PATH=".data/token_cache.json"

    # Public/LAN base URL that XiaoAi speakers can use to reach local audio files.
    # Leave empty to let xiaoai-bridge infer a local file server URL.
    MI_PUBLIC_BASE_URL=""

    # Local audio file server bind host and port.
    MI_FILE_SERVER_HOST="0.0.0.0"
    MI_FILE_SERVER_PORT="8765"
    """
).lstrip()

HANDLER_TEMPLATE = dedent(
    '''
    from __future__ import annotations

    from xiaoai_bridge.mina_client import MiNADevice


    def handler(question: str, speaker: MiNADevice) -> str | None:
        """Handle a new XiaoAi question.

        Return values:
        - text: XiaoAi speaks it with TTS
        - http(s) audio URL: XiaoAi plays the URL
        - local mp3/audio path: xiaoai-bridge maps it through the local file server
        - None or empty string: no reply
        """
        print(f"用户问题：{question}，来自：{speaker.display_name}", flush=True)
        return f"{speaker.display_name} 收到：{question}"
    '''
).lstrip()

GITIGNORE_TEMPLATE = dedent(
    """
    .env
    .env.*
    .data/
    __pycache__/
    *.py[cod]
    .venv/
    """
).lstrip()


@dataclass(frozen=True)
class InitResult:
    created: list[Path]
    skipped: list[Path]


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    result = initialize_project(args.directory, force=args.force)
    for path in result.created:
        print(f"created {path}")
    for path in result.skipped:
        print(f"skipped {path} (already exists; use --force to overwrite)")
    print("\nNext steps:")
    print("1. Fill MI_XIAOMI_USER_ID and MI_XIAOMI_PASS_TOKEN in .env")
    print("2. Run xiaoai-check-login")
    print("3. Run xiaoai-select")
    print("4. Run xiaoai-bridge")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a minimal xiaoai-bridge user project.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        type=Path,
        help="Target directory to initialize. Defaults to the current directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing generated files.",
    )
    return parser.parse_args(argv)


def initialize_project(directory: Path, *, force: bool = False) -> InitResult:
    target = directory.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    skipped: list[Path] = []
    for name, content in {
        ".env": ENV_TEMPLATE,
        "handler.py": HANDLER_TEMPLATE,
        ".gitignore": GITIGNORE_TEMPLATE,
    }.items():
        path = target / name
        if path.exists() and not force:
            skipped.append(path)
            continue
        path.write_text(content, encoding="utf-8")
        created.append(path)
    return InitResult(created=created, skipped=skipped)
