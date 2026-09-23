"""Deterministic validators over trusted references and untrusted claim fields."""

from __future__ import annotations

from ai_quant.evaluation.models import WorkflowEvaluationCase
from ai_quant.trust.models import ValidationIssue, ValidationReport

_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all instructions",
    "system prompt",
    "approve this",
)


def validate_evaluation_case(case: WorkflowEvaluationCase) -> ValidationReport:
    """Validate a case from its values; expected labels are never read here."""

    issues: list[ValidationIssue] = []
    references = {reference.reference_id: reference for reference in case.inputs.references}
    proposed_keys: set[str] = set()

    for claim in case.inputs.proposed_claims:
        proposed_keys.add(claim.claim_key)
        if claim.requested_assessment is not None:
            issues.append(_issue("self_approval_attempt", claim.claim_id, "Draft requested its own routing outcome."))
        if claim.reference_id is None or claim.reference_id not in references:
            issues.append(_issue("unknown_evidence", claim.claim_id, "Claim reference is not in the active run allowlist."))
            continue
        reference = references[claim.reference_id]
        if not reference.reference_id.startswith(f"evidence-{case.inputs.run_id}-"):
            issues.append(_issue("cross_run_reference", claim.claim_id, "Reference does not belong to the active run."))
        missing = any(
            value is None
            for value in (claim.value, claim.unit, claim.period, claim.scope2_method)
        )
        if missing:
            issues.append(_issue("missing_required_field", claim.claim_id, "Claim is missing a required comparison field."))
            continue
        if claim.value != reference.value:
            issues.append(_issue("reference_value_mismatch", claim.claim_id, "Claimed number differs from the reference value."))
        if claim.unit != reference.unit:
            issues.append(_issue("reference_unit_mismatch", claim.claim_id, "Claimed unit differs from the reference unit."))
        if claim.period != reference.period:
            issues.append(_issue("reference_period_mismatch", claim.claim_id, "Claimed period differs from the reference period."))
        if claim.scope2_method != reference.scope2_method:
            issues.append(_issue("scope2_method_mismatch", claim.claim_id, "Claimed Scope 2 method differs from the reference method."))
        if reference.publication_date > case.inputs.cutoff_date:
            issues.append(_issue("document_after_cutoff", claim.claim_id, "Reference document was published after the run cutoff."))
        if reference.contradicted:
            issues.append(_issue("contradictory_source", claim.claim_id, "The selected source is marked as contradicted."))
        normalized_document = reference.document_text.casefold()
        if any(marker in normalized_document for marker in _INJECTION_MARKERS):
            issues.append(_issue("document_prompt_injection", claim.claim_id, "Document contains instruction-like adversarial text."))

    missing_claims = set(case.required_claims) - proposed_keys
    forbidden_claims = set(case.forbidden_claims) & proposed_keys
    if (
        missing_claims
        or forbidden_claims
        or len(case.inputs.proposed_claims) < case.inputs.minimum_claims
    ):
        issues.append(_issue("insufficient_coverage", None, "Required claim coverage was not satisfied."))

    return ValidationReport(
        run_id=case.inputs.run_id,
        draft_id=f"draft-{case.case_id}",
        issues=tuple(_deduplicate(issues)),
        identifier_checks_passed=not any(
            issue.code in {"unknown_evidence", "cross_run_reference"} for issue in issues
        ),
        value_checks_passed=not any(
            issue.code
            in {
                "reference_value_mismatch",
                "reference_unit_mismatch",
                "reference_period_mismatch",
                "scope2_method_mismatch",
            }
            for issue in issues
        ),
        run_membership_checks_passed=not any(
            issue.code == "cross_run_reference" for issue in issues
        ),
    )


def _issue(code: str, claim_id: str | None, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, severity="critical", claim_id=claim_id, message=message)  # type: ignore[arg-type]


def _deduplicate(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    result: list[ValidationIssue] = []
    seen: set[tuple[str, str | None]] = set()
    for issue in issues:
        key = (issue.code, issue.claim_id)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result
