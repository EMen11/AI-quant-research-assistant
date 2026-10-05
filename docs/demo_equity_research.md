# AI Equity Research Copilot — 60–90 second demo

## Setup

Run the offline application:

```bash
APP_MODE=demo uv run --frozen streamlit run app.py
```

The app opens **Equity research** by default. No network, secret, provider call, database or
adjacent SED checkout is required.

## Demo path

### First fifteen seconds — business question

Open **Snapshot**.

> This is a reproducible comparison of Bachem and Siegfried, two Swiss CDMOs, using annual
> FY2021–FY2025 data. Python calculates the metrics and every displayed number retains its
> status and provenance.

Point to FY2025 revenue, EBITDA margin, cash conversion and leverage. Explain that published,
calculated, unavailable and non-comparable values are never merged.

### Next twenty seconds — history and valuation

Open **Fondamentaux**, then **Valorisation**.

> The five-year view separates growth, profitability, cash flow, capex and balance-sheet
> metrics. Valuation uses historical fiscal-closing data, not current prices. Published market
> capitalization remains separate from the indicative price-times-shares calculation.

Point out the visible Bachem limitation: published P/E is unavailable; the recalculated P/E is
shown separately and never substituted for the missing source field.

### Next fifteen seconds — sustainability and provenance

Open **ESG & sources**.

> Scope two methods remain separate, assurance is attached at metric level, and documentary
> evidence shows what the issuer published rather than claiming physical verification. No
> finance-climate causality or ESG score is inferred.

Open one metric inspector or source row to show unit, formula, inputs, page and source hash.

### Final twenty to thirty seconds — note, controls and human review

Open **Research note** with the **Admissible** scenario.

> The note contract separates sourced facts, calculated metrics, analyst interpretation and
> limitations. The generator sees only allowlisted metric and Evidence records. Independent
> validators check IDs, values, units, periods, excerpts and prohibited output. Automation can
> make the note eligible for review, but it cannot approve it.

Show `pending_human_review`, the source links and monitoring freshness. Then select **Bloqué**.

> A forbidden target-price statement blocks reliable rendering and routes the result to review.
> No valid-looking note and no human approval are fabricated.

## Interview pitch

> J’ai construit un copilote de recherche actions qui transforme des rapports annuels en une
> comparaison financière reproductible. Python calcule les métriques, chaque chiffre reste lié
> à sa source, l’IA aide à structurer la note, puis des validateurs indépendants contrôlent ses
> affirmations avant revue humaine.

## Claims to avoid

- Do not describe the project as professional investment research or client work.
- Do not claim investment performance, predictive accuracy or universal AI reliability.
- Do not call `eligible_for_review` an approval.
- Do not describe historical closing values as current market data.
- Do not fill the missing published Bachem P/E or add consensus not present in the pipeline.
