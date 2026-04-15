from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    db_path: str = Field(default="data/bot.db", alias="DB_PATH")
    default_tz: str = Field(default="Europe/Moscow", alias="DEFAULT_TZ")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def db_file(self) -> Path:
        return Path(self.db_path)


settings = Settings()
