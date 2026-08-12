"""
Módulo de Configuración Global del Sistema.

Utiliza Pydantic Settings v2 para garantizar tipado estricto,
validación en tiempo de ejecución e inmutabilidad (frozen=True).
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración global e inmutable de la aplicación.

    Carga variables desde el entorno del sistema o archivo `.env`.
    """

    api_key: str = Field(default="mock_river_api_key_2026_secret", validation_alias="API_KEY")
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=3306, validation_alias="DB_PORT")
    db_user: str = Field(default="root", validation_alias="DB_USER")
    db_password: str = Field(default="secret_password", validation_alias="DB_PASSWORD")
    db_name: str = Field(default="river_predictive_db", validation_alias="DB_NAME")

    # Variables opcionales para alertas de Telegram Bot API
    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,
        extra="ignore",
    )


# Instancia global inmutable de la configuración
settings = Settings()
