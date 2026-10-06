# Bachem / Siegfried equity findings, FY2021–FY2025

This note records the numerical basis for the short findings presented in the project README.
It is an offline, reproducible reading of the committed Equity fixtures. It is not a forecast,
valuation recommendation, target price, or BUY / SELL / HOLD opinion.

## Scope and snapshot identity

- Companies: Bachem Holding AG (`BANB.SW`) and Siegfried Holding AG (`SFZN.SW`).
- Fundamental and historical valuation periods: FY2021–FY2025.
- Comparison endpoint: FY2025.
- Fixture manifest: `src/ai_quant/fixtures/equity/manifest.v1.json`.
- Manifest schema: `equity-snapshot-manifest.v1`.
- Financial fixture schema: `equity-fundamentals.v1`.
- Formula version: `equity-formulas.v1`.
- Manifest SHA-256 at the time of this note:
  `36335177042bb043619791b15914141092ece419f16d2b93aa303445415e8003`.
- Upstream source identifier recorded by the manifest: `SED/pdf.extractor` at revision
  `bc1c54eefd663a257aab71e58fd7953a6239a1fc`.

The manifest records `runtime_external_dependency: false`: downstream analysis can be reproduced
from this repository's committed fixtures without an adjacent Swiss Equity Data checkout or a
network request. The upstream extraction pipeline itself is outside this repository.

## Reproduction

Run this command from the repository root. It loads the authorized fixture, executes the existing
fundamentals and valuation builders, and prints the six metrics used below.

```bash
uv run --frozen python - <<'PY'
from ai_quant.equity.analysis import build_fundamental_analysis
from ai_quant.equity.repository import load_equity_repository
from ai_quant.equity.valuation import build_valuation_analysis

repository = load_equity_repository()
fundamentals = build_fundamental_analysis(repository)
valuation = build_valuation_analysis(repository, fundamentals)

metrics = (
    ("revenue_cagr_2021_2025", fundamentals),
    ("ebitda_margin", fundamentals),
    ("calculated_fcf_cash_conversion", fundamentals),
    ("capex_calculated_to_revenue", fundamentals),
    ("net_debt_to_ebitda", fundamentals),
    ("enterprise_value_to_ebitda", valuation),
)

for company in ("bachem", "siegfried"):
    print(company)
    for name, analysis in metrics:
        metric = analysis.metric(company, 2025, name)
        print(name, metric.value, metric.unit, metric.status, metric.formula.version)
PY
```

## Verified numerical facts

All six outputs are calculated metrics. Percentages and multiples in the README are rounded to one
decimal place; the engine results below retain six decimal places so that the displayed rounding is
auditable.

| Metric | Period and calculation basis | Bachem engine result | Siegfried engine result | README display |
|---|---|---:|---:|---:|
| Revenue CAGR | FY2021–FY2025; reported revenue endpoints over four annual intervals | 8.408826% | 4.760818% | 8.4% / 4.8% |
| EBITDA margin | FY2025; EBITDA / revenue | 30.888975% | 23.986432% | 30.9% / 24.0% |
| Calculated FCF cash conversion | FY2025; calculated free cash flow / EBITDA | -26.931998% | -1.039246% | -26.9% / -1.0% |
| Calculated capex / revenue | FY2025; absolute value of signed calculated capex / revenue | 47.390335% | 17.432074% | 47.4% / 17.4% |
| Net debt / EBITDA | FY2025; (total debt - cash) / EBITDA | 0.122981x | 1.482317x | 0.1x / 1.5x |
| Historical EV / EBITDA | FY2025 fiscal close; (published market capitalization + net debt) / EBITDA | 21.049856x | 11.742914x | 21.0x / 11.7x |

Definition differences remain material. Bachem FY2025 EBITDA is a reported source field. Siegfried
FY2025 EBITDA is a source-calculated field derived from statutory EBIT plus depreciation and
amortization. The comparison therefore retains, rather than conceals, those different input
statuses. Free cash flow and capex in the two rows labelled “calculated” use the fixture's explicit
calculation convention.

Historical EV / EBITDA is based on fiscal-year-end information. It is not a current trading
multiple. Published market capitalization remains distinct from the indicative calculation of
closing price multiplied by registered shares.

## Sources and lineage

The calculations inherit field-level provenance from the following embedded snapshot files:

| Company | Snapshot file | Snapshot SHA-256 | Relevant source periods |
|---|---|---|---|
| Bachem | `BANB.SW_2015_2025_locked_snapshot_v1.csv` | `cf6077a32d26001d7919e4cd194f171e8b667419254257b4ee8f40c7b49aae72` | FY2021 and FY2025 annual reports |
| Siegfried | `SFZN.SW_2015_2025_locked_snapshot_v2.csv` | `63c3b46b8757687c187b129942e02b4f9a536140c0f2e4f5d311786bc4592ba1` | FY2021 and FY2025 annual reports |

The committed application fixtures are `cdmo_fundamentals.v1.csv`, `cdmo_sources.v1.csv`, and
`valuation_diagnostic.v1.json`; their hashes and the source-repository revision are recorded in the
[Equity manifest](../../src/ai_quant/fixtures/equity/manifest.v1.json). A hash establishes artifact
identity and detects a changed file; it does not prove that a financial statement or extraction is
economically true.

The FY2025 climate corpus follows a separate issuer-document pipeline and is not used to produce
the six financial observations in this note.

## Interpretation — pending human review

The following statements are analytical interpretations of the verified outputs, not additional
numeric facts:

- Bachem shows the stronger FY2021–FY2025 revenue growth rate and the higher FY2025 EBITDA margin
  on the recorded definitions.
- The FY2025 calculated free-cash-flow conversion is negative for both companies. Bachem's more
  negative conversion coincides with substantially higher calculated capex intensity; this does not
  by itself establish value creation, value destruction, or an operational deterioration.
- Bachem has lower FY2025 net debt / EBITDA, while Siegfried carries more leverage on the recorded
  EBITDA basis.
- Bachem's FY2025 historical EV / EBITDA is higher. Siegfried's lower multiple does not by itself
  establish undervaluation, because growth, profitability, accounting definitions, risk, timing,
  and market expectations are not held constant.
- The main monitoring trade-off is therefore Bachem's cash conversion and capital intensity versus
  Siegfried's leverage and ability to sustain profitability and cash conversion.

Taken together, the snapshot presents Bachem with faster historical growth, higher recorded margin,
lower leverage, and a higher historical valuation multiple, but also materially heavier FY2025
capital intensity and weaker calculated cash conversion. Siegfried presents slower growth and a
lower margin and multiple, with less negative calculated cash conversion but higher leverage. The
data describes a trade-off; it does not identify an automatic winner.

These new interpretations have not been approved by a human reviewer. They should remain pending
review until an analyst checks the source definitions, comparative framing, and wording.

## Boundaries

- No current prices, live market feed, consensus estimates, forecasts, DCF, or target prices are
  included.
- Historical information does not automatically describe the companies' current position.
- Revenue growth is not labelled organic because the fixture does not supply the required basis.
- Negative free cash flow is not treated as proof of weaker operations.
- A higher margin is not treated as proof of a better investment.
- A lower multiple is not treated as proof of undervaluation.
- Climate values, Scope 2 methods, and assurance boundaries require a separate comparison and are
  documented in the sustainability methodology.
