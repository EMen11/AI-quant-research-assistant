from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ai_quant.equity.analysis import build_fundamental_analysis
from ai_quant.equity.climate import CLIMATE_FIXTURE_CUTOFF, build_climate_metrics
from ai_quant.equity.repository import load_equity_repository
from ai_quant.equity.valuation import build_valuation_analysis
from ai_quant.equity_dashboard import (
    BLOCKED_SIEGFRIED_VALUATION_FIELDS,
    VALUATION_SECTIONS,
    displayed_fundamental_metric_names,
    esg_metric_rows,
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
        "Fondamentaux",
        "Valorisation",
        "ESG & sources",
    ]
    assert any(
        all(status in item.value for status in (
            "reported",
            "calculated",
            "unavailable",
            "not_comparable",
        ))
        for item in app.info
    )

    snapshot = next(
        item.value
        for item in app.dataframe
        if "Bachem FY2025" in item.value.columns
    )
    assert set(snapshot.columns) == {
        "Métrique",
        "Bachem FY2025",
        "Statut Bachem",
        "Siegfried FY2025",
        "Statut Siegfried",
    }
    assert {
        "Chiffre d’affaires",
        "Marge EBITDA",
        "Operating cash flow",
        "Dette nette / EBITDA",
        "Equity ratio recalculé",
    } <= set(snapshot["Métrique"])

    fundamental_frames = [
        item.value
        for item in app.dataframe
        if {"Société", "Exercice", "Métrique", "Statut"} <= set(item.value.columns)
    ]
    visible_metrics = {
        metric
        for frame in fundamental_frames
        for metric in frame["Métrique"].tolist()
    }
    assert {
        "Croissance annuelle",
        "Marge EBIT",
        "Marge nette",
        "Operating cash flow / CA",
        "Capex reported / CA",
        "Capex calculated / CA",
        "FCF reported",
        "FCF calculated dans la source",
        "FCF recalculé par AI Quant",
        "Dette nette",
        "ROE sur capitaux propres de clôture",
        "Equity ratio reported",
    } <= visible_metrics
    assert {
        "Cours de clôture historique",
        "Capitalisation boursière publiée",
        "Capitalisation indicative cours × actions",
        "Enterprise Value",
        "EV / Revenue",
        "EV / EBITDA",
        "EV / EBIT",
        "P/E publié",
        "P/E recalculé",
        "P/B recalculé",
        "FCF yield (FCF calculated)",
        "Dividend yield",
        "Scope 1",
        "Scope 2 · market-based",
        "Scope 2 · location-based",
    } <= visible_metrics
    calculated_rows = [
        row
        for frame in fundamental_frames
        for _, row in frame.loc[frame["Statut"] == "calculated"].iterrows()
    ]
    unavailable_rows = [
        row
        for frame in fundamental_frames
        for _, row in frame.loc[frame["Statut"] == "unavailable"].iterrows()
    ]
    assert calculated_rows
    assert all("equity-formulas.v1" in row["Formule / version"] for row in calculated_rows)
    assert all(row["Provenance"] != "indisponible" for row in calculated_rows)
    assert unavailable_rows
    assert all(row["Valeur"] == "—" for row in unavailable_rows)
    assert all(row["Valeur source / non formatée"] == "—" for row in unavailable_rows)
    assert any(
        {"Objectif publié", "Validation déclarée", "Page PDF", "SHA-256"}
        <= set(item.value.columns)
        for item in app.dataframe
    )
    assert any(
        {"Statut d’assurance", "Niveau", "Portée confirmée", "SHA-256"}
        <= set(item.value.columns)
        for item in app.dataframe
    )
    captions = "\n".join(item.value for item in app.caption)
    assert "aucune donnée n’est présentée comme un cours ou une valorisation actuelle" in captions


def test_every_visible_metric_is_traceable_and_unlocked_gate_adds_no_warning(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _equity_app()

    assert not app.exception
    inspection_tables = [
        item.value
        for item in app.table
        if "Valeur source / non formatée" in item.value.columns
    ]
    assert len(inspection_tables) == 4
    for table in inspection_tables:
        assert {
            "Exercice",
            "Valeur source / non formatée",
            "Unité",
            "Statut",
            "Formule",
            "Version",
            "Entrées",
        } <= set(table.columns)

    warning_text = "\n".join(item.value for item in app.warning)
    assert not any(field in warning_text for field in BLOCKED_SIEGFRIED_VALUATION_FIELDS)


def test_snapshot_and_fundamental_contracts_use_phase3_metrics_only() -> None:
    analysis = build_fundamental_analysis()
    rows = snapshot_rows(analysis)

    assert rows
    assert all("valuation" not in row["Métrique"].lower() for row in rows)
    assert all("price" not in name for name in displayed_fundamental_metric_names())
    assert all("market" not in name for name in displayed_fundamental_metric_names())
    assert any(row["Statut Bachem"] == "reported" for row in rows)
    assert any(row["Statut Bachem"] == "calculated" for row in rows)


def test_historical_valuation_scope_split_and_published_precedence() -> None:
    repository = load_equity_repository()
    analysis = build_valuation_analysis(repository)
    all_specs = tuple(spec for _, specs in VALUATION_SECTIONS for spec in specs)
    rows = valuation_rows(analysis, all_specs)

    assert {row["Exercice"] for row in rows} == {
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

    scope_two = [row for row in rows if row["Métrique"].startswith("Scope 2")]
    assert {row["Méthode Scope 2"] for row in scope_two} == {
        "market_based",
        "location_based",
    }
    assert all(row["Statut"] == "reported" for row in scope_two)
    assert all(row["Provenance"] != "indisponible" for row in rows)
    intensities = [row for row in rows if row["Métrique"].startswith("Intensité")]
    assert all(row["Statut"] == "calculated" for row in intensities)
    assert {row["Méthode Scope 2"] for row in intensities} == {
        "market_based",
        "location_based",
    }


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
    'Snapshot', 'Fondamentaux', 'Valorisation', 'ESG & sources'
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
