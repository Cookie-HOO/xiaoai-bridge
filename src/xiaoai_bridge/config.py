from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MI_", extra="ignore")

    xiaomi_account: str = Field(default="", alias="MI_XIAOMI_ACCOUNT")
    xiaomi_password: str = Field(default="", alias="MI_XIAOMI_PASSWORD")
    xiaomi_user_id: str = Field(default="", alias="MI_XIAOMI_USER_ID")
    xiaomi_pass_token: str = Field(default="", alias="MI_XIAOMI_PASS_TOKEN")
    speaker_sn: str = Field(default="", alias="MI_SPEAKER_SN")
    speaker_mac: str = Field(default="", alias="MI_SPEAKER_MAC")
    poll_interval_seconds: float = Field(default=1.0, alias="MI_POLL_INTERVAL_SECONDS")
    token_cache_path: Path = Field(
        default=Path(".data/token_cache.json"),
        alias="MI_TOKEN_CACHE_PATH",
    )
    public_base_url: str = Field(default="", alias="MI_PUBLIC_BASE_URL")
    file_server_host: str = Field(default="0.0.0.0", alias="MI_FILE_SERVER_HOST")
    file_server_port: int = Field(default=8765, alias="MI_FILE_SERVER_PORT")

    @field_validator("poll_interval_seconds")
    @classmethod
    def validate_poll_interval(cls, value: float) -> float:
        if value <= 0:
            msg = "MI_POLL_INTERVAL_SECONDS must be greater than 0"
            raise ValueError(msg)
        return value

    @field_validator("file_server_port")
    @classmethod
    def validate_file_server_port(cls, value: int) -> int:
        if not 0 < value < 65536:
            msg = "MI_FILE_SERVER_PORT must be between 1 and 65535"
            raise ValueError(msg)
        return value

    def validate_required_credentials(self) -> None:
        missing = []
        if not self.xiaomi_account and not self.xiaomi_user_id:
            missing.append("MI_XIAOMI_ACCOUNT or MI_XIAOMI_USER_ID")
        if not self.xiaomi_password and not self.xiaomi_pass_token:
            missing.append("MI_XIAOMI_PASSWORD or MI_XIAOMI_PASS_TOKEN")
        if missing:
            joined = ", ".join(missing)
            msg = (
                f"Missing required configuration: {joined}. "
                "Copy .env.example to .env and fill it."
            )
            raise ValueError(msg)

    def speaker_sn_values(self) -> list[str]:
        return split_csv(self.speaker_sn)

    def speaker_mac_values(self) -> list[str]:
        return split_csv(self.speaker_mac)

    def has_device_selector(self) -> bool:
        return bool(self.speaker_sn_values() or self.speaker_mac_values())

    def redacted_summary(self) -> str:
        account = self.xiaomi_account or "<empty>"
        if account and account != "<empty>":
            account = f"{account[:3]}***"
        return (
            f"account={account}, speaker_sn={len(self.speaker_sn_values()) or '<empty>'}, "
            f"speaker_mac={len(self.speaker_mac_values()) or '<empty>'}, "
            f"poll_interval={self.poll_interval_seconds}s"
        )


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
