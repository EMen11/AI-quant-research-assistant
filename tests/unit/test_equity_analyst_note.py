from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest
from pydantic import ValidationError

from ai_quant.equity.analyst_note import REQUIRED_LIMITATION_IDS, AnalystNoteV1


def valid_note_payload() -> dict[str, object]:
    metric_id = "metric-run-equity-research-v1-bachem-revenue"
    evidence_id = "evidence-run-equity-research-v1-scope"

    def metric_statement(index: int, text: str) -> dict[str, object]:
        return {
            "statement_id": f"statement-equity-{index}",
            "kind": "calculated_metric",
            "text_template": text + f" {{{{metric:{metric_id}}}}}.",
            "metric_uses": (
                {
                    "metric_id": metric_id,
                    "value": 695.07,
                    "unit": "CHF_millions",
                    "period": "FY2025",
                },
            ),
            "evidence_uses": (),
            "uncertainty": None,
        }

    sections = {
        "comparison_scope": {
            "title": "Objet et date des données",
            "statements": (metric_statement(1, "The comparison uses authorized annual data"),),
        },
        "company_profiles": {
            "title": "Profils et modèles économiques",
            "statements": (
                {
                    "statement_id": "statement-equity-2",
                    "kind": "sourced_fact",
                    "text_template": (
                        "The bounded universe contains Bachem and Siegfried "
                        f"{{{{evidence:{evidence_id}}}}}."
                    ),
                    "metric_uses": (),
                    "evidence_uses": (
                        {
                            "evidence_id": evidence_id,
                            "exact_excerpt": "Bachem and Siegfried are Swiss CDMOs.",
                        },
                    ),
                    "uncertainty": None,
                },
            ),
        },
        "growth_profitability": {
            "title": "Croissance et rentabilité",
            "statements": (metric_statement(3, "Growth and profitability remain distinct"),),
        },
        "cash_balance_capital_allocation": {
            "title": "Cash bilan et allocation du capital",
            "statements": (metric_statement(4, "Cash generation is assessed with balance-sheet context"),),
        },
        "relative_historical_valuation": {
            "title": "Valorisation relative et historique",
            "statements": (metric_statement(5, "Historical valuation is kept separate from current pricing"),),
        },
        "sustainability_comparability": {
            "title": "Durabilité et comparabilité",
            "statements": (metric_statement(6, "Sustainability is described without financial causality"),),
        },
        "favorable_arguments": {
            "title": "Arguments favorables",
            "statements": (metric_statement(7, "The favorable case rests on observed fundamentals"),),
        },
        "risks_attention": {
            "title": "Risques et points d attention",
            "statements": (metric_statement(8, "The risk case includes capital intensity"),),
        },
        "catalysts": {
            "title": "Catalyseurs",
            "statements": (metric_statement(9, "Potential catalysts require later reported confirmation"),),
        },
        "monitoring_indicators": {
            "title": "Indicateurs à suivre",
            "statements": (metric_statement(10, "Monitoring reuses the same authoritative metric"),),
        },
        "comparative_conclusion": {
            "title": "Conclusion comparative",
            "statements": (
                metric_statement(
                    11,
                    "The comparison shows different financial profiles without an investment recommendation",
                ),
            ),
        },
    }
    limitation_texts = (
        "The comparison universe contains only Bachem and Siegfried.",
        "Only annual data are included.",
        "Valuation observations are historical closing values.",
        "No market consensus is included.",
        "No forecast or prediction is produced.",
        "Bachem published price to earnings data are unavailable.",
    )
    return {
        "schema_version": "analyst-note.v1",
        "note_id": "analyst-note-bachem-siegfried-v1",
        "run_id": "run-equity-research-v1",
        "comparison_as_of": date(2026, 3, 12),
        "data_period": "FY2021-FY2025",
        "executive_summary": (
            "Bachem and Siegfried present distinct growth, margin, cash and valuation profiles."
        ),
        "sections": sections,
        "limitations": tuple(
            {"limitation_id": limitation_id, "text": text}
            for limitation_id, text in zip(
                REQUIRED_LIMITATION_IDS, limitation_texts, strict=True
            )
        ),
        "ai_assistance_disclosure": (
            "AI assistance structures the note; Python calculates and validates; "
            "a human analyst decides."
        ),
    }


def test_valid_analyst_note_contract() -> None:
    note = AnalystNoteV1.model_validate(valid_note_payload())

    assert note.schema_version == "analyst-note.v1"
    assert len(note.sections.ordered()) == 11
    assert len(note.statements) == 11
    assert tuple(item.limitation_id for item in note.limitations) == REQUIRED_LIMITATION_IDS


def test_analyst_note_rejects_unknown_field() -> None:
    payload = valid_note_payload()
    payload["approval"] = "approved"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AnalystNoteV1.model_validate(payload)


def test_analyst_note_rejects_missing_required_section() -> None:
    payload = valid_note_payload()
    del payload["sections"]["cash_balance_capital_allocation"]  # type: ignore[index]

    with pytest.raises(ValidationError, match="Field required"):
        AnalystNoteV1.model_validate(payload)


def test_analyst_note_rejects_free_number_without_metric_binding() -> None:
    payload = valid_note_payload()
    metric_id = "metric-run-equity-research-v1-bachem-revenue"
    payload["sections"]["growth_profitability"]["statements"][0][  # type: ignore[index]
        "text_template"
    ] = f"Revenue increased by 12 percent alongside {{{{metric:{metric_id}}}}}."

    with pytest.raises(ValidationError, match="free numeric literals"):
        AnalystNoteV1.model_validate(payload)


def test_analyst_note_rejects_missing_required_limitation() -> None:
    payload = deepcopy(valid_note_payload())
    payload["limitations"] = payload["limitations"][:-1]  # type: ignore[index]

    with pytest.raises(ValidationError, match="every required limitation"):
        AnalystNoteV1.model_validate(payload)


@pytest.mark.parametrize(
    "forbidden_text",
    (
        "This is a BUY.",
        "A target price is warranted.",
        "You should add it to your portfolio.",
    ),
)
def test_analyst_note_rejects_forbidden_advice(forbidden_text: str) -> None:
    payload = valid_note_payload()
    payload["executive_summary"] = forbidden_text

    with pytest.raises(ValidationError):
        AnalystNoteV1.model_validate(payload)
