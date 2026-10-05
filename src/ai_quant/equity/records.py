"""Adapters from immutable Equity values to run-bound trust records."""

from __future__ import annotations

import hashlib
import re

from ai_quant.equity.models import MetricValue
from ai_quant.sustainability import SustainabilityCorpus
from ai_quant.trust.models import EvidenceRecord, MetricRecord

EQUITY_SNAPSHOT_ID = "equity-research-snapshot-v1"
RESEARCH_SCOPE_EXCERPT = (
    "Bachem Holding AG and Siegfried Holding AG are the two Swiss CDMOs in scope."
)


def create_equity_metric_records(
    run_id: str,
    metrics: tuple[MetricValue, ...],
) -> tuple[MetricRecord, ...]:
    """Create deterministic trust records from available authoritative Equity metrics."""

    records: list[MetricRecord] = []
    for metric in sorted(metrics, key=lambda item: item.metric_id):
        if not metric.is_available or metric.value is None:
            continue
        formula_version = (
            metric.formula.version if metric.formula is not None else "issuer-reported-v1"
        )
        records.append(
            MetricRecord(
                metric_id=metric_record_id(run_id, metric.metric_id),
                run_id=run_id,
                metric_name=metric_record_name(metric.company_id, metric.name),
                value=float(metric.value),
                unit=metric.unit,
                horizon_or_frequency=f"FY{metric.fiscal_year}",
                formula_version=formula_version,
                snapshot_id=EQUITY_SNAPSHOT_ID,
            )
        )
    ids = tuple(record.metric_id for record in records)
    if len(ids) != len(set(ids)):
        raise ValueError("Equity MetricRecord IDs must be unique.")
    return tuple(records)


def create_equity_evidence_records(
    run_id: str,
    corpus: SustainabilityCorpus,
) -> tuple[EvidenceRecord, ...]:
    """Create the bounded research-scope and FY2025 climate Evidence allowlist."""

    evidence = [
        EvidenceRecord(
            evidence_id=f"evidence-{run_id}-scope",
            run_id=run_id,
            document_id="document-equity-research-scope",
            document_sha256=hashlib.sha256(
                RESEARCH_SCOPE_EXCERPT.encode("utf-8")
            ).hexdigest(),
            page=1,
            excerpt=RESEARCH_SCOPE_EXCERPT,
            period="V4.1 bounded comparison scope",
            unit=None,
            status="synthetic_demo_evidence",
        )
    ]
    wanted = {
        "observation-bachem-2025-scope-two-market",
        "observation-siegfried-2025-scope-two-market",
    }
    for observation in sorted(corpus.observations, key=lambda item: item.observation_id):
        if observation.observation_id not in wanted:
            continue
        evidence.append(
            EvidenceRecord(
                evidence_id=f"evidence-{run_id}-{_identifier(observation.observation_id)}",
                run_id=run_id,
                document_id=observation.document_id,
                document_sha256=observation.document_sha256,
                page=observation.pdf_page,
                excerpt=observation.short_exact_excerpt,
                period=f"FY{observation.period_end.year}",
                unit=observation.unit,
                status="official_corpus_passage",
                passage_id=f"passage-{_identifier(observation.observation_id)}",
                source_record_type="sustainability-observation",
                source_record_id=observation.observation_id,
                issuer_id=observation.issuer_id,
                publication_date=observation.publication_date,
                printed_page=observation.printed_page,
            )
        )
    if len(evidence) != 3:
        raise ValueError("The Equity Research Evidence allowlist is incomplete.")
    return tuple(evidence)


def metric_record_id(run_id: str, source_metric_id: str) -> str:
    """Return the stable trust identifier for one source Equity metric."""

    return _identifier(f"metric-{run_id}-{source_metric_id}")


def metric_record_name(company_id: str, metric_name: str) -> str:
    """Return the canonical trust metric name for Equity lookup."""

    return _identifier(f"{company_id}-{metric_name}")


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not normalized or not normalized[0].isalpha():
        normalized = f"id-{normalized}"
    return normalized
