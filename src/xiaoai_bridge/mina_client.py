from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from xiaoai_bridge.xiaomi_auth import XiaomiAuthenticator, XiaomiSession

LOGGER = logging.getLogger(__name__)
MINA_BASE_URL = "https://api2.mina.mi.com"
CONVERSATION_URL = "https://userprofile.mina.mi.com/device_profile/v2/conversation"
MINA_USER_AGENT = "MICO/AndroidApp/@SHIP.TO.2A2FE0D7@/2.4.40"
WEBVIEW_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; 000; wv) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/119.0.6045.193 Mobile Safari/537.36 "
    "/XiaoMi/HybridView/ micoSoundboxApp/i appVersion/A_2.4.40"
)


class MiNAError(RuntimeError):
    """Raised when a MiNA request fails."""


@dataclass(slots=True)
class MiNADevice:
    device_id: str
    hardware: str
    serial_number: str = ""
    mac: str = ""
    name: str = ""
    alias: str = ""
    miot_did: str = ""
    device_sn_profile: str = ""

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> MiNADevice:
        return cls(
            device_id=str(raw.get("deviceID") or raw.get("deviceId") or ""),
            hardware=str(raw.get("hardware") or ""),
            serial_number=str(
                raw.get("serialNumber")
                or raw.get("serial_number")
                or raw.get("sn")
                or raw.get("deviceSN")
                or ""
            ),
            mac=str(raw.get("mac") or raw.get("macAddress") or ""),
            name=str(raw.get("name") or ""),
            alias=str(raw.get("alias") or ""),
            miot_did=str(raw.get("miotDID") or raw.get("miotDid") or raw.get("did") or ""),
            device_sn_profile=str(raw.get("deviceSNProfile") or ""),
        )

    @property
    def display_name(self) -> str:
        return self.alias or self.name or self.serial_number or self.device_id

    def matches(self, sn: str, mac: str) -> bool:
        return self.matches_any([sn] if sn else [], [mac] if mac else [])

    def matches_any(self, sns: list[str], macs: list[str]) -> bool:
        normalized_macs = {normalize_mac(mac) for mac in macs if mac}
        own_mac = normalize_mac(self.mac)
        sn_values = {self.serial_number, self.device_sn_profile}
        sn_match = any(sn and sn in sn_values for sn in sns)
        mac_match = bool(own_mac and own_mac in normalized_macs)
        return sn_match or mac_match

    def describe(self) -> str:
        return (
            f"name={self.name or '<empty>'}, alias={self.alias or '<empty>'}, "
            f"sn={self.serial_number or self.device_sn_profile or '<empty>'}, "
            f"mac={self.mac or '<empty>'}, hardware={self.hardware or '<empty>'}"
        )


class MiNAClient:
    def __init__(self, authenticator: XiaomiAuthenticator) -> None:
        self.authenticator = authenticator
        self.session: XiaomiSession | None = None
        self.client = httpx.AsyncClient(timeout=20, follow_redirects=False)

    async def __aenter__(self) -> MiNAClient:
        self.session = await self.authenticator.get_session()
        self._apply_session_cookies(self.session)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.client.aclose()

    async def refresh_session(self) -> None:
        self.session = await self.authenticator.get_session(force_login=True)
        self._apply_session_cookies(self.session)

    async def list_devices(self) -> list[MiNADevice]:
        data = await self._mina_get("/admin/v2/device_list")
        raw_devices = data.get("data") or data.get("list") or data.get("devices") or []
        if isinstance(raw_devices, dict):
            raw_devices = raw_devices.get("list") or raw_devices.get("devices") or []
        if not isinstance(raw_devices, list):
            msg = f"Unexpected device list response: {data}"
            raise MiNAError(msg)
        return [MiNADevice.from_raw(item) for item in raw_devices if isinstance(item, dict)]

    async def resolve_device(self, sn: str, mac: str) -> MiNADevice:
        devices = await self.resolve_devices([sn] if sn else [], [mac] if mac else [])
        return devices[0]

    async def resolve_devices(self, sns: list[str], macs: list[str]) -> list[MiNADevice]:
        devices = await self.list_devices()
        if not devices:
            msg = "No XiaoAi/MiNA devices were returned by Xiaomi account."
            raise MiNAError(msg)
        if not sns and not macs:
            hints = "\n".join(f"- {device.describe()}" for device in devices)
            msg = f"MI_SPEAKER_SN or MI_SPEAKER_MAC is required. Available devices:\n{hints}"
            raise MiNAError(msg)
        matched = [device for device in devices if device.matches_any(sns, macs)]
        if matched:
            for device in matched:
                LOGGER.info("Target speaker selected: %s", device.describe())
            return matched
        hints = "\n".join(f"- {device.describe()}" for device in devices)
        msg = (
            "Target speaker not found. Check MI_SPEAKER_SN/MI_SPEAKER_MAC. "
            f"Available devices:\n{hints}"
        )
        raise MiNAError(msg)

    async def get_conversations(
        self,
        device: MiNADevice,
        limit: int = 10,
        timestamp: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": limit,
            "requestId": str(uuid.uuid4()),
            "source": "dialogu",
            "hardware": device.hardware,
            "timestamp": timestamp if timestamp is not None else int(time.time() * 1000),
        }
        data = await self._conversation_get(params, device)
        payload = data.get("data")
        if isinstance(payload, str):
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError as exc:
                msg = f"Unable to parse conversation data: {payload[:200]}"
                raise MiNAError(msg) from exc
            if isinstance(decoded, dict):
                return decoded
        if isinstance(payload, dict):
            return payload
        if "records" in data:
            return data
        msg = f"Unexpected conversation response: {data}"
        raise MiNAError(msg)

    async def play_tts(self, device: MiNADevice, text: str, save: int = 0) -> None:
        await self.call_ubus(device, "mibrain", "text_to_speech", {"text": text, "save": save})

    async def play_url(self, device: MiNADevice, url: str) -> None:
        await self.call_ubus(device, "mediaplayer", "player_play_url", {"url": url, "type": 1})

    async def get_nlp_results(self, device: MiNADevice) -> list[dict[str, Any]]:
        response = await self.call_ubus(device, "mibrain", "nlp_result_get", {})
        data = response.get("data")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return []
        if not isinstance(data, dict):
            return []
        info = data.get("info")
        if isinstance(info, str):
            try:
                info = json.loads(info)
            except json.JSONDecodeError:
                return []
        if not isinstance(info, dict):
            return []
        results = info.get("result") or []
        return [item for item in results if isinstance(item, dict)]

    async def call_ubus(
        self,
        device: MiNADevice,
        path: str,
        method: str,
        message: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._mina_post(
            "/remote/ubus",
            data={
                "deviceId": device.device_id,
                "path": path,
                "method": method,
                "message": json.dumps(message or {}, ensure_ascii=False),
            },
            device=device,
        )

    async def _mina_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = {"requestId": str(uuid.uuid4()), "timestamp": int(time.time()), **(params or {})}
        response = await self._request_with_refresh(
            "GET",
            f"{MINA_BASE_URL}{path}",
            params=params,
            headers={"User-Agent": MINA_USER_AGENT},
        )
        return self._parse_api_response(response)

    async def _mina_post(
        self,
        path: str,
        data: dict[str, Any],
        device: MiNADevice | None = None,
    ) -> dict[str, Any]:
        headers = {"User-Agent": MINA_USER_AGENT}
        cookies = self._device_cookies(device) if device else None
        response = await self._request_with_refresh(
            "POST",
            f"{MINA_BASE_URL}{path}",
            data=data,
            headers=headers,
            cookies=cookies,
        )
        return self._parse_api_response(response)

    async def _conversation_get(self, params: dict[str, Any], device: MiNADevice) -> dict[str, Any]:
        response = await self._request_with_refresh(
            "GET",
            CONVERSATION_URL,
            params=params,
            headers={
                "User-Agent": WEBVIEW_USER_AGENT,
                "Referer": "https://userprofile.mina.mi.com/dialogue-note/index.html",
                "Cookie": self._conversation_cookie_header(device),
            },
        )
        return self._parse_api_response(response)

    async def _request_with_refresh(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        response = await self.client.request(method, url, **kwargs)
        if response.status_code == 401:
            LOGGER.info("MiNA request returned 401, refreshing Xiaomi session")
            await self.refresh_session()
            response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def _parse_api_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            msg = f"MiNA endpoint returned non-JSON response: {response.text[:200]}"
            raise MiNAError(msg) from exc
        if not isinstance(data, dict):
            msg = f"MiNA endpoint returned unexpected response type: {type(data).__name__}"
            raise MiNAError(msg)
        code = data.get("code")
        if code not in (0, "0", None):
            msg = f"MiNA endpoint failed: {data}"
            raise MiNAError(msg)
        return data

    def _apply_session_cookies(self, session: XiaomiSession) -> None:
        self.client.cookies.set("userId", session.user_id, domain=".mina.mi.com")
        self.client.cookies.set("serviceToken", session.service_token, domain=".mina.mi.com")
        self.client.cookies.set("deviceId", session.device_id, domain=".mina.mi.com")

    def _conversation_cookie_header(self, device: MiNADevice) -> str:
        if not self.session:
            return ""
        return (
            f"userId={self.session.user_id}; "
            f"serviceToken={self.session.service_token}; "
            f"channel=MI_APP_STORE; "
            f"deviceId={device.device_id}"
        )

    def _device_cookies(self, device: MiNADevice | None) -> dict[str, str]:
        cookies: dict[str, str] = {}
        if not self.session or not device:
            return cookies
        cookies.update(
            {
                "userId": self.session.user_id,
                "serviceToken": self.session.service_token,
                "sn": device.serial_number,
                "hardware": device.hardware,
                "deviceId": device.device_id,
                "deviceSNProfile": device.device_sn_profile,
            }
        )
        return {key: value for key, value in cookies.items() if value}


def normalize_mac(value: str) -> str:
    return value.lower().replace(":", "").replace("-", "").strip()
