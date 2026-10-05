# Equity V4.1 — Phase 4 validation

Date: 2026-10-05

## Scope

Phase 4 adds a stable top-level Streamlit selector with two isolated routes:

- `Equity research`, selected by default in demo mode;
- `AI audit workbench`, selected by default in live mode.

Only the selected route is rendered. The Equity route does not import the historical audit
workbench or live dashboard, and it performs no network access. The historical workbench keeps
its existing demo and live implementations behind the router.

The Equity dashboard is limited to two tabs in this phase:

- `Snapshot`: descriptive FY2025 Bachem/Siegfried comparison;
- `Fondamentaux`: traceable FY2021–FY2025 fundamental series.

Every displayed row retains its raw value, unit, status, formula/version when applicable, input
metric IDs and locked-source provenance. Missing inputs remain `unavailable`; the UI never
replaces them with zero.

## Valuation boundary

Comparative valuation for Siegfried remains blocked. The UI neither calculates nor displays it
because the locked source lacks all four required market fields for FY2021–FY2025:

- `year_end_share_price`;
- `registered_shares`;
- `market_capitalization_published`;
- `price_to_earnings_published`.

The dashboard validates this exact gate against the embedded valuation diagnostic before
rendering the warning. No market value is inferred, extrapolated or fetched. The Phase 4
valuation and ESG/source tabs described by the broader plan are outside this validated slice.
