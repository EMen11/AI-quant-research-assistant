"""Six-view Streamlit presentation for the offline analyst dashboard."""

from __future__ import annotations

import streamlit as st

from ai_quant.analyst_dashboard import (
    DEMO_REVIEWER_ID,
    HISTORICAL_LIVE_PROVENANCE_LABEL,
    METHODOLOGY_LINKS,
    SCENARIO_LABELS,
    AnalystDashboard,
    DraftRevision,
    EvidenceView,
    ScenarioKey,
    ScenarioSession,
    SessionReviewRepository,
    add_human_review,
    build_analyst_dashboard,
    climate_evidence_groups,
    create_corrected_revision,
    decide_export,
    metric_views,
    validation_issue_path,
    workflow_evidence_views,
)
from ai_quant.config import AppMode, Settings
from ai_quant.trust import WorkflowResult

_CONTENT_ORIGIN_LABELS = {
    "historical-live-provider-normalized-fixture": "Historical normalized demo fixture",
    "synthetic-offline-fixture": "Synthetic offline fixture",
    "human-edited-session-revision": "Human-edited session revision",
}
_SOURCE_GENERATION_ORIGIN_LABELS = {
    "historical-live-provider-normalized-fixture": "Historical Anthropic call",
    "synthetic-offline-fixture": "Synthetic offline fixture",
}
_UNTRUSTED_DRAFT_WARNING = (
    "Untrusted and non-reliable draft proposal. Kept only for audit; not rendered as "
    "final text and not eligible for approved export."
)


def build_demo_view(settings: Settings) -> AnalystDashboard:
    """Compatibility entry point for tests and non-Streamlit consumers."""

    return build_analyst_dashboard(settings)


def main() -> None:
    """Validate startup configuration and render the offline analyst interface."""

    settings = Settings.from_env()
    st.set_page_config(
        page_title="AI Quant Research Workbench",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _render_css()
    st.title("AI Quant Research Workbench")
    st.caption("Analyst review dashboard · traceable evidence · deterministic controls")

    if settings.app_mode is AppMode.LIVE:
        st.warning(
            "Live mode is not part of Block 7. No provider, database, or persistent review "
            "repository is initialized here. Start with APP_MODE=demo."
        )
        return

    dashboard = build_demo_view(settings)
    repository = SessionReviewRepository(st.session_state, dashboard.scenarios)
    scenario = st.selectbox(
        "Demo scenario",
        options=("admissible", "blocked"),
        format_func=lambda value: SCENARIO_LABELS[value],
        help="Both scenarios are deterministic and run entirely from versioned local artifacts.",
    )
    selected: ScenarioKey = scenario
    result = dashboard.scenarios[selected]
    session = repository.get(selected)

    st.info(
        "APP_MODE=demo · offline artifacts only · no provider call · research tool, not "
        "investment advice"
    )
    overview, quant, climate, validation, quality, methodology = st.tabs(
        (
            "Overview",
            "Quant",
            "Climate Evidence",
            "Validation & Review",
            "Quality",
            "Methodology",
        )
    )
    with overview:
        _render_overview(selected, result, session)
    with quant:
        _render_quant(result)
    with climate:
        _render_climate(result, dashboard)
    with validation:
        _render_validation_and_review(selected, result, session, repository)
    with quality:
        _render_quality(result, dashboard, session)
    with methodology:
        _render_methodology()


def _render_overview(
    scenario: ScenarioKey,
    result: WorkflowResult,
    session: ScenarioSession,
) -> None:
    st.header("Overview")
    snapshot = result.analysis.snapshot
    current = session.current
    response_origin = (
        HISTORICAL_LIVE_PROVENANCE_LABEL
        if current.source_generation_origin
        == "historical-live-provider-normalized-fixture"
        else "Manifestly synthetic offline fixture · no provider call"
    )
    current_review = session.current_review
    st.table(
        [
            {"Field": "Scenario", "Value": SCENARIO_LABELS[scenario]},
            {"Field": "Run ID", "Value": result.run_id},
            {"Field": "Run state", "Value": result.state},
            {"Field": "Application mode", "Value": "demo · offline"},
            {
                "Field": "Data origin",
                "Value": f"{snapshot.provider} · {snapshot.artifact_uri}",
            },
            {"Field": "Response origin", "Value": response_origin},
            {"Field": "Snapshot date", "Value": snapshot.retrieved_at.isoformat()},
            {"Field": "Snapshot ID", "Value": snapshot.snapshot_id},
            {"Field": "Snapshot SHA-256", "Value": snapshot.content_sha256},
            {"Field": "Current draft", "Value": current.draft.draft_id},
            {
                "Field": "Current content origin",
                "Value": _CONTENT_ORIGIN_LABELS[current.content_origin],
            },
            {
                "Field": "Source generation origin",
                "Value": _SOURCE_GENERATION_ORIGIN_LABELS[
                    current.source_generation_origin
                ],
            },
            {"Field": "Automated status", "Value": current.assessment.status},
            {
                "Field": "Human review",
                "Value": (
                    f"{current_review.review.disposition} · session-only"
                    if current_review
                    else "not created · session-only"
                ),
            },
        ]
    )
    st.subheader("Primary limitations")
    for limitation in current.draft.limitations:
        st.markdown(f"- {limitation}")
    st.warning(
        "Historical and synthetic demonstration inputs can support research review only. "
        "They are not a forecast, trading signal, or investment recommendation."
    )


def _render_quant(result: WorkflowResult) -> None:
    st.header("Quant")
    analysis = result.analysis
    portfolio = analysis.portfolio
    snapshot = analysis.snapshot
    st.subheader("Portfolio and data window")
    st.table(
        [
            {
                "Portfolio ID": portfolio.portfolio_id,
                "Composition": ", ".join(portfolio.instruments),
                "Weighting": portfolio.weighting_rule,
                "Base currency": portfolio.base_currency,
                "Data window": f"{snapshot.data_start} → {snapshot.data_end}",
                "Cutoff": portfolio.analysis_cutoff.isoformat(),
            }
        ]
    )
    st.caption(
        f"Snapshot {snapshot.snapshot_id} · {snapshot.rows} price rows · "
        f"{len(snapshot.missing_values)} explicit missing prices · "
        f"{len(analysis.return_matrix.dropped_dates)} dropped return dates"
    )

    st.subheader("Authoritative MetricRecord values")
    st.dataframe(
        [
            {
                "Metric ID": item.metric_id,
                "Name": item.name,
                "Value": item.value,
                "Unit": item.unit,
                "Horizon / frequency": item.horizon_or_frequency,
                "Formula version": item.formula_version,
                "Snapshot ID": item.snapshot_id,
            }
            for item in metric_views(result)
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Conventions and assumptions")
    for assumption in analysis.assumptions:
        st.markdown(f"- {assumption}")
    risk_free = analysis.risk_free_rate
    st.caption(
        f"Risk-free assumption: {risk_free.annual_rate:.2%} {risk_free.currency}, "
        f"dated {risk_free.as_of.isoformat()} · {risk_free.source}"
    )

    st.subheader("Available diagnostics")
    diagnostics = analysis.optimization.diagnostics
    st.table(
        [
            {
                "Objective": diagnostics.objective,
                "Converged": diagnostics.converged,
                "Solver success": diagnostics.solver_success,
                "Constraints satisfied": diagnostics.constraints_satisfied,
                "Bounds satisfied": diagnostics.bounds_satisfied,
                "Weight sum": diagnostics.weight_sum,
                "Iterations": diagnostics.iterations,
                "Excluded assets": ", ".join(diagnostics.excluded_assets) or "none",
                "Failure reason": diagnostics.failure_reason or "none",
            }
        ]
    )
    st.warning(
        "Quantitative limits: one small synthetic historical snapshot; no future "
        "performance, buy/sell recommendation, or production-quality claim."
    )


def _render_climate(result: WorkflowResult, dashboard: AnalystDashboard) -> None:
    st.header("Climate Evidence")
    st.caption(
        "Financial metrics and climate evidence remain separate. The artifacts establish no "
        "causal, temporal, predictive, or investment relationship between them."
    )
    st.subheader("Evidence referenced by the selected run")
    _render_evidence_collection(
        workflow_evidence_views(result, dashboard.climate_corpus)
    )

    st.subheader("Versioned official corpus")
    st.caption(
        f"Publication cutoff: {dashboard.climate_corpus.cutoff_date.isoformat()} · "
        "issuer reporting is evidence of disclosure, not proof of physical truth."
    )
    groups = climate_evidence_groups(dashboard.climate_corpus)
    labels = (
        ("Observed results · Scope 2 location-based", "observed_scope2_location"),
        ("Observed results · Scope 2 market-based", "observed_scope2_market"),
        (
            "Observed results · Scope 2 method not applicable",
            "observed_other_method_not_applicable",
        ),
        ("Explicitly reported zero values", "explicitly_reported_zero"),
        ("Issuer-reported climate targets · not observed results", "climate_targets"),
        ("Missing, explicitly unpublished, or ambiguous data", "missing_or_ambiguous"),
    )
    for label, key in labels:
        with st.expander(f"{label} ({len(groups[key])})", expanded=key.startswith("observed_scope2")):
            _render_evidence_collection(groups[key])
    st.subheader("Corpus limitations")
    for limitation in dashboard.climate_corpus.coverage_report.limitations:
        st.markdown(f"- {limitation}")


def _render_evidence_collection(items: tuple[EvidenceView, ...]) -> None:
    if not items:
        st.caption("No record in this versioned category.")
        return
    st.dataframe(
        [
            {
                "Evidence ID": item.evidence_id,
                "Issuer": item.issuer,
                "Document": item.document,
                "Period": item.period,
                "PDF page": str(item.pdf_page) if item.pdf_page is not None else "not available",
                "Printed page": (
                    str(item.printed_page)
                    if item.printed_page is not None
                    else "not available"
                ),
                "Record type": item.record_type,
                "Coverage status": item.coverage_status,
                "Scope 2 method": item.scope_2_method,
            }
            for item in items
        ],
        hide_index=True,
        width="stretch",
    )
    for item in items:
        with st.expander(f"Open evidence · {item.evidence_id}"):
            st.code(item.evidence_id, language=None)
            st.markdown(f"**Excerpt:** {item.excerpt or 'No excerpt available.'}")
            st.caption(f"Source / provenance: {item.source}")
            st.caption(f"Limit: {item.limitation}")


def _render_validation_and_review(
    scenario: ScenarioKey,
    result: WorkflowResult,
    session: ScenarioSession,
    repository: SessionReviewRepository,
) -> None:
    st.header("Validation & Review")
    revision_options = tuple(revision.version for revision in session.revisions)
    selected_version = st.selectbox(
        "Draft history",
        options=revision_options,
        index=len(revision_options) - 1,
        format_func=lambda value: f"v{value:02d}",
        key=f"history-{scenario}-current-{session.current.version}",
    )
    revision = next(item for item in session.revisions if item.version == selected_version)
    _render_revision(revision)

    st.subheader("Status semantics")
    st.markdown(
        "- `eligible_for_review`: a human may review it; it is **not approved**.\n"
        "- `review_required`: blocking deterministic findings are present.\n"
        "- `abstain`: trusted inputs are insufficient.\n"
        "- `HumanReview`: an explicit decision made only by a human."
    )

    st.subheader("Human review · session-only")
    st.info(
        f"Reviewer label: `{DEMO_REVIEWER_ID}` · unauthenticated. Reviews are stored only "
        "in the current Streamlit session. They are not persisted and may disappear after "
        "reload, disconnect, or a new browser session."
    )
    _render_review_history(session)

    current = session.current
    dispositions = ["corrected", "rejected", "escalated"]
    if current.assessment.status == "eligible_for_review" and current.rendered_draft.reliable:
        dispositions.insert(0, "approved")
    with st.form(f"review-form-{scenario}", clear_on_submit=False):
        disposition = st.selectbox("Disposition", options=dispositions)
        comment = st.text_input("Review comment", value="Demo review; no authenticated identity.")
        corrected_summary = st.text_area(
            "Corrected summary (used only when disposition is corrected)",
            value=current.draft.summary,
            height=100,
        )
        corrected_claims = tuple(
            st.text_area(
                f"Corrected claim {index}",
                value=claim.text_template,
                height=90,
                key=f"correction-{scenario}-{current.version}-{index}",
            )
            for index, claim in enumerate(current.draft.claims, start=1)
        )
        submitted = st.form_submit_button("Record session-only review")
    if submitted:
        try:
            if disposition == "corrected":
                updated = create_corrected_revision(
                    session,
                    result,
                    summary=corrected_summary,
                    claim_templates=corrected_claims,
                    comment=comment,
                )
            else:
                updated = add_human_review(
                    session,
                    disposition=disposition,
                    comment=comment,
                )
            repository.put(scenario, updated)
            st.success("Session-only review recorded. The page will show the updated state.")
            st.rerun()
        except ValueError as error:
            st.error(str(error))

    st.subheader("Approved export policy")
    decision = decide_export(session)
    if decision.allowed:
        assert decision.payload is not None and decision.filename is not None
        st.download_button(
            "Download approved current version",
            data=decision.payload,
            file_name=decision.filename,
            mime="application/json",
        )
        st.success(decision.reason)
    else:
        st.warning(decision.reason)


def _render_revision(revision: DraftRevision) -> None:
    is_untrusted = (
        not revision.rendered_draft.reliable
        or revision.assessment.status in {"review_required", "abstain"}
    )
    if revision.content_origin == "human-edited-session-revision":
        st.subheader(f"Human-edited session revision · v{revision.version:02d}")
        st.info(
            "The current text was edited by a human in this session. Historical model "
            "metadata belongs to the source generation, not to this edited revision."
        )
    elif is_untrusted:
        st.subheader(f"Blocked draft proposal · failed validation · v{revision.version:02d}")
    else:
        st.subheader(f"Untrusted generated proposal · v{revision.version:02d}")
    if is_untrusted:
        st.warning(_UNTRUSTED_DRAFT_WARNING)
    st.caption(
        f"Current content origin: `{_CONTENT_ORIGIN_LABELS[revision.content_origin]}` · "
        "source generation: "
        f"`{_SOURCE_GENERATION_ORIGIN_LABELS[revision.source_generation_origin]}`"
    )
    if is_untrusted:
        _render_validation_report(revision)
    st.code(revision.draft.draft_id, language=None)
    st.write(revision.draft.summary)
    st.dataframe(
        [
            {
                "Claim ID": claim.claim_id,
                "Type": claim.claim_type,
                "Template": claim.text_template,
                "Metric IDs": ", ".join(claim.metric_ids) or "none",
                "Evidence IDs": ", ".join(claim.evidence_ids) or "none",
                "Uncertainty": claim.uncertainty or "not supplied",
            }
            for claim in revision.draft.claims
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Deterministically rendered text")
    if revision.rendered_draft.reliable:
        st.text(revision.rendered_draft.final_text or "")
        st.caption("Reliable rendering means validated references; it does not mean approved.")
    else:
        st.error("No reliable final text is emitted for this blocked version.")

    if not is_untrusted:
        _render_validation_report(revision)
    st.subheader("AutomatedAssessment")
    st.table(
        [
            {
                "Status": revision.assessment.status,
                "Reason codes": ", ".join(revision.assessment.reason_codes),
                "Human approval": "not implied",
            }
        ]
    )


def _render_validation_report(revision: DraftRevision) -> None:
    st.subheader("ValidationReport")
    report = revision.validation_report
    st.caption(
        f"Trusted inputs: {report.trusted_input_count} · identifier checks: "
        f"{report.identifier_checks_passed} · value checks: {report.value_checks_passed} · "
        f"run membership: {report.run_membership_checks_passed}"
    )
    if report.issues:
        st.markdown("**Full finding messages**")
        for issue in report.issues:
            path = validation_issue_path(issue.claim_id)
            with st.expander(f"{issue.code} · {issue.severity} · {path}"):
                st.code(path, language=None)
                st.write(issue.message)
        st.dataframe(
            [
                {
                    "Code": issue.code,
                    "Severity": issue.severity,
                    "Path": validation_issue_path(issue.claim_id),
                    "Message": issue.message,
                }
                for issue in report.issues
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.success("ValidationReport contains no finding.")


def _render_review_history(session: ScenarioSession) -> None:
    if not session.reviews:
        st.caption("No HumanReview has been created in this session.")
        return
    st.dataframe(
        [
            {
                "Draft ID": item.draft_id,
                "Revision": item.revision_number,
                "Approved draft SHA-256": item.approved_draft_sha256 or "not applicable",
                "Approved text SHA-256": item.approved_final_text_sha256 or "not applicable",
                "Disposition": item.review.disposition,
                "Reviewer": item.review.reviewer_id,
                "Reviewed at UTC": item.review.reviewed_at.isoformat(),
                "Comment": item.review.comment,
            }
            for item in session.reviews
        ],
        hide_index=True,
        width="stretch",
    )


def _render_quality(
    result: WorkflowResult,
    dashboard: AnalystDashboard,
    session: ScenarioSession,
) -> None:
    st.header("Quality")
    retrieval = dashboard.quality.retrieval
    st.subheader("Retrieval evaluation")
    st.caption(
        f"Source: `{retrieval.source_path}` · schema `{retrieval.schema_version}` · "
        f"gold set `{retrieval.gold_set_path}` · SHA-256 `{retrieval.gold_set_sha256}` · "
        f"{retrieval.question_count} questions"
    )
    st.markdown("**Overall**")
    st.dataframe(retrieval.overall_rows, hide_index=True, width="stretch")
    st.markdown("**Ranking-only**")
    st.dataframe(retrieval.ranking_rows, hide_index=True, width="stretch")
    ranking_question_count = retrieval.ranking_rows[0]["Questions"]
    st.warning(
        f"{retrieval.question_count} gold questions in total, including "
        f"{ranking_question_count} ranking-only cases. These sample sizes are descriptive "
        "and too small for broad performance claims."
    )
    for failure in retrieval.observed_failures:
        st.warning(f"Observed retrieval failure: {failure}")
    st.caption(
        "Recall is measured only on the versioned gold set. The long-context baseline uses "
        "canonical order; latency is intentionally absent from the deterministic artifact."
    )

    workflow = dashboard.quality.workflow
    st.subheader("Workflow evaluation")
    st.caption(
        f"Source: `{workflow.source_path}` · schema `{workflow.schema_version}` · dataset "
        f"`{workflow.dataset_version}` · SHA-256 `{workflow.dataset_sha256}` · "
        f"{workflow.case_count} cases"
    )
    split_columns = st.columns(3)
    for column, (split, count) in zip(split_columns, workflow.split_counts, strict=True):
        column.metric(split, count)
    st.dataframe(
        [{"Cell": key, "Count": value} for key, value in workflow.confusion_matrix],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"False eligible_for_review: {workflow.false_eligible_count}/"
        f"{workflow.false_eligible_denominator} critical cases."
    )
    st.dataframe(
        [
            {
                "Error type": name,
                "Detected": detected,
                "Total": total,
                "Rate": f"{rate:.0%}",
            }
            for name, detected, total, rate in workflow.rates_by_type
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Versioned model-call metadata")
    call = result.draft.generation.model_call
    if call is None:
        st.caption("No model-call metadata exists for this scenario.")
    else:
        if call.response_origin == "live_provider":
            st.info(
                f"{HISTORICAL_LIVE_PROVENANCE_LABEL}. Tokens, latency, cost and "
                "`schema_error` below describe that historical call, not the current "
                "offline demo run."
            )
        if session.current.content_origin == "human-edited-session-revision":
            st.info(
                "The current draft is a human-edited session revision. Model metadata below "
                "belongs only to its source generation."
            )
        st.table(
            [
                {
                    "Provider": call.provider,
                    "Model": call.model_id,
                    "Status": call.status,
                    "Input tokens": call.input_tokens if call.input_tokens is not None else "absent",
                    "Output tokens": call.output_tokens if call.output_tokens is not None else "absent",
                    "Latency ms": (
                        call.latency_ms
                        if call.response_origin in {"live_provider", "mocked_provider"}
                        else "not measured · synthetic fixture"
                    ),
                    "Retries": call.retry_count,
                    "Estimated cost": (
                        f"{call.cost_estimate} {call.currency}"
                        if call.cost_estimate is not None
                        else call.cost_unavailable_reason or "absent"
                    ),
                    "Pricing snapshot": call.pricing_snapshot_id or "absent",
                    "Origin": call.response_origin,
                }
            ]
        )

    st.subheader("Scope and P2 limitations")
    limitations = (
        workflow.scope_statement,
        "Many error categories have only 1/1 positive case; those rates must not be generalized.",
        "The deterministic injection detector is bounded to versioned attack families.",
        "Benign wording close to an instruction may produce a false positive.",
        "StructuredValidationContext is not fully populated by the current demo workflow.",
        "The holdout is versioned, but neither external nor historically blind.",
        "Timing is hardware-, cache-, scheduling-, and load-dependent and is not portable.",
    )
    for limitation in limitations:
        st.markdown(f"- {limitation}")


def _render_methodology() -> None:
    st.header("Methodology")
    st.subheader("Run architecture and authority")
    st.table(
        [
            {"Stage": "1", "Authority": "Python", "Responsibility": "loads and calculates"},
            {"Stage": "2", "Authority": "Retriever", "Responsibility": "selects evidence"},
            {"Stage": "3", "Authority": "LLM / offline fixture", "Responsibility": "proposes a draft"},
            {"Stage": "4", "Authority": "Python", "Responsibility": "validates and renders"},
            {"Stage": "5", "Authority": "Policy", "Responsibility": "classifies review routing"},
            {"Stage": "6", "Authority": "Human", "Responsibility": "decides explicitly"},
        ]
    )
    st.markdown(
        "`MetricRecord` is calculated data; `EvidenceRecord` is cited source material; "
        "`GeneratedDraft` is an untrusted proposal; `ValidationReport` is deterministic; "
        "`AutomatedAssessment` routes work; `HumanReview` alone records a human decision."
    )
    st.info(
        "Demo mode runs offline from frozen artifacts. It does not initialize Anthropic, access "
        "PostgreSQL, persist reviews, refresh market data, or establish production performance."
    )
    st.subheader("Versioned methods and evaluation")
    for link in METHODOLOGY_LINKS:
        st.markdown(f"- [{link.label}]({link.url})")
    st.caption(
        "The evaluations cover only their exact versioned datasets, corpus, rules and attack "
        "families. They do not establish universal prompt-injection protection or production rates."
    )


def _render_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1180px; padding-top: 1.4rem; padding-bottom: 2rem;}
        h1 {font-size: 2rem; margin-bottom: .2rem;}
        h2 {font-size: 1.35rem; margin-top: 1rem;}
        h3 {font-size: 1.05rem; margin-top: .8rem;}
        [data-testid="stDataFrame"] {font-size: .86rem;}
        [data-testid="stMetricValue"] {font-size: 1.35rem;}
        code {overflow-wrap: anywhere; white-space: pre-wrap;}
        @media (max-width: 700px) {
          .block-container {padding: .8rem .65rem 1.5rem;}
          h1 {font-size: 1.55rem;}
          [data-baseweb="tab-list"] {overflow-x: auto; flex-wrap: nowrap;}
          [data-testid="stHorizontalBlock"] {flex-wrap: wrap;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
