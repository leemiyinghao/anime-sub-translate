from contextvars import ContextVar
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from logger import LOG_LEVEL


class _Setting(BaseSettings):
    """
    Settings for the application.
    """

    model_config = SettingsConfigDict(
        env_file=None, env_file_encoding="utf-8", frozen=True, extra="ignore"
    )

    # LLM setting
    llm_model: str = "gpt-3.5-turbo"
    llm_extra_prompt: str = ""
    max_output_token: int = 5_000
    max_input_token: int = 500_000
    llm_retry_times: int = 5
    llm_retry_delay: float = 2.0
    llm_retry_backoff: float = 2.0

    # translator setting
    language_postfix: Optional[str] = None
    concurrency: int = 16

    # application setting
    log_level: LOG_LEVEL = "info"
    anilist_token: Optional[str] = None

    @property
    def debug(self) -> bool:
        """
        Debug mode.
        """
        return self.log_level == "debug"


def load_setting_with_env_file(env_file: str) -> _Setting:
    """
    Load the settings from the environment file.
    """
    # apply env_file for litellm
    load_dotenv(env_file)
    # Load the settings from the environment variables
    return _Setting(_env_file=env_file)  # type: ignore[arg-type]


_setting: ContextVar[Optional[_Setting]] = ContextVar(
    "_setting",
    default=None,
)


def get_setting() -> _Setting:
    """
    Get the current settings.
    """
    setting = None
    if setting := _setting.get():
        pass
    else:
        setting = _Setting()
        _setting.set(setting)
    return setting


def set_setting(setting: _Setting) -> None:
    """
    Set the current settings.
    """
    _setting.set(setting)
