from __future__ import annotations

import asyncio
import logging
import mimetypes
import socket
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import quote, urlparse

LOGGER = logging.getLogger(__name__)


class AudioFileServer:
    def __init__(self, host: str, port: int, public_base_url: str = "") -> None:
        self.host = host
        self.port = port
        self.public_base_url = public_base_url.rstrip("/")
        self._files: dict[str, Path] = {}
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    async def start(self) -> None:
        if self._server:
            return
        handler_cls = self._make_handler()
        self._server = ThreadingHTTPServer((self.host, self.port), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        LOGGER.info("Local MP3 server listening on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        if not self._server:
            return
        server = self._server
        await asyncio.to_thread(server.shutdown)
        server.server_close()
        self._server = None
        self._thread = None

    def register(self, path: Path) -> str:
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            msg = f"MP3 path does not exist or is not a file: {resolved}"
            raise FileNotFoundError(msg)
        token = f"{uuid.uuid4().hex}{resolved.suffix or '.mp3'}"
        self._files[token] = resolved
        return f"{self.base_url()}/audio/{quote(token)}"

    def base_url(self) -> str:
        if self.public_base_url:
            return self.public_base_url
        return f"http://{local_lan_ip()}:{self.port}"

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        files = self._files

        class Handler(BaseHTTPRequestHandler):
            server_version = "MiFeedAudio/0.1"
            files_ref: ClassVar[dict[str, Path]] = files

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if not parsed.path.startswith("/audio/"):
                    self.send_error(404)
                    return
                token = parsed.path.removeprefix("/audio/")
                file_path = self.files_ref.get(token)
                if not file_path or not file_path.is_file():
                    self.send_error(404)
                    return

                content_type = mimetypes.guess_type(file_path.name)[0] or "audio/mpeg"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(file_path.stat().st_size))
                self.end_headers()
                with file_path.open("rb") as file_obj:
                    while chunk := file_obj.read(1024 * 64):
                        self.wfile.write(chunk)

            def log_message(self, fmt: str, *args: object) -> None:
                LOGGER.debug("audio server: " + fmt, *args)

        return Handler


def maybe_audio_result(value: str) -> bool:
    lowered = value.lower().split("?", 1)[0]
    if lowered.startswith(("http://", "https://")):
        return lowered.endswith((".mp3", ".m4a", ".wav", ".aac", ".flac"))
    return Path(value).expanduser().suffix.lower() in {".mp3", ".m4a", ".wav", ".aac", ".flac"}


def is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def local_lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()
