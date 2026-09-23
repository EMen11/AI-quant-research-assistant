"""Deterministic validation, rendering and automated routing for generated drafts."""

from __future__ import annotations

from ai_quant.content_rules import (
    contains_metric_value,
    evidence_placeholder_ids,
    evidence_supports_numeric_text,
    has_any_placeholder,
    has_generic_placeholder,
    has_implicit_cross_domain_relation,
    has_internal_status_token,
    has_prohibited_risk_language,
    has_unknown_placeholder_kind,
    has_unsupported_period_alignment,
    metric_placeholder_ids,
    numeric_literals,
)
from ai_quant.trust.models import (
    AutomatedAssessment,
    ClaimEvidenceReference,
    ClaimMetricReference,
    EvidenceRecord,
    GeneratedDraft,
    IssueCode,
    MetricRecord,
    RenderedClaim,
    RenderedDraft,
    ValidationIssue,
    ValidationReport,
)


def validate_draft(
    *,
    run_id: str,
    draft: GeneratedDraft,
    metrics: tuple[MetricRecord, ...],
    evidence: tuple[EvidenceRecord, ...],
) -> ValidationReport:
    """Validate all references and quantitative text against current-run records."""

    issues: list[ValidationIssue] = []
    metric_by_id = {record.metric_id: record for record in metrics}
    evidence_by_id = {record.evidence_id: record for record in evidence}

    if has_any_placeholder(draft.summary):
        issues.append(
            ValidationIssue(
                code="summary_placeholder",
                severity="critical",
                message="The summary cannot contain placeholders.",
            )
        )
    _append_prose_issues(
        issues,
        text=draft.summary,
        claim_id=None,
        metrics=metrics,
        evidence_excerpts=(),
        has_metrics=bool(metrics),
        has_evidence=bool(evidence),
    )
    for limitation in draft.limitations:
        if has_any_placeholder(limitation):
            issues.append(
                ValidationIssue(
                    code="unresolved_placeholder",
                    severity="critical",
                    message="Limitations cannot contain unresolved placeholders.",
                )
            )
        _append_prose_issues(
            issues,
            text=limitation,
            claim_id=None,
            metrics=metrics,
            evidence_excerpts=(),
            has_metrics=bool(metrics),
            has_evidence=bool(evidence),
        )

    if draft.run_id != run_id:
        issues.append(
            ValidationIssue(
                code="cross_run_reference",
                severity="critical",
                message="The generated draft does not belong to the active run.",
            )
        )

    for claim in draft.claims:
        metric_placeholders = metric_placeholder_ids(claim.text_template)
        evidence_placeholders = evidence_placeholder_ids(claim.text_template)

        if set(metric_placeholders) != set(claim.metric_ids):
            issues.append(
                ValidationIssue(
                    code="metric_placeholder_mismatch",
                    severity="error",
                    claim_id=claim.claim_id,
                    message="Metric placeholders must exactly match declared metric IDs.",
                )
            )
        if has_generic_placeholder(claim.text_template):
            issues.append(
                ValidationIssue(
                    code="generic_placeholder",
                    severity="critical",
                    claim_id=claim.claim_id,
                    message="Generic placeholders are forbidden.",
                )
            )
        if has_unknown_placeholder_kind(claim.text_template):
            issues.append(
                ValidationIssue(
                    code="unresolved_placeholder",
                    severity="critical",
                    claim_id=claim.claim_id,
                    message="The claim contains an unknown placeholder kind.",
                )
            )

        for metric_id in set(metric_placeholders) - set(claim.metric_ids):
            issue = _missing_reference_issue(
                reference_id=metric_id,
                run_id=run_id,
                expected_prefix="metric",
                known_ids=metric_by_id,
                unknown_code="unknown_metric",
                noun="metric",
                claim_id=claim.claim_id,
            )
            if issue is not None:
                issues.append(issue)
        for evidence_id in set(evidence_placeholders) - set(claim.evidence_ids):
            issue = _missing_reference_issue(
                reference_id=evidence_id,
                run_id=run_id,
                expected_prefix="evidence",
                known_ids=evidence_by_id,
                unknown_code="unknown_evidence",
                noun="evidence",
                claim_id=claim.claim_id,
            )
            if issue is not None:
                issues.append(issue)
        if set(evidence_placeholders) != set(claim.evidence_ids):
            issues.append(
                ValidationIssue(
                    code="evidence_reference_mismatch",
                    severity="error",
                    claim_id=claim.claim_id,
                    message="Evidence placeholders must exactly match declared evidence IDs.",
                )
            )

        for metric_id in claim.metric_ids:
            issue = _missing_reference_issue(
                reference_id=metric_id,
                run_id=run_id,
                expected_prefix="metric",
                known_ids=metric_by_id,
                unknown_code="unknown_metric",
                noun="metric",
                claim_id=claim.claim_id,
            )
            if issue is not None:
                issues.append(issue)
            elif metric_by_id[metric_id].run_id != run_id:
                issues.append(_cross_run_issue(metric_id, "metric", claim.claim_id))

        for evidence_id in claim.evidence_ids:
            issue = _missing_reference_issue(
                reference_id=evidence_id,
                run_id=run_id,
                expected_prefix="evidence",
                known_ids=evidence_by_id,
                unknown_code="unknown_evidence",
                noun="evidence",
                claim_id=claim.claim_id,
            )
            if issue is not None:
                issues.append(issue)
            elif evidence_by_id[evidence_id].run_id != run_id:
                issues.append(_cross_run_issue(evidence_id, "evidence", claim.claim_id))

        if claim.claim_type == "quantitative":
            if numeric_literals(claim.text_template):
                issues.append(
                    ValidationIssue(
                        code="free_numeric_literal",
                        severity="critical",
                        claim_id=claim.claim_id,
                        message=(
                            "Quantitative templates cannot contain free numeric literals; "
                            "Python must inject every value from a MetricRecord."
                        ),
                    )
                )

        evidence_excerpts = tuple(
            evidence_by_id[evidence_id].excerpt
            for evidence_id in claim.evidence_ids
            if evidence_id in evidence_by_id
        )
        claim_fields = [claim.text_template]
        if claim.uncertainty is not None:
            claim_fields.append(claim.uncertainty)
        if claim.claim_type == "evidence":
            for text in claim_fields:
                if numeric_literals(text) and not evidence_supports_numeric_text(
                    text, evidence_excerpts
                ):
                    issues.append(
                        ValidationIssue(
                            code="evidence_numeric_literal_unverified",
                            severity="critical",
                            claim_id=claim.claim_id,
                            message=(
                                "Every numeric evidence fact must occur in an authorized "
                                "source excerpt."
                            ),
                        )
                    )
        for text in claim_fields:
            _append_prose_issues(
                issues,
                text=text,
                claim_id=claim.claim_id,
                metrics=metrics,
                evidence_excerpts=(
                    evidence_excerpts if claim.claim_type == "evidence" else ()
                ),
                has_metrics=bool(metrics),
                has_evidence=bool(evidence),
            )

    identifier_checks_passed = not any(
        issue.code
        in {
            "unknown_metric",
            "unknown_evidence",
            "metric_placeholder_mismatch",
            "evidence_reference_mismatch",
            "generic_placeholder",
            "summary_placeholder",
            "unresolved_placeholder",
        }
        for issue in issues
    )
    value_checks_passed = not any(
        issue.code
        in {
            "free_numeric_literal",
            "metric_value_literal",
            "evidence_numeric_literal_unverified",
        }
        for issue in issues
    )
    run_membership_checks_passed = not any(
        issue.code == "cross_run_reference" for issue in issues
    )
    return ValidationReport(
        run_id=run_id,
        draft_id=draft.draft_id,
        issues=tuple(issues),
        identifier_checks_passed=identifier_checks_passed,
        value_checks_passed=value_checks_passed,
        run_membership_checks_passed=run_membership_checks_passed,
    )


def render_validated_draft(
    *,
    draft: GeneratedDraft,
    report: ValidationReport,
    metrics: tuple[MetricRecord, ...],
    evidence: tuple[EvidenceRecord, ...],
) -> RenderedDraft:
    """Inject trusted values only after a completely non-blocking validation."""

    if (
        report.run_id != draft.run_id
        or report.draft_id != draft.draft_id
        or report.has_blocking_issues
    ):
        return RenderedDraft(
            run_id=draft.run_id,
            draft_id=draft.draft_id,
            reliable=False,
        )

    metric_by_id = {record.metric_id: record for record in metrics}
    evidence_by_id = {record.evidence_id: record for record in evidence}
    rendered_claims: list[RenderedClaim] = []
    for claim in draft.claims:
        text = claim.text_template
        metric_references: list[ClaimMetricReference] = []
        for metric_id in claim.metric_ids:
            metric = metric_by_id[metric_id]
            rendered_value, transformation = _format_metric(metric)
            text = text.replace(
                f"{{{{metric:{metric_id}}}}}",
                f"{rendered_value} ({metric.unit})",
            )
            metric_references.append(
                ClaimMetricReference(
                    run_id=draft.run_id,
                    claim_id=claim.claim_id,
                    metric_id=metric_id,
                    rendered_value=rendered_value,
                    unit=metric.unit,
                    transformation=transformation,
                )
            )

        evidence_references: list[ClaimEvidenceReference] = []
        for evidence_id in claim.evidence_ids:
            evidence_record = evidence_by_id[evidence_id]
            label = (
                "synthetic evidence"
                if evidence_record.status == "synthetic_demo_evidence"
                else "official corpus evidence"
            )
            text = text.replace(
                f"{{{{evidence:{evidence_id}}}}}",
                f"[{label}: {evidence_record.evidence_id}]",
            )
            evidence_references.append(
                ClaimEvidenceReference(
                    run_id=draft.run_id,
                    claim_id=claim.claim_id,
                    evidence_id=evidence_id,
                )
            )

        if has_any_placeholder(text):
            return RenderedDraft(
                run_id=draft.run_id,
                draft_id=draft.draft_id,
                reliable=False,
            )

        rendered_claims.append(
            RenderedClaim(
                run_id=draft.run_id,
                claim_id=claim.claim_id,
                text=text,
                metric_references=tuple(metric_references),
                evidence_references=tuple(evidence_references),
            )
        )

    final_text = "\n\n".join(
        (
            draft.summary,
            *(claim.text for claim in rendered_claims),
            "Limitations: " + " ".join(draft.limitations),
        )
    )
    if has_any_placeholder(final_text):
        return RenderedDraft(
            run_id=draft.run_id,
            draft_id=draft.draft_id,
            reliable=False,
        )
    return RenderedDraft(
        run_id=draft.run_id,
        draft_id=draft.draft_id,
        reliable=True,
        final_text=final_text,
        claims=tuple(rendered_claims),
    )


def assess_draft(
    *,
    run_id: str,
    report: ValidationReport,
    metrics: tuple[MetricRecord, ...],
    evidence: tuple[EvidenceRecord, ...],
) -> AutomatedAssessment:
    """Route the draft without expressing any approval or human decision."""

    if not metrics or not evidence:
        return AutomatedAssessment(
            run_id=run_id,
            status="abstain",
            reason_codes=("insufficient_trusted_inputs",),
        )
    if report.run_id != run_id or report.has_blocking_issues:
        return AutomatedAssessment(
            run_id=run_id,
            status="review_required",
            reason_codes=("blocking_validation_issues",),
        )
    return AutomatedAssessment(
        run_id=run_id,
        status="eligible_for_review",
        reason_codes=("validated_references",),
    )


def _append_prose_issues(
    issues: list[ValidationIssue],
    *,
    text: str,
    claim_id: str | None,
    metrics: tuple[MetricRecord, ...],
    evidence_excerpts: tuple[str, ...],
    has_metrics: bool,
    has_evidence: bool,
) -> None:
    metric_value_found = any(contains_metric_value(text, metric.value) for metric in metrics)
    if metric_value_found and not (
        evidence_excerpts and evidence_supports_numeric_text(text, evidence_excerpts)
    ):
        issues.append(
            ValidationIssue(
                code="metric_value_literal",
                severity="critical",
                claim_id=claim_id,
                message="Metric values must be injected by Python, never written by the LLM.",
            )
        )
    if has_prohibited_risk_language(text):
        issues.append(
            ValidationIssue(
                code="unsupported_risk_statement",
                severity="error",
                claim_id=claim_id,
                message="A single historical metric cannot establish globally limited risk.",
            )
        )
    if has_metrics and has_evidence and has_unsupported_period_alignment(text):
        issues.append(
            ValidationIssue(
                code="unsupported_period_alignment",
                severity="error",
                claim_id=claim_id,
                message="The metric and evidence periods are not explicitly aligned.",
            )
        )
    if has_implicit_cross_domain_relation(text):
        issues.append(
            ValidationIssue(
                code="implicit_cross_domain_relation",
                severity="error",
                claim_id=claim_id,
                message="Financial metrics and ESG evidence cannot imply a relationship.",
            )
        )
    if has_internal_status_token(text):
        issues.append(
            ValidationIssue(
                code="internal_status_token",
                severity="error",
                claim_id=claim_id,
                message="Internal evidence statuses require public natural-language wording.",
            )
        )


def _missing_reference_issue(
    *,
    reference_id: str,
    run_id: str,
    expected_prefix: str,
    known_ids: dict[str, object],
    unknown_code: IssueCode,
    noun: str,
    claim_id: str,
) -> ValidationIssue | None:
    if reference_id in known_ids:
        return None
    if reference_id.startswith(f"{expected_prefix}-{run_id}-"):
        return ValidationIssue(
            code=unknown_code,
            severity="critical",
            claim_id=claim_id,
            message=f"Unknown current-run {noun} ID: {reference_id}.",
        )
    return _cross_run_issue(reference_id, noun, claim_id)


def _cross_run_issue(reference_id: str, noun: str, claim_id: str) -> ValidationIssue:
    return ValidationIssue(
        code="cross_run_reference",
        severity="critical",
        claim_id=claim_id,
        message=f"The {noun} reference is not owned by the active run: {reference_id}.",
    )


def _format_metric(metric: MetricRecord) -> tuple[str, str]:
    if metric.unit.startswith("decimal"):
        return f"{metric.value:.2%}", "percentage"
    return f"{metric.value:.4g}", "rounded"
