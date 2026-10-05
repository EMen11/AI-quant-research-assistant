# Equity source preflight — 2026-10-05

Scope: local copies in `~/Desktop/Projet/sed-equity-source/` only. No Hostinger, network,
adjacent repository, or alternate dataset was accessed. Source files were read and hashed but
not modified.

## Gate result

- Fundamentals FY2021–FY2025: **PASS** for Bachem and Siegfried.
- Comparative historical valuation FY2021–FY2025: **BLOCKED** by missing Siegfried market data.
- Runtime external dependency: **none**. AI Quant loads only embedded derived fixtures.

## Source identities

| Ticker | Artifact | SHA-256 |
|---|---|---|
| BANB.SW | `BANB.SW_2015_2025_locked_snapshot_v1.csv` | `cf6077a32d26001d7919e4cd194f171e8b667419254257b4ee8f40c7b49aae72` |
| BANB.SW | `BANB.SW_2015_2025_locked_snapshot_v1.json` | `9a3c1df90c5cfcfd82a7c247d16326dd4f488e246dc21b7b8f3afdc034e43066` |
| SFZN.SW | `SFZN.SW_2015_2025_locked_snapshot_v1.csv` | `0c879f1d1086427ab6ca8268f331fad82baeea967cbb5f315fd4ede5439c7d9d` |
| SFZN.SW | `SFZN.SW_2015_2025_locked_snapshot_v1.json` | `60ccdef83691806ff8c5d8713cc1fa5e58cc905122c8b4de2e9136759419a7f1` |

## Siegfried authority chain

The Siegfried JSON retains its original internal value
`artifact_type=candidate_snapshot_for_review`; the importer does not reinterpret that field as a
lock. Authority is established separately and fail-closed through all three local reports:

| Report | SHA-256 | Required evidence |
|---|---|---|
| Phase 6A | `c4b78b6543d37b8c3167701615035a66e71c632d2abd24a6cc10a569706cde4d` | locked paths, candidate/locked CSV and JSON hashes, byte-for-byte copy, successful `cmp`, GO |
| Phase 6B | `2499703348a0d2ca502e5a064634002dac082a5841980c1c863df66692b38f01` | artifact presence and byte/schema/row/formula/currency/unit/provenance drift checks all PASS, zero cell drift, GO |
| Phase 7B | `47c68cee5f4eaf34347fe6b638c10623e92a7ae89c42e47c0e52746e074cb868` | locked source paths, product promotion, `protocol_status=full_v2_locked_snapshot`, product validation PASS |

The importer verifies the current local CSV/JSON hashes against the hashes embedded in Phase 6A
and Phase 6B. Missing reports, altered hashes, absent locked paths, a missing PASS, drift, or an
undocumented promotion cause the import to stop before any output is written.

## Projection and status rules

Only FY2021–FY2025 is projected. Source values are not recalculated during import.

- Bachem EBITDA is retained as reported.
- Siegfried EBITDA is retained as calculated from EBIT plus D&A.
- Reported and calculated capex remain separate.
- Reported and calculated FCF remain separate.
- Calculated equity ratio remains identifiable and formula-versioned.
- EPS and dividend per share use `CHF_per_share`, not the row-level CHF-million unit.
- Missing fields remain explicit `unavailable` records and never become zero.
- Bachem and Siegfried split caveats are preserved.
- PDF page numbers are unavailable in these source artifacts and are not invented.

## Valuation diagnostic

Bachem has FY2021–FY2025 year-end share price, shares outstanding, and published market
capitalization. Published P/E is absent from this snapshot projection, although P/E can later be
calculated deterministically from authoritative market capitalization and net income.

Siegfried is missing all four required market columns for FY2021–FY2025:

1. `year_end_share_price`;
2. `registered_shares`;
3. `market_capitalization_published`;
4. `price_to_earnings_published`.

Therefore the fundamentals snapshot, formula engine, and Snapshot/Fundamentals UI work can
continue. Bachem-only historical valuation can continue with a visible limitation. Comparative
Bachem/Siegfried valuation remains blocked until the Siegfried market fields are source-validated.

## Derived runtime artifacts

The product embeds only:

- `cdmo_fundamentals.v1.csv`;
- `cdmo_sources.v1.csv`;
- `valuation_diagnostic.v1.json`;
- `manifest.v1.json`.

The complete SED snapshots and authority reports are not copied into the product. Their names,
hashes, schema versions, authority mode, missing values, caveats, and derived-output hashes are
recorded in the manifest.
