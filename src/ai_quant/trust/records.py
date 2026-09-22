"""Server-side factories for trusted records and deterministic identifiers."""

from __future__ import annotations

import hashlib
from datetime import datetime

from ai_quant.quant import QuantAnalysis
from ai_quant.trust.models import (
    ClaimDraft,
    DraftProposal,
    EvidenceRecord,
    GeneratedDraft,
    GenerationMetadata,
    HumanDisposition,
    HumanReview,
    MetricRecord,
)


def create_metric_records(run_id: str, analysis: QuantAnalysis) -> tuple[MetricRecord, ...]:
    """Create authoritative records from existing Block 2 portfolio metrics."""

    metrics = analysis.portfolio_metrics
    return (
        MetricRecord(
            metric_id=f"metric-{run_id}-cumulative-return",
            run_id=run_id,
            metric_name="cumulative-return",
            value=float(metrics.cumulative_return.value),
            unit=metrics.cumulative_return.unit,
            horizon_or_frequency=metrics.cumulative_return.horizon,
            formula_version=metrics.cumulative_return.formula_version,
            snapshot_id=analysis.snapshot.snapshot_id,
        ),
        MetricRecord(
            metric_id=f"metric-{run_id}-maximum-drawdown",
            run_id=run_id,
            metric_name="maximum-drawdown",
            value=float(metrics.maximum_drawdown.value),
            unit=metrics.maximum_drawdown.unit,
            horizon_or_frequency=metrics.maximum_drawdown.horizon,
            formula_version=metrics.maximum_drawdown.formula_version,
            snapshot_id=analysis.snapshot.snapshot_id,
        ),
    )


def create_fake_evidence(run_id: str) -> tuple[EvidenceRecord, ...]:
    """Create clearly labelled synthetic evidence without invoking a retriever or LLM."""

    excerpt = (
        "Synthetic methodology fixture: demo observations are frozen and non-predictive."
    )
    return (
        EvidenceRecord(
            evidence_id=f"evidence-{run_id}-methodology",
            run_id=run_id,
            document_id="document-synthetic-demo-methodology",
            document_sha256=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            page=1,
            excerpt=excerpt,
            period="Block 3 synthetic demo",
            unit=None,
            status="synthetic_demo_evidence",
        ),
    )


def materialize_generated_draft(
    run_id: str,
    proposal: DraftProposal,
    metadata: GenerationMetadata,
) -> GeneratedDraft:
    """Assign server-owned draft and claim IDs to untrusted structured content."""

    claims = tuple(
        ClaimDraft(
            claim_id=f"claim-{run_id}-{index:02d}",
            run_id=run_id,
            text_template=proposal_claim.text_template,
            claim_type=proposal_claim.claim_type,
            metric_ids=proposal_claim.metric_ids,
            evidence_ids=proposal_claim.evidence_ids,
            uncertainty=proposal_claim.uncertainty,
        )
        for index, proposal_claim in enumerate(proposal.claims, start=1)
    )
    return GeneratedDraft(
        draft_id=f"draft-{run_id}",
        run_id=run_id,
        summary=proposal.summary,
        claims=claims,
        limitations=proposal.limitations,
        generation=metadata,
    )


def create_human_review(
    *,
    run_id: str,
    reviewer_id: str,
    comment: str,
    reviewed_at: datetime,
    disposition: HumanDisposition,
) -> HumanReview:
    """Materialize a review only from explicit human-supplied inputs."""

    return HumanReview(
        run_id=run_id,
        reviewer_id=reviewer_id,
        comment=comment,
        reviewed_at=reviewed_at,
        disposition=disposition,
    )
