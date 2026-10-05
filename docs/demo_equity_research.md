# AI Equity Research Copilot — 60–90 second demo

## Setup

Run the offline application:

```bash
APP_MODE=demo uv run --frozen streamlit run app.py
```

The app opens **Equity research** by default. No network, secret, provider call, database or
adjacent SED checkout is required.

## Finance-first demo path

### 1. Open Equity Research and orient the audience

Start at the **Executive Investment View**.

> This is a reproducible comparison of Bachem and Siegfried, two Swiss CDMOs, using annual
> FY2021–FY2025 data. The first view summarizes growth, profitability, cash generation,
> balance-sheet leverage, returns and historical valuation.

### 2. Show the Research Note

Open **Research Note** with the **Valid** scenario. Point to the Executive Summary and the
eight-KPI Financial Comparison before the company investment cases.

> The note gives the finance view first: the main comparison, company cases, risks, catalysts,
> valuation context, sustainability considerations and honest limitations.

### 3. Explain one important difference

Use the displayed EBITDA margin and cash-conversion values to explain one supported Bachem vs
Siegfried difference. Keep the language descriptive: the data shows different margin, cash and
leverage profiles, not a recommendation.

### 4. Open Valuation

Show the **Historical FY-end data — not current market data** banner and the EV / EBITDA rows.
Point out that Bachem published P/E is unavailable and that Calculated P/E remains a separate
field rather than replacing the missing published figure.

### 5. Show a risk, catalyst or monitoring KPI

Return to **Research Note** and point to **Key risks** and **Catalysts / What to watch**, or open
**Monitoring** to show one KPI, its latest value, why it matters and whether it is available or
needs an update.

### 6. Open one source and provenance example

Open **Inspect source, calculation & technical provenance** for one metric. Show its source,
raw value, formula and page. Explain that technical IDs, versions and SHA-256 fingerprints are
available without dominating the finance view.

### 7. Demonstrate the blocked AI scenario

In **Research Note**, select **Blocked**.

> A forbidden target-price statement blocks reliable rendering. The application shows the
> validation issue and cannot fabricate either a valid-looking note or a human approval.

### 8. Close with the operating model

> Python owns the numbers, AI structures the research, validators check the claims, and the
> analyst remains responsible for the final view.

## Interview pitch

> I built an equity research copilot that turns annual reports into a reproducible financial
> comparison. It lets a finance reader understand the investment case in under a minute while
> keeping every figure, calculation and validation path inspectable on demand.

## Claims to avoid

- Do not describe the project as professional investment research or client work.
- Do not claim investment performance, predictive accuracy or universal AI reliability.
- Do not call `eligible_for_review` an approval.
- Do not describe historical closing values as current market data.
- Do not fill the missing published Bachem P/E or add consensus not present in the pipeline.
