from __future__ import annotations

from ai_quant.equity.monitoring import build_monitoring_rows, monitoring_table_rows


def test_monitoring_contains_available_kpis_with_sources_and_freshness() -> None:
    rows = build_monitoring_rows()

    available = tuple(row for row in rows if row.freshness == "available")
    assert available
    assert {row.company for row in available} == {"Bachem", "Siegfried"}
    assert all(row.latest_value is not None for row in available)
    assert all(row.display_value != "—" for row in available)
    assert all(row.source_uris for row in available)
    assert all(row.update_frequency == "annual" for row in available)
    assert all(row.predictive is False for row in available)


def test_monitoring_keeps_unavailable_kpi_visible_without_inventing_value() -> None:
    rows = build_monitoring_rows()
    missing = tuple(row for row in rows if row.freshness == "to_update")

    assert len(missing) == 1
    assert missing[0].company == "Bachem"
    assert missing[0].kpi == "Published price to earnings"
    assert missing[0].latest_value is None
    assert missing[0].display_value == "—"
    assert missing[0].source_uris


def test_monitoring_table_has_no_prediction_or_consensus_field() -> None:
    rows = monitoring_table_rows(build_monitoring_rows())

    assert rows
    assert all("prediction" not in " ".join(row).casefold() for row in rows)
    assert all("consensus" not in " ".join(row).casefold() for row in rows)
    assert {row["Fraîcheur"] for row in rows} == {"available", "to_update"}
