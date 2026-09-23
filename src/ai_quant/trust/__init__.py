"""Strict trust-boundary contracts and deterministic offline workflow."""

from ai_quant.trust.generation import (
    DraftSchemaError,
    FixtureDraftGenerator,
    GenerationBudget,
    GenerationBudgetExceeded,
    GenerationController,
    GenerationError,
    GenerationTimeout,
    LLMStructuredDraftGenerator,
    StructuredDraftGenerator,
    StructuredGenerationResponse,
)
from ai_quant.trust.models import (
    AutomatedAssessment,
    ClaimDraft,
    ClaimEvidenceReference,
    ClaimMetricReference,
    ClaimProposal,
    DraftProposal,
    EvidenceRecord,
    GeneratedDraft,
    GenerationMetadata,
    HumanReview,
    MetricRecord,
    PublicDemoFixture,
    PublicFixturePromotionReview,
    RenderedClaim,
    RenderedDraft,
    ValidationIssue,
    ValidationReport,
)
from ai_quant.trust.records import create_human_review
from ai_quant.trust.validation import assess_draft, render_validated_draft, validate_draft

__all__ = [
    "AutomatedAssessment",
    "ClaimDraft",
    "ClaimEvidenceReference",
    "ClaimMetricReference",
    "ClaimProposal",
    "DraftProposal",
    "DraftSchemaError",
    "EvidenceRecord",
    "FixtureDraftGenerator",
    "GeneratedDraft",
    "GenerationBudget",
    "GenerationBudgetExceeded",
    "GenerationController",
    "GenerationError",
    "GenerationMetadata",
    "GenerationTimeout",
    "HumanReview",
    "InMemoryTrustWorkflow",
    "LLMStructuredDraftGenerator",
    "MetricRecord",
    "PublicDemoFixture",
    "PublicFixturePromotionReview",
    "RenderedClaim",
    "RenderedDraft",
    "RunStateMachine",
    "StructuredDraftGenerator",
    "StructuredGenerationResponse",
    "ValidationIssue",
    "ValidationReport",
    "WORKFLOW_STEPS",
    "WorkflowResult",
    "WorkflowGenerationError",
    "WorkflowTransitionError",
    "assess_draft",
    "build_synthesis_request",
    "build_demo_trust_scenarios",
    "create_human_review",
    "render_validated_draft",
    "validate_draft",
]

_WORKFLOW_EXPORTS = {
    "WORKFLOW_STEPS",
    "InMemoryTrustWorkflow",
    "RunStateMachine",
    "WorkflowGenerationError",
    "WorkflowResult",
    "WorkflowTransitionError",
    "build_demo_trust_scenarios",
    "build_synthesis_request",
}


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Load workflow exports lazily to keep model-only imports acyclic."""

    if name in _WORKFLOW_EXPORTS:
        from ai_quant.trust import workflow

        return getattr(workflow, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
