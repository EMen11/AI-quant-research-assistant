"""Deterministic rules for untrusted LLM-authored proposal text."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from ai_quant.trust.models import DraftProposal

CanonicalSummaryVersion = Literal["canonical-summary-v1"]
CANONICAL_SUMMARY_VERSION: Final[CanonicalSummaryVersion] = "canonical-summary-v1"
CANONICAL_SUMMARY_METRICS_AND_EVIDENCE: Final = (
    "This report presents historical run metrics and a separate official evidence record. "
    "Each is reported independently, and no temporal, causal, predictive or investment "
    "relationship between them is asserted."
)
CANONICAL_SUMMARY_METRICS_ONLY: Final = (
    "This report presents historical run metrics and their stated limitations. "
    "No predictive or investment conclusion is asserted."
)
CANONICAL_SUMMARY_EVIDENCE_ONLY: Final = (
    "This report presents official evidence records and their stated limitations. "
    "No causal, predictive or investment conclusion is asserted."
)


class CanonicalSummaryError(ValueError):
    """The server cannot select a canonical summary for empty trusted inputs."""


def canonical_summary(*, has_metrics: bool, has_evidence: bool) -> str:
    """Return the versioned server-owned summary for the trusted input shape."""

    if has_metrics and has_evidence:
        return CANONICAL_SUMMARY_METRICS_AND_EVIDENCE
    if has_metrics:
        return CANONICAL_SUMMARY_METRICS_ONLY
    if has_evidence:
        return CANONICAL_SUMMARY_EVIDENCE_ONLY
    raise CanonicalSummaryError(
        "Canonical summary requires at least one metric or evidence record."
    )


def normalize_proposal_summary(
    proposal: DraftProposal,
    *,
    has_metrics: bool,
    has_evidence: bool,
) -> DraftProposal:
    """Replace only the untrusted summary with deterministic server-owned text."""

    normalized = canonical_summary(
        has_metrics=has_metrics,
        has_evidence=has_evidence,
    )
    if proposal.summary == normalized:
        return proposal
    return proposal.model_copy(update={"summary": normalized})

METRIC_PLACEHOLDER = re.compile(r"\{\{metric:([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\}\}")
EVIDENCE_PLACEHOLDER = re.compile(
    r"\{\{evidence:([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\}\}"
)
NUMERIC_LITERAL = re.compile(r"(?<![a-zA-Z\d])[-+]?\d+(?:[.,]\d+)?%?")

_GENERIC_PLACEHOLDER = re.compile(
    r"(?<!\{)\{(?:value|metric|evidence)\}(?!\})|\[(?:value|metric|evidence)\]",
    re.IGNORECASE,
)
_ANY_PLACEHOLDER = re.compile(
    r"\{\{[^{}]+\}\}|(?<!\{)\{[^{}]+\}(?!\})|\[(?:value|metric|evidence)\]",
    re.IGNORECASE,
)
_PROHIBITED_RISK_LANGUAGE = re.compile(
    r"\b(?:limited downside risk|low risk|safe investment|safe strategy)\b",
    re.IGNORECASE,
)
_PERIOD_ALIGNMENT_LANGUAGE = re.compile(
    r"\b(?:same (?:reporting )?period|temporal comparability|"
    r"(?:dates?|periods?)[^.?!]{0,80}\balign(?:ed|ment)?\b)",
    re.IGNORECASE,
)
_SAFE_PERIOD_RESERVATIONS = frozenset(
    {
        (
            "no claim is made that the metrics and the evidence record cover the same "
            "period, as their explicit dates are not confirmed to be equal in the supplied "
            "inputs."
        ),
        "the supplied inputs do not establish temporal comparability.",
        "the periods are not confirmed to align.",
    }
)
_IMPLICIT_CROSS_DOMAIN_RELATION = re.compile(
    r"\b(?:caused by|driven by|due to|correlated with|correlation between|"
    r"associated with|linked to|explains?)\b",
    re.IGNORECASE,
)
_INTERNAL_STATUS_TOKEN = re.compile(
    r"\b(?:reported_zero|not_applicable)\b",
    re.IGNORECASE,
)


def metric_placeholder_ids(text: str) -> tuple[str, ...]:
    """Return canonical metric IDs in textual order."""

    return tuple(METRIC_PLACEHOLDER.findall(text))


def evidence_placeholder_ids(text: str) -> tuple[str, ...]:
    """Return canonical evidence IDs in textual order."""

    return tuple(EVIDENCE_PLACEHOLDER.findall(text))


def has_generic_placeholder(text: str) -> bool:
    """Detect explicitly forbidden non-canonical placeholder spellings."""

    return _GENERIC_PLACEHOLDER.search(text) is not None


def has_any_placeholder(text: str) -> bool:
    """Detect canonical, generic or otherwise unknown placeholder syntax."""

    return _ANY_PLACEHOLDER.search(text) is not None


def has_unknown_placeholder_kind(text: str) -> bool:
    """Detect placeholders that are neither canonical metrics nor canonical evidence."""

    without_known = METRIC_PLACEHOLDER.sub("", EVIDENCE_PLACEHOLDER.sub("", text))
    return _ANY_PLACEHOLDER.search(without_known) is not None


def numeric_literals(text: str) -> tuple[str, ...]:
    """Return numeric tokens after removing canonical reference placeholders."""

    without_placeholders = METRIC_PLACEHOLDER.sub("", text)
    without_placeholders = EVIDENCE_PLACEHOLDER.sub("", without_placeholders)
    return tuple(NUMERIC_LITERAL.findall(without_placeholders))


def contains_metric_value(text: str, value: float) -> bool:
    """Detect exact or renderer-formatted forms of one authoritative metric value."""

    candidates = {
        str(value),
        format(value, ".17g"),
        format(value, ".4g"),
        f"{value:.2%}",
    }
    return any(_contains_numeric_token(text, candidate) for candidate in candidates)


def evidence_supports_numeric_text(text: str, excerpts: tuple[str, ...]) -> bool:
    """Require every numeric token to occur in at least one authorized source excerpt."""

    return all(
        any(_contains_numeric_token(excerpt, token) for excerpt in excerpts)
        for token in numeric_literals(text)
    )


def has_prohibited_risk_language(text: str) -> bool:
    return _PROHIBITED_RISK_LANGUAGE.search(text) is not None


def has_unsupported_period_alignment(text: str) -> bool:
    """Reject alignment language except for explicitly allowlisted epistemic reservations."""

    normalized = " ".join(text.casefold().split())
    if normalized in _SAFE_PERIOD_RESERVATIONS:
        return False
    return _PERIOD_ALIGNMENT_LANGUAGE.search(normalized) is not None


def has_implicit_cross_domain_relation(text: str) -> bool:
    return _IMPLICIT_CROSS_DOMAIN_RELATION.search(text) is not None


def has_internal_status_token(text: str) -> bool:
    return _INTERNAL_STATUS_TOKEN.search(text) is not None


def _contains_numeric_token(text: str, token: str) -> bool:
    return re.search(
        rf"(?<![\d.]){re.escape(token)}(?!\d)",
        text,
        flags=re.IGNORECASE,
    ) is not None
