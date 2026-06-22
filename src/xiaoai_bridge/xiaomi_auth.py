from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx

LOGGER = logging.getLogger(__name__)
LOGIN_URL = "https://account.xiaomi.com/pass/serviceLogin"
LOGIN_AUTH_URL = "https://account.xiaomi.com/pass/serviceLoginAuth2"
DEFAULT_USER_AGENT = (
    "Dalvik/2.1.0 (Linux; U; Android 10; RMX2111 Build/QP1A.190711.020) "
    "APP/xiaomi.mico APPV/2004040 MK/Uk1YMjExMQ== "
    "PassportSDK/3.8.3 passport-ui/3.8.3"
)


class XiaomiAuthError(RuntimeError):
    """Raised when Xiaomi account authentication fails."""


@dataclass(slots=True)
class XiaomiSession:
    user_id: str
    service_token: str
    ssecurity: str
    pass_token: str
    device_id: str
    c_user_id: str = ""
    sid: str = "micoapi"


class XiaomiAuthenticator:
    def __init__(
        self,
        account: str,
        password: str,
        cache_path: Path,
        sid: str = "micoapi",
        user_id: str = "",
        pass_token: str = "",
    ) -> None:
        self.account = account
        self.password = password
        self.user_id = user_id or account
        self.pass_token = pass_token
        self.cache_path = cache_path
        self.sid = sid
        self.device_id = f"android_{uuid.uuid4().hex[:16]}"

    def load_cached_session(self) -> XiaomiSession | None:
        if not self.cache_path.exists():
            return None
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if data.get("sid") != self.sid:
                return None
            session = XiaomiSession(**data)
            self.device_id = session.device_id
            return session
        except (OSError, TypeError, ValueError) as exc:
            LOGGER.warning("Failed to load Xiaomi token cache: %s", exc)
            return None

    def save_session(self, session: XiaomiSession) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(asdict(session), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def get_session(self, force_login: bool = False) -> XiaomiSession:
        if not force_login:
            cached = self.load_cached_session()
            if cached:
                LOGGER.info("Using cached Xiaomi %s session", self.sid)
                return cached
        session = await self.login()
        self.save_session(session)
        return session

    async def login(self) -> XiaomiSession:
        LOGGER.info("Logging in to Xiaomi account for sid=%s", self.sid)
        async with httpx.AsyncClient(follow_redirects=False, timeout=20) as client:
            login_state = await self._get_login_state(client)
            if login_state.get("code") == 0 and self.pass_token:
                login_pass = login_state
            else:
                login_pass = await self._submit_login(client, login_state)
            session = await self._exchange_service_token(client, login_pass)
            LOGGER.info("Xiaomi login finished for sid=%s", self.sid)
            return session

    def _login_cookies(self) -> dict[str, str]:
        cookies = {"deviceId": self.device_id}
        if self.user_id:
            cookies["userId"] = self.user_id
        if self.pass_token:
            cookies["passToken"] = self.pass_token
        return cookies

    async def _get_login_state(self, client: httpx.AsyncClient) -> dict[str, Any]:
        response = await client.get(
            LOGIN_URL,
            params={"sid": self.sid, "_json": "true", "_locale": "zh_CN"},
            cookies=self._login_cookies(),
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        response.raise_for_status()
        data = parse_xiaomi_json(response.text)
        if data.get("code") in (0, "0"):
            return data
        required = {"qs", "_sign", "callback"}
        if not required <= data.keys():
            msg = f"Unexpected Xiaomi login state response: missing {required - data.keys()}"
            raise XiaomiAuthError(msg)
        return data

    async def _submit_login(
        self,
        client: httpx.AsyncClient,
        login_state: dict[str, Any],
    ) -> dict[str, Any]:
        password_hash = hashlib.md5(self.password.encode()).hexdigest().upper()  # noqa: S324
        response = await client.post(
            LOGIN_AUTH_URL,
            data={
                "_json": "true",
                "qs": login_state["qs"],
                "sid": self.sid,
                "_sign": login_state["_sign"],
                "callback": login_state["callback"],
                "user": self.account,
                "hash": password_hash,
            },
            cookies=self._login_cookies(),
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        response.raise_for_status()
        data = parse_xiaomi_json(response.text)
        if data.get("notificationUrl") and "identity/authStart" in str(data["notificationUrl"]):
            msg = (
                "Xiaomi requires extra security verification. "
                "Finish it in Xiaomi app/web, then retry."
            )
            raise XiaomiAuthError(msg)
        if data.get("code") not in (0, "0", None) and not data.get("location"):
            msg = f"Xiaomi login failed: {data.get('desc') or data.get('description') or data}"
            raise XiaomiAuthError(msg)
        if not data.get("location") or not data.get("ssecurity") or not data.get("nonce"):
            msg = f"Unexpected Xiaomi login response: {data}"
            raise XiaomiAuthError(msg)
        return data

    async def _exchange_service_token(
        self,
        client: httpx.AsyncClient,
        login_pass: dict[str, Any],
    ) -> XiaomiSession:
        client_sign = make_client_sign(str(login_pass["nonce"]), str(login_pass["ssecurity"]))
        response = await client.get(
            build_url_with_params(
                str(login_pass["location"]),
                {"_userIdNeedEncrypt": "true", "clientSign": client_sign},
            ),
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        if response.status_code not in (200, 302):
            response.raise_for_status()

        service_token = response.cookies.get("serviceToken") or client.cookies.get("serviceToken")
        user_id = str(login_pass.get("userId") or response.cookies.get("userId") or self.account)
        if not service_token:
            msg = "Xiaomi login did not return serviceToken cookie"
            raise XiaomiAuthError(msg)

        return XiaomiSession(
            user_id=user_id,
            c_user_id=str(login_pass.get("cUserId") or ""),
            service_token=service_token,
            ssecurity=str(login_pass["ssecurity"]),
            pass_token=str(login_pass.get("passToken") or ""),
            device_id=self.device_id,
            sid=self.sid,
        )


def parse_xiaomi_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^&&&START&&&", "", cleaned)
    cleaned = re.sub(r":(\d{9,})", r':"\1"', cleaned)
    start = cleaned.find("{")
    if start > 0:
        cleaned = cleaned[start:]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        msg = f"Unable to parse Xiaomi JSON response: {cleaned[:200]}"
        raise XiaomiAuthError(msg) from exc
    if not isinstance(parsed, dict):
        msg = f"Expected Xiaomi JSON object, got {type(parsed).__name__}"
        raise XiaomiAuthError(msg)
    return parsed


def make_client_sign(nonce: str, ssecurity: str) -> str:
    digest = hashlib.sha1(f"nonce={nonce}&{ssecurity}".encode()).digest()  # noqa: S324
    return base64.b64encode(digest).decode()


def build_url_with_params(url: str, params: dict[str, str]) -> str:
    parts = urlsplit(url)
    extra_query = urlencode(params)
    query = f"{parts.query}&{extra_query}" if parts.query else extra_query
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
