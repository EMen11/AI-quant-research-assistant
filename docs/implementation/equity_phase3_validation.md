# Equity Research V4.1 — Phase 3 validation

**Scope:** deterministic fundamentals engine for Bachem and Siegfried, FY2021–FY2025.
**Gate result:** PASS.
**Valuation gate:** unchanged and blocked for Siegfried.

## Runtime result

The engine loads only the embedded, hash-validated Equity fixtures and produces:

- 170 authoritative source metrics used by Phase 3;
- 172 derived metrics;
- 25 source/recomputation concordance checks;
- 151 available calculated metrics;
- 21 explicitly unavailable derived metrics;
- zero real-data `not_comparable` metrics;
- 20 concordance checks passing, zero mismatches, and five unavailable checks caused by
  Bachem's absent source equity-ratio field.

Every derived metric, including an unavailable or non-comparable result, retains its intended
formula and `equity-formulas.v1`, input metric IDs, period, unit, inherited field-level source
references, and explicit status. Missing inputs never become zero.

## Available for both companies

- revenue growth for FY2022–FY2025;
- revenue CAGR FY2021–FY2025;
- EBITDA, EBIT, and net margins for every year;
- reported operating cash flow and operating-cash-flow/revenue for every year;
- calculated capex/revenue for every year;
- source calculated FCF, independently recomputed FCF, and calculated-FCF cash conversion;
- net debt and net debt/EBITDA for every year;
- ROE on period-end equity for every year;
- independently recomputed equity ratio for every year;
- separate EBITDA-from-EBIT-and-D&A diagnostic without replacing the authoritative EBITDA.

Siegfried additionally has reported capex/revenue and reported-FCF cash conversion for all five
years. Bachem has an estimated aggregate cash distribution and payout ratio for all five years
because same-year dividend per share and share count are both available.

## Explicit distinctions

- Bachem EBITDA remains `reported`.
- Siegfried EBITDA remains source-`calculated`; its EBIT+D&A recomputation passes the documented
  CHF 0.05 million rounding tolerance in all five years.
- `capex_reported` and `capex_calculated` are never merged.
- `free_cash_flow_reported`, source `free_cash_flow_calculated`, and Phase 3
  `free_cash_flow_recomputed` are separate metrics.
- All ten source calculated-FCF values exactly match operating cash flow plus signed calculated
  capex within CHF 0.001 million.
- Source equity-ratio values for Siegfried match the independent calculation within 0.01
  percentage point.

## Unavailable metrics

- Both issuers: FY2021 year-over-year revenue growth, because FY2020 is outside the approved
  fixture window.
- Bachem: reported capex/revenue FY2021–FY2024; reported-FCF cash conversion FY2021–FY2025.
- Siegfried: estimated cash distribution and payout ratio FY2021–FY2025 because registered shares
  are unavailable.
- Bachem: source equity ratio is unavailable, but the deterministic ratio from total equity and
  total assets is available and remains separately labelled `equity_ratio_recomputed`.

No real-data ratio is non-comparable in the approved period. Unit tests cover zero and negative
denominators, invalid CAGR bases, non-positive share counts, cross-company inputs, mismatched
periods and units, and visible concordance mismatches.

## Valuation boundary

Phase 3 does not consume or create year-end share price, market capitalization, P/E, EV, or other
valuation metrics. The existing Siegfried block remains unchanged for:

- `year_end_share_price`;
- `registered_shares`;
- `market_capitalization_published`;
- `price_to_earnings_published`.

## Verification

- Ruff, targeted Equity scope: PASS.
- Targeted Equity tests: 45 passed.
- Full suite: 624 passed, 38 skipped, 2 pre-existing failures.
- Both failures are the already documented duplicate Alembic revision caused by the untracked
  `20260924_0002_block8_final 2.py`; Phase 3 introduces no new regression.
