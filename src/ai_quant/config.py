"""Typed application configuration loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class ConfigurationError(ValueError):
    """Raised when application configuration is missing or invalid."""


class AppMode(StrEnum):
    """Supported application execution modes."""

    DEMO = "demo"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated settings used at application startup."""

    app_mode: AppMode = AppMode.DEMO
    api_base_url: str = "http://api:8000"
    anthropic_api_key: str | None = field(default=None, repr=False)
    anthropic_model: str | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build and validate settings from an environment mapping."""

        source = os.environ if environ is None else environ
        raw_mode = source.get("APP_MODE", AppMode.DEMO.value).strip().lower()

        try:
            app_mode = AppMode(raw_mode)
        except ValueError as exc:
            allowed = ", ".join(mode.value for mode in AppMode)
            raise ConfigurationError(
                f"APP_MODE must be one of: {allowed}; received {raw_mode!r}."
            ) from exc

        api_key = source.get("ANTHROPIC_API_KEY", "").strip() or None
        model = source.get("ANTHROPIC_MODEL", "").strip() or None
        api_base_url = source.get("API_BASE_URL", "http://api:8000").strip()
        if not api_base_url.startswith(("http://", "https://")):
            raise ConfigurationError("API_BASE_URL must be an HTTP(S) URL.")

        return cls(
            app_mode=app_mode,
            api_base_url=api_base_url.rstrip("/"),
            anthropic_api_key=api_key,
            anthropic_model=model,
        )
