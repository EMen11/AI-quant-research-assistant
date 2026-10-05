# Equity V4.1 — Phase 4 and Part 1 validation

Date: 2026-10-06

## Scope

Phase 4 exposes two isolated top-level Streamlit routes:

- `Equity research`, selected by default in demo mode;
- `AI audit workbench`, selected by default in live mode.

Only the selected route is rendered. The Equity route does not import the historical audit
workbench or live dashboard and performs no network access. The historical demo and live
workbench implementations remain behind the existing router.

The Equity dashboard now contains four offline tabs:

- `Snapshot`: descriptive FY2025 Bachem/Siegfried comparison;
- `Fondamentaux`: traceable FY2021–FY2025 fundamental series;
- `Valorisation`: historical closing-date market data, Enterprise Value, multiples and yields;
- `ESG & sources`: FY2025 climate observations, method-specific intensities, targets,
  metric-level assurance, comparability caveats and source documents.

Every financial row retains its raw value, unit, status, formula/version when applicable,
input metric IDs and locked-source provenance. Missing inputs remain `unavailable`; invalid or
incompatible bases remain `not_comparable`; neither is converted to zero.

## Valuation controls

- Published market capitalization and indicative `price × registered shares` capitalization
  remain separate metrics.
- Published market capitalization is the only market-cap basis used for Enterprise Value and
  recalculated valuation multiples.
- SFZN FY2021–FY2025 prices and registered shares use the issuer-published post-split 1:10
  comparative series.
- SFZN FY2021–FY2024 dividend per share remains on its native pre-split basis. The corresponding
  dividend yields are therefore `not_comparable`; no implicit split adjustment is applied.
- Bachem `price_to_earnings_published` remains `unavailable` for all five years. A separately
  labelled recalculated P/E does not replace the missing published field.
- Every market figure is labelled by fiscal year and described as historical, never current.

The comparative gate is `pass`, with readiness `ready_with_source_limitations`. The only source
limitation is Bachem `price_to_earnings_published`.

## ESG controls

The ESG tab consumes only the committed sustainability corpus. Scope 2 market-based and
location-based values and intensities remain separate. Intensities use same-company FY2025
Scope 1, Scope 2 and revenue inputs. Assurance is displayed at metric level, and committed
comparison assessments expose boundary, restatement and assurance caveats. No ESG score is
produced. Documentary evidence records issuer publication; it does not certify physical truth.

## Part 1 acceptance

- Finance: FY2025 comparison, five-year fundamentals and historical multiples are visible;
  accounting bases and share splits are explicit.
- Data engineering: the runtime manifest remains pinned to SED commit
  `bc1c54eefd663a257aab71e58fd7953a6239a1fc`; fixture hashes remain validated and
  `runtime_external_dependency` remains `false`.
- AI engineering: the historical workbench and its valid/blocked controls remain accessible;
  no fail-closed rule was removed.
- Quality: Ruff passes; targeted Equity/ESG/UI/routing tests pass (`84 passed`); the complete
  suite passes (`413 passed, 20 skipped`).

Verdict: **POINT D’ARRÊT 1 — PASS WITH SOURCE LIMITATIONS**.
