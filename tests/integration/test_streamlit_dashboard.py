from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _app() -> AppTest:
    return AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=20).run()


def test_dashboard_renders_exactly_six_views_with_responsive_structure(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    app = _app()

    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Overview",
        "Quant",
        "Climate Evidence",
        "Validation & Review",
        "Quality",
        "Methodology",
    ]
    assert any("@media (max-width: 700px)" in item.value for item in app.markdown)
    assert any("stored only in the current Streamlit session" in item.value for item in app.info)


def test_admissible_ui_displays_ids_units_pages_excerpts_and_separate_statuses(
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _app()

    metric_frame = app.dataframe[0].value
    run_evidence_frame = app.dataframe[1].value
    assert "Metric ID" in metric_frame.columns
    assert "Unit" in metric_frame.columns
    assert metric_frame["Metric ID"].str.startswith("metric-run-demo-valid").all()
    assert "Evidence ID" in run_evidence_frame.columns
    assert "PDF page" in run_evidence_frame.columns
    assert "Record type" in run_evidence_frame.columns
    assert "Coverage status" in run_evidence_frame.columns
    assert run_evidence_frame.iloc[0]["Coverage status"] == "reported_zero"
    assert run_evidence_frame.iloc[0]["PDF page"] == "33"
    assert any("TOTAL FUEL CONSUMPTION" in item.value for item in app.markdown)
    assert any(
        "Automated status" in str(table.value) and "Human review" in str(table.value)
        for table in app.table
    )


def test_blocked_ui_shows_findings_and_has_no_approval_or_export(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _app()
    app.selectbox[0].select("blocked").run()

    assert not app.exception
    finding_frames = [
        item.value for item in app.dataframe if "Code" in item.value.columns
    ]
    assert len(finding_frames) == 1
    findings = finding_frames[0]
    assert {"Code", "Severity", "Path", "Message"} <= set(findings.columns)
    assert not findings.empty
    disposition = next(item for item in app.selectbox if item.label == "Disposition")
    assert "approved" not in disposition.options
    assert not app.get("download_button")
    assert any("No reliable final text" in error.value for error in app.error)
    assert any("Export blocked" in warning.value for warning in app.warning)
    assert any(
        "Blocked draft proposal · failed validation" in header.value
        for header in app.subheader
    )
    assert any(
        "Untrusted and non-reliable draft proposal" in warning.value
        and "not eligible for approved export" in warning.value
        for warning in app.warning
    )
    assert len(app.expander) >= len(findings)
    call_table = next(table.value for table in app.table if "Origin" in table.value.columns)
    assert call_table.iloc[0]["Latency ms"] == "not measured · synthetic fixture"


def test_new_apptest_session_starts_without_human_review(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    first = _app()
    second = _app()

    assert not first.exception and not second.exception
    assert any("no HumanReview" in warning.value for warning in first.warning)
    assert any("no HumanReview" in warning.value for warning in second.warning)
    assert any("may disappear after reload" in info.value for info in first.info)


def test_explicit_approval_enables_current_version_export(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _app()

    app.button[0].click().run()

    assert not app.exception
    downloads = app.get("download_button")
    assert len(downloads) == 1
    assert downloads[0].label == "Download approved current version"
    assert any("Approved export available" in item.value for item in app.success)


def test_ui_correction_creates_v2_and_invalidates_prior_review(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _app()
    disposition = next(item for item in app.selectbox if item.label == "Disposition")
    disposition.select("corrected")
    app.text_area[0].set_value(app.text_area[0].value + " Editorial correction.")

    app.button[0].click().run()

    assert not app.exception
    history = next(item for item in app.selectbox if item.label == "Draft history")
    assert history.options == ["v01", "v02"]
    assert history.value == 2
    assert any("Human-edited session revision" in item.value for item in app.subheader)
    assert any("source generation" in item.value for item in app.info)
    overview = next(table.value for table in app.table if "Field" in table.value.columns)
    overview_values = overview.set_index("Field")["Value"]
    assert overview_values["Current content origin"] == "Human-edited session revision"
    assert overview_values["Source generation origin"] == "Historical Anthropic call"
    assert not app.get("download_button")
    assert any("current draft version has no HumanReview" in item.value for item in app.warning)


def test_human_edited_revision_that_fails_validation_keeps_untrusted_banner(
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _app()
    app.selectbox[0].select("blocked").run()
    app.text_area[0].set_value(app.text_area[0].value + " Human edit remains blocked.")
    submit = next(
        item for item in app.button if item.label == "Record session-only review"
    )

    submit.click().run()

    assert not app.exception
    assert any("Human-edited session revision · v02" in item.value for item in app.subheader)
    assert any(
        "Untrusted and non-reliable draft proposal" in warning.value
        and "not eligible for approved export" in warning.value
        for warning in app.warning
    )
    assessment = next(
        table.value for table in app.table if "Status" in table.value.columns
    )
    assert assessment.iloc[0]["Status"] == "review_required"
    assert not app.get("download_button")


def test_historical_provenance_and_retrieval_sample_limits_are_explicit(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    app = _app()

    exact_provenance = (
        "Historical live-provider call · original semantic validation failed · "
        "deterministically normalized and human-reviewed for offline demo use"
    )
    overview = next(table.value for table in app.table if "Field" in table.value.columns)
    response_origin = overview.loc[overview["Field"] == "Response origin", "Value"].iloc[0]
    assert response_origin == exact_provenance
    assert any(
        "Tokens, latency, cost and `schema_error` below describe that historical call"
        in info.value
        for info in app.info
    )
    assert any(
        "10 gold questions in total, including 4 ranking-only cases" in warning.value
        and "too small for broad performance claims" in warning.value
        for warning in app.warning
    )
