import pytest

from ai_quant.config import AppMode, ConfigurationError, Settings


def test_settings_default_to_demo_without_secrets() -> None:
    settings = Settings.from_env({})

    assert settings.app_mode is AppMode.DEMO
    assert settings.anthropic_api_key is None
    assert settings.anthropic_model is None


def test_settings_accept_demo_without_anthropic_key() -> None:
    settings = Settings.from_env({"APP_MODE": "demo"})

    assert settings == Settings(app_mode=AppMode.DEMO)


def test_settings_normalize_app_mode() -> None:
    settings = Settings.from_env({"APP_MODE": "  DEMO  "})

    assert settings.app_mode is AppMode.DEMO


def test_settings_reject_unknown_app_mode() -> None:
    with pytest.raises(ConfigurationError, match="APP_MODE must be one of"):
        Settings.from_env({"APP_MODE": "preview"})


def test_live_mode_requires_no_anthropic_configuration() -> None:
    settings = Settings.from_env({"APP_MODE": "live"})

    assert settings.app_mode is AppMode.LIVE
    assert settings.api_base_url == "http://api:8000"


def test_api_base_url_must_be_http() -> None:
    with pytest.raises(ConfigurationError, match="API_BASE_URL"):
        Settings.from_env({"APP_MODE": "live", "API_BASE_URL": "postgres://wrong"})


def test_live_mode_accepts_configured_anthropic_key_without_exposing_it() -> None:
    settings = Settings.from_env(
        {
            "APP_MODE": "live",
            "ANTHROPIC_API_KEY": "placeholder-test-key",
            "ANTHROPIC_MODEL": "placeholder-model-id",
            "API_BASE_URL": "http://127.0.0.1:8000/",
        }
    )

    assert settings.app_mode is AppMode.LIVE
    assert settings.anthropic_api_key == "placeholder-test-key"
    assert settings.anthropic_model == "placeholder-model-id"
    assert settings.api_base_url == "http://127.0.0.1:8000"
    assert "placeholder-test-key" not in repr(settings)
