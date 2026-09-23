"""Block 6 adapter into the production deterministic validation path."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from ai_quant.evaluation.models import ProposedClaim, WorkflowEvaluationCase
from ai_quant.trust.models import (
    ClaimDraft,
    EvidenceRecord,
    GeneratedDraft,
    GenerationMetadata,
    StructuredReferenceComparison,
    StructuredValidationContext,
    ValidationReport,
)
from ai_quant.trust.validation import validate_draft


def validate_evaluation_case(case: WorkflowEvaluationCase) -> ValidationReport:
    """Adapt a versioned case and return the production validator's exact report."""

    evidence = tuple(
        EvidenceRecord(
            evidence_id=reference.reference_id,
            run_id=reference.run_id,
            document_id=reference.source_id,
            document_sha256=hashlib.sha256(
                reference.document_text.encode("utf-8")
            ).hexdigest(),
            page=1,
            excerpt=reference.document_text,
            period=reference.period,
            unit=reference.unit,
            status="synthetic_demo_evidence",
        )
        for reference in case.inputs.references
    )
    claims = tuple(_production_claim(case, claim) for claim in case.inputs.proposed_claims)
    if not claims:
        claims = (
            ClaimDraft(
                claim_id=f"claim-{case.inputs.run_id}-no-trusted-inputs",
                run_id=case.inputs.run_id,
                text_template="No trusted inputs are available for this evaluation case.",
                claim_type="limitation",
            ),
        )
    draft = GeneratedDraft(
        draft_id=f"draft-{case.case_id}",
        run_id=case.inputs.run_id,
        summary="Deterministic validation evaluation case.",
        claims=claims,
        limitations=("Versioned evaluation input; no live model call.",),
        generation=GenerationMetadata(
            provider="offline-evaluation",
            model_id="deterministic-adapter-v1",
            parameters=(),
            prompt_version="trust-synthesis-v3",
            response_id=f"response-{case.case_id}",
            generated_at=datetime(2026, 9, 23, tzinfo=UTC),
        ),
    )
    context = StructuredValidationContext(
        comparisons=tuple(
            _structured_comparison(case, claim)
            for claim in case.inputs.proposed_claims
        ),
        proposed_claim_keys=tuple(
            claim.claim_key for claim in case.inputs.proposed_claims
        ),
        required_claim_keys=case.required_claims,
        forbidden_claim_keys=case.forbidden_claims,
        minimum_claims=case.inputs.minimum_claims,
    )
    return validate_draft(
        run_id=case.inputs.run_id,
        draft=draft,
        metrics=(),
        evidence=evidence,
        structured_context=context,
    )


def _production_claim(
    case: WorkflowEvaluationCase,
    claim: ProposedClaim,
) -> ClaimDraft:
    if claim.reference_id is None:
        return ClaimDraft(
            claim_id=claim.claim_id,
            run_id=case.inputs.run_id,
            text_template=claim.claim_text,
            claim_type="limitation",
        )
    return ClaimDraft(
        claim_id=claim.claim_id,
        run_id=case.inputs.run_id,
        text_template=f"{claim.claim_text} {{{{evidence:{claim.reference_id}}}}}.",
        claim_type="evidence",
        evidence_ids=(claim.reference_id,),
    )


def _structured_comparison(
    case: WorkflowEvaluationCase,
    claim: ProposedClaim,
) -> StructuredReferenceComparison:
    references = {
        reference.reference_id: reference for reference in case.inputs.references
    }
    reference = references.get(claim.reference_id) if claim.reference_id is not None else None
    return StructuredReferenceComparison(
        claim_id=claim.claim_id,
        claim_key=claim.claim_key,
        reference_present=reference is not None,
        reference_claim_key=None if reference is None else reference.claim_key,
        claim_value=claim.value,
        reference_value=None if reference is None else reference.value,
        claim_unit=claim.unit,
        reference_unit=None if reference is None else reference.unit,
        claim_period=claim.period,
        reference_period=None if reference is None else reference.period,
        claim_scope2_method=claim.scope2_method,
        reference_scope2_method=(
            None if reference is None else reference.scope2_method
        ),
        publication_date=None if reference is None else reference.publication_date,
        cutoff_date=case.inputs.cutoff_date,
        contradicted_by_source_id=(
            None if reference is None else reference.contradicted_by_source_id
        ),
    )
