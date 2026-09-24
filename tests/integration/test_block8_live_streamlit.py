from __future__ import annotations

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ai_quant.live_dashboard import api_request

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_live_streamlit_calls_api_and_reads_persisted_analysis(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    api_url = os.environ.get("BLOCK8_LIVE_API_URL", "").strip()
    if not api_url:
        pytest.skip("BLOCK8_LIVE_API_URL is required for the live Streamlit smoke test")
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("API_BASE_URL", api_url)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=20).run()
    assert not app.exception
    assert any("API health: ok" in item.value for item in app.success)
    run_button = next(item for item in app.button if item.label == "Run and persist analysis")

    run_button.click().run()

    assert not app.exception
    analysis = app.session_state["block8-live-analysis"]
    assert analysis["data_origin"] == "frozen_offline_fixture"
    persisted = api_request(api_url, "GET", f"/analyses/{analysis['analysis_id']}")
    assert isinstance(persisted, dict)
    assert persisted["analysis_id"] == analysis["analysis_id"]
