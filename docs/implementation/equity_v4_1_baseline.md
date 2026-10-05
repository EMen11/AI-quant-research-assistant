# Equity Research Copilot V4.1 — implementation baseline

Baseline captured on 2026-10-05 before the first Equity-domain change.

## Application repository

- Repository: `ai-quant-research-assistant`
- Branch: `main`
- Revision: `bfc9fc6efa409eb395a0df1eabf25317f695ae09`
- Working tree: contains pre-existing untracked plans, assets, and `* 2.*` duplicate files.
- Safety decision: no pre-existing untracked file is deleted, renamed, or adopted silently.

## Upstream data repository

- Repository: adjacent local checkout `pdf.extractor`
- Branch: `main`
- Working revision: `3cd0cbcb6f750324d2177242e4f024241cbc66a2`
- Recorded upstream revision: `origin/main` at
  `146ef2d491bf9b496f1008d5ba643ffbe376d137`.
- Divergence at baseline: local branch is 188 commits behind its recorded upstream ref.
- Working tree: clean.
- Decision: do not modify or use the lagging checkout as the final V4.1 snapshot authority.
  Source reconciliation and the Siegfried market-data work remain a separate gated session.

The recorded `origin/main` product export still has Siegfried FY2021–FY2025 market fields
blank, so the Phase 1 source gate is not yet satisfied. No market values will be invented in
this repository to bypass that gate.

## Test baseline

Command: `uv run pytest`

- 619 tests collected.
- 579 passed.
- 38 skipped because optional live API or PostgreSQL test configuration was absent.
- 2 failed, both pre-existing duplicate-file failures:
  `test_final_revision_is_unique_and_old_ephemeral_stamp_fails_closed` is collected once
  from the canonical test and once from its untracked `* 2.py` duplicate.
- Runtime: 10.16 seconds.

## Alembic baseline

Command: `uv run alembic heads`

Alembic reports revision `20260924_0002` twice because both
`20260924_0002_block8_final.py` and the pre-existing untracked
`20260924_0002_block8_final 2.py` are present. The duplicate is not removed without explicit
approval.

## First implementation boundary

The first safe increment is the immutable Equity domain and deterministic formula engine.
It can be tested with synthetic unit-test records while the source-data and reproducible
snapshot gates remain closed. Runtime fixtures and the Equity UI must not be populated until
the source revision and provenance corrections are approved.
