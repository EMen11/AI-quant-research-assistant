"""Deterministic validation, rendering and automated routing for generated drafts."""

from __future__ import annotations

import re

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

_METRIC_PLACEHOLDER = re.compile(r"\{\{metric:([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\}\}")
_EVIDENCE_PLACEHOLDER = re.compile(
    r"\{\{evidence:([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\}\}"
)
_NUMERIC_LITERAL = re.compile(r"(?<![a-zA-Z])[-+]?\d+(?:[.,]\d+)?%?")


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

    if draft.run_id != run_id:
        issues.append(
            ValidationIssue(
                code="cross_run_reference",
                severity="critical",
                message="The generated draft does not belong to the active run.",
            )
        )

    for claim in draft.claims:
        metric_placeholders = tuple(_METRIC_PLACEHOLDER.findall(claim.text_template))
        evidence_placeholders = tuple(_EVIDENCE_PLACEHOLDER.findall(claim.text_template))

        if set(metric_placeholders) != set(claim.metric_ids):
            issues.append(
                ValidationIssue(
                    code="metric_placeholder_mismatch",
                    severity="error",
                    claim_id=claim.claim_id,
                    message="Metric placeholders must exactly match declared metric IDs.",
                )
            )
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
            text_without_placeholders = _METRIC_PLACEHOLDER.sub("", claim.text_template)
            text_without_placeholders = _EVIDENCE_PLACEHOLDER.sub("", text_without_placeholders)
            if _NUMERIC_LITERAL.search(text_without_placeholders):
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

    identifier_checks_passed = not any(
        issue.code
        in {
            "unknown_metric",
            "unknown_evidence",
            "metric_placeholder_mismatch",
            "evidence_reference_mismatch",
        }
        for issue in issues
    )
    value_checks_passed = not any(
        issue.code == "free_numeric_literal" for issue in issues
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
            text = text.replace(f"{{{{metric:{metric_id}}}}}", rendered_value)
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
            text = text.replace(
                f"{{{{evidence:{evidence_id}}}}}",
                f"[synthetic evidence: {evidence_record.evidence_id}]",
            )
            evidence_references.append(
                ClaimEvidenceReference(
                    run_id=draft.run_id,
                    claim_id=claim.claim_id,
                    evidence_id=evidence_id,
                )
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
