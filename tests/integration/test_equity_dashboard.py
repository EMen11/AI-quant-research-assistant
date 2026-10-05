from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ai_quant.equity.analysis import build_fundamental_analysis
from ai_quant.equity.climate import CLIMATE_FIXTURE_CUTOFF, build_climate_metrics
from ai_quant.equity.monitoring import build_monitoring_rows
from ai_quant.equity.repository import load_equity_repository
from ai_quant.equity.valuation import build_valuation_analysis
from ai_quant.equity_dashboard import (
    BLOCKED_SIEGFRIED_VALUATION_FIELDS,
    VALUATION_SECTIONS,
    displayed_fundamental_metric_names,
    esg_metric_rows,
    executive_investment_rows,
    primary_monitoring_rows,
    research_comparison_rows,
    snapshot_rows,
    valuation_rows,
)
from ai_quant.sustainability import load_corpus

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _equity_app() -> AppTest:
    return AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=20).run()


def test_equity_research_smoke_and_visible_scope(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _equity_app()

    assert not app.exception
    view = next(item for item in app.selectbox if item.label == "View")
    assert view.value == "Equity research"
    assert app.title[0].value == "Equity Research"
    assert [tab.label for tab in app.tabs] == [
        "Snapshot",
        "Research Note",
        "Fundamentals",
        "Valuation",
        "Monitoring",
        "ESG & Sources",
    ]
    assert app.header[0].value == "Executive Investment View"

    snapshot = next(
        item.value
        for item in app.dataframe
        if set(item.value.columns)
        == {"Metric", "Bachem FY2025", "Siegfried FY2025"}
    )
    assert len(snapshot) == 8
    assert {
        "Revenue",
        "Revenue CAGR FY2021–FY2025",
        "EBITDA margin",
        "Calculated FCF cash conversion",
        "Net debt / EBITDA",
        "Historical EV / EBITDA",
    } <= set(snapshot["Metric"])

    expander_labels = {item.label for item in app.expander}
    assert {
        "Show detailed metrics",
        "View calculation details",
        "View valuation methodology & detailed fields",
        "Monitoring details & provenance",
        "Source & technical provenance",
        "How validation works",
        "Inspect source, calculation & technical provenance",
    } <= expander_labels
    technical = next(
        item
        for item in app.expander
        if item.label == "Inspect source, calculation & technical provenance"
    )
    assert technical.proto.expanded is False

    fundamental_frames = [
        item.value
        for item in app.dataframe
        if {"Company", "Fiscal year", "Metric", "Status"} <= set(item.value.columns)
    ]
    visible_metrics = {
        metric
        for frame in fundamental_frames
        for metric in frame["Metric"].tolist()
    }
    assert {
        "Annual growth",
        "EBIT margin",
        "Net margin",
        "Operating cash flow / CA",
        "Capex reported / CA",
        "Capex calculated / CA",
        "FCF reported",
        "Source-calculated FCF",
        "FCF recomputed by AI Quant",
        "Net debt",
        "ROE on period-end equity",
        "Reported equity ratio",
    } <= visible_metrics
    assert {
        "Historical closing share price",
        "Published market capitalization",
        "Indicative price × shares market capitalization",
        "Enterprise Value",
        "EV / Revenue",
        "EV / EBITDA",
        "EV / EBIT",
        "Published P/E",
        "Calculated P/E",
        "Recalculated P/B",
        "FCF yield (FCF calculated)",
        "Dividend yield",
        "Scope 1",
        "Scope 2 · market-based",
        "Scope 2 · location-based",
    } <= visible_metrics
    calculated_rows = [
        row
        for frame in fundamental_frames
        for _, row in frame.loc[frame["Status"] == "calculated"].iterrows()
    ]
    unavailable_rows = [
        row
        for frame in fundamental_frames
        for _, row in frame.loc[frame["Status"] == "unavailable"].iterrows()
    ]
    assert calculated_rows
    assert all("equity-formulas.v1" in row["Formula / version"] for row in calculated_rows)
    assert all(row["Provenance"] != "unavailable" for row in calculated_rows)
    assert unavailable_rows
    assert all(row["Value"] == "—" for row in unavailable_rows)
    assert all(row["Raw source value"] == "—" for row in unavailable_rows)
    assert any(
        {"Published target", "Declared validation", "PDF page", "SHA-256"}
        <= set(item.value.columns)
        for item in app.dataframe
    )
    assert any(
        {"Assurance status", "Level", "Scope confirmed", "SHA-256"}
        <= set(item.value.columns)
        for item in app.dataframe
    )
    warnings = "\n".join(item.value for item in app.warning)
    assert "Historical FY-end data — not current market data" in warnings


def test_every_visible_metric_is_traceable_and_unlocked_gate_adds_no_warning(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _equity_app()

    assert not app.exception
    inspection_tables = [
        item.value
        for item in app.table
        if "Raw source value" in item.value.columns
    ]
    assert len(inspection_tables) == 4
    for table in inspection_tables:
        assert {
            "Fiscal year",
            "Raw source value",
            "Unit",
            "Status",
            "Formula",
            "Version",
            "Inputs",
        } <= set(table.columns)

    warning_text = "\n".join(item.value for item in app.warning)
    assert not any(field in warning_text for field in BLOCKED_SIEGFRIED_VALUATION_FIELDS)


def test_snapshot_and_fundamental_contracts_use_phase3_metrics_only() -> None:
    analysis = build_fundamental_analysis()
    rows = snapshot_rows(analysis)
    valuation = build_valuation_analysis(fundamentals=analysis)
    comparison = research_comparison_rows(analysis, valuation)
    executive = executive_investment_rows(analysis, valuation)

    assert len(rows) == 14
    assert len(comparison) == 8
    assert len(executive) == 6
    assert {row["Research lens"] for row in executive} == {
        "Growth",
        "Profitability",
        "Cash generation",
        "Balance sheet",
        "Key watchpoint",
        "Historical valuation",
    }
    assert all("valuation" not in row["Metric"].lower() for row in rows)
    assert all("price" not in name for name in displayed_fundamental_metric_names())
    assert all("market" not in name for name in displayed_fundamental_metric_names())
    assert any(row["Bachem status"] == "reported" for row in rows)
    assert any(row["Bachem status"] == "calculated" for row in rows)


def test_primary_monitoring_is_finance_first_without_losing_detail() -> None:
    source_rows = build_monitoring_rows()
    rows = primary_monitoring_rows(source_rows)

    assert rows
    assert set(rows[0]) == {
        "Company",
        "KPI",
        "Latest value",
        "Why it matters",
        "Status",
    }
    assert {row["Status"] for row in rows} == {"Available", "To update"}


def test_historical_valuation_scope_split_and_published_precedence() -> None:
    repository = load_equity_repository()
    analysis = build_valuation_analysis(repository)
    all_specs = tuple(spec for _, specs in VALUATION_SECTIONS for spec in specs)
    rows = valuation_rows(analysis, all_specs)

    assert {row["Fiscal year"] for row in rows} == {
        "FY2021",
        "FY2022",
        "FY2023",
        "FY2024",
        "FY2025",
    }
    published = analysis.metric("siegfried", 2025, "market_capitalization_published")
    indicative = analysis.metric("siegfried", 2025, "market_capitalization_calculated")
    assert published.status == "reported"
    assert published.value == 3268
    assert indicative.status == "calculated"
    assert indicative.value != published.value
    enterprise_value = analysis.metric("siegfried", 2025, "enterprise_value")
    assert published.metric_id in enterprise_value.input_metric_ids
    assert indicative.metric_id not in enterprise_value.input_metric_ids
    assert str(analysis.metric("siegfried", 2021, "year_end_share_price").value) == "89.0"
    assert str(analysis.metric("siegfried", 2024, "year_end_share_price").value) == "98.6"
    assert all(
        analysis.metric("siegfried", year, "dividend_yield").status
        == "not_comparable"
        for year in range(2021, 2025)
    )
    assert analysis.metric("siegfried", 2025, "dividend_yield").status == "calculated"
    assert all(
        analysis.metric("bachem", year, "price_to_earnings_published").status
        == "unavailable"
        for year in range(2021, 2026)
    )
    assert all(
        analysis.metric("bachem", year, "price_to_earnings_calculated").status
        == "calculated"
        for year in range(2021, 2026)
    )


def test_esg_scope_two_methods_and_provenance_remain_separate() -> None:
    repository = load_equity_repository()
    corpus = load_corpus(CLIMATE_FIXTURE_CUTOFF)
    metrics = build_climate_metrics(repository, corpus)
    rows = esg_metric_rows(metrics)

    scope_two = [row for row in rows if row["Metric"].startswith("Scope 2")]
    assert {row["Scope 2 method"] for row in scope_two} == {
        "market_based",
        "location_based",
    }
    assert all(row["Status"] == "reported" for row in scope_two)
    assert all(row["Provenance"] != "unavailable" for row in rows)
    intensities = [row for row in rows if row["Metric"].startswith("Scope 1+2 intensity")]
    assert all(row["Status"] == "calculated" for row in intensities)
    assert {row["Scope 2 method"] for row in intensities} == {
        "market_based",
        "location_based",
    }


def test_research_note_admissible_status_sources_and_limitations(
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _equity_app()

    assert not app.exception
    assert any("Awaiting human review" in item.value for item in app.warning)
    assert any("Automated validation passed" in item.value for item in app.success)
    assert not any("approved" in item.value.casefold() for item in app.success)

    subheaders = {item.value for item in app.subheader}
    assert {
        "Executive summary",
        "Financial comparison",
        "Investment case",
        "Key risks",
        "Catalysts / What to watch",
        "Valuation context",
        "Sustainability context",
        "Limitations",
    } <= subheaders
    captions = "\n".join(item.value for item in app.caption)
    assert "Reported fact" in captions
    assert "Calculated metric" in captions
    assert "Analyst interpretation" in captions
    assert "does not make a final decision" in captions
    assert "published P/E is unavailable" in captions

    sources = next(
        item.value
        for item in app.dataframe
        if set(item.value.columns) == {"Document", "Page", "Openable source"}
    )
    assert len(sources) == 3
    assert sources["Openable source"].str.len().gt(0).all()
    monitoring = next(
        item.value
        for item in app.dataframe
        if set(item.value.columns)
        == {"Company", "KPI", "Latest value", "Why it matters", "Status"}
    )
    assert {"Available", "To update"} == set(monitoring["Status"])

    limitations = next(
        item.value
        for item in app.dataframe
        if "Limitation ID" in item.value.columns
    )
    assert "bachem-published-pe-unavailable" in set(limitations["Limitation ID"])
    assert limitations["Required limitation"].str.contains("not invented").any()


def test_research_note_blocked_scenario_never_appears_validated(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _equity_app()
    scenario = next(
        item for item in app.selectbox if item.label == "Research note scenario"
    )

    app = scenario.select("Blocked").run()

    assert not app.exception
    assert any("Validation blocked" in item.value for item in app.error)
    assert not any("Automated validation passed" in item.value for item in app.success)
    assert not any("Awaiting human review" in item.value for item in app.warning)
    diagnostics = next(
        item.value for item in app.dataframe if "Diagnostic" in item.value.columns
    )
    assert "prohibited_target_price" in set(diagnostics["Code"])


def test_default_equity_view_has_no_network_or_historical_workbench_import() -> None:
    script = r"""
import importlib.abc
import socket
import sys
from streamlit.testing.v1 import AppTest

BLOCKED = ('ai_quant.analyst_dashboard', 'ai_quant.live_dashboard')

class DenyNonSelectedImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in BLOCKED):
            raise AssertionError(f'non-selected view imported: {fullname}')
        return None

def reject_network(*args, **kwargs):
    raise AssertionError('Equity Research attempted network access')

socket.socket.connect = reject_network
socket.create_connection = reject_network
sys.meta_path.insert(0, DenyNonSelectedImports())

app = AppTest.from_file('app.py', default_timeout=20).run()
assert not app.exception
assert app.title[0].value == 'Equity Research'
assert [tab.label for tab in app.tabs] == [
    'Snapshot', 'Research Note', 'Fundamentals', 'Valuation', 'Monitoring',
    'ESG & Sources'
]
for name in BLOCKED:
    assert not any(module == name or module.startswith(name + '.') for module in sys.modules)
"""
    environment = os.environ.copy()
    environment["APP_MODE"] = "demo"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
