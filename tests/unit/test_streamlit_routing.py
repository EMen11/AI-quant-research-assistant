from __future__ import annotations

import sys
from types import ModuleType

from ai_quant.config import AppMode, Settings
from ai_quant.streamlit_app import (
    AI_AUDIT_WORKBENCH_VIEW,
    EQUITY_RESEARCH_VIEW,
    default_view_for_mode,
    render_selected_view,
)


def test_demo_and_live_defaults_preserve_the_requested_behavior() -> None:
    assert default_view_for_mode(AppMode.DEMO) == EQUITY_RESEARCH_VIEW
    assert default_view_for_mode(AppMode.LIVE) == AI_AUDIT_WORKBENCH_VIEW


def test_equity_selection_does_not_render_the_audit_workbench(monkeypatch) -> None:
    called: list[str] = []
    fake_equity = ModuleType("ai_quant.equity_dashboard")
    fake_equity.render_equity_dashboard = lambda: called.append("equity")
    monkeypatch.setitem(sys.modules, "ai_quant.equity_dashboard", fake_equity)
    monkeypatch.setattr(
        "ai_quant.streamlit_app.render_audit_workbench",
        lambda settings: called.append("audit"),
    )

    render_selected_view(Settings(app_mode=AppMode.DEMO), EQUITY_RESEARCH_VIEW)

    assert called == ["equity"]


def test_audit_selection_does_not_render_the_equity_view(monkeypatch) -> None:
    called: list[str] = []
    fake_equity = ModuleType("ai_quant.equity_dashboard")

    def unexpected_equity_render() -> None:
        raise AssertionError("Non-selected Equity view was rendered")

    fake_equity.render_equity_dashboard = unexpected_equity_render
    monkeypatch.setitem(sys.modules, "ai_quant.equity_dashboard", fake_equity)
    monkeypatch.setattr(
        "ai_quant.streamlit_app.render_audit_workbench",
        lambda settings: called.append(settings.app_mode.value),
    )

    render_selected_view(Settings(app_mode=AppMode.LIVE), AI_AUDIT_WORKBENCH_VIEW)

    assert called == ["live"]
