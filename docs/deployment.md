# Secure public demo deployment

## Release boundary

The public release runs `app.py` with Python 3.12 and `APP_MODE=demo`. It is a deterministic,
read-only Streamlit demonstration. At runtime it does not require PostgreSQL, Docker, Anthropic,
market-data downloads, or another network service. Do not add a live button and leave the
Streamlit Community Cloud **Secrets** section empty.

`APP_MODE=demo` deliberately ignores `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, and `API_BASE_URL`.
The demo path does not import the Anthropic adapter, FastAPI application, PostgreSQL repositories,
SQLAlchemy, or psycopg. CI verifies those boundaries even when placeholder live variables exist.
`APP_MODE=live` is a separate local Block 8 workflow and is not part of this public deployment.

## Installation is not offline execution

Package installation may need access to the Python package registry when the locked artifacts are
not already cached:

```bash
uv sync --frozen --all-groups
```

After installation, the release gate runs with uv's network access disabled:

```bash
APP_MODE=demo UV_OFFLINE=1 uv run --offline --frozen streamlit run app.py
```

The automated server test additionally rejects non-loopback Python socket connections while
allowing localhost for its health request. This is an application-process test, not an operating
system firewall: it does not govern a browser process, native code that bypasses Python sockets,
or subprocesses that deliberately remove the injected guard. Import-denial checks independently
fail if the demo loads live API, persistence, database, or Anthropic modules.

## Versioned fixtures and review meaning

The demo reuses reviewed, versioned fixtures; it does not regenerate or silently approve output.

| Fixture | Purpose and provenance | SHA-256 / date |
|---|---|---|
| `src/ai_quant/fixtures/demo_adjusted_prices.csv` | synthetic frozen adjusted-close input | `4a96fbc3af61e22d93bcb0fa3ccd95880c349e8242843c036118baa5932b235e` |
| `src/ai_quant/fixtures/llm/public_demo_live_v3_v1.json` | historical provider response, sanitized, deterministically normalized, then explicitly approved for public-demo promotion | file `66a232ce7b130ca2994a0de24edbea5b291ff0b19d5c357c037f12a86cbc83d8`; promotion review `2026-09-23`; source artifact `ac94b30563857a87259484879fb20009c8ce6c234c795769cbe16cabea708141` |
| `src/ai_quant/fixtures/trust_blocked_draft_v1.json` | deliberately invalid synthetic scenario | `9a13c1c85c2025de047b251016ce22ebc786b5ba9fc4351437670c9ccbce53f9` |

The promotion review means only that the historical fixture may be shown in the offline demo. It
is not an analytical approval. Every new Streamlit session starts without a `HumanReview`;
`eligible_for_review` means a human may review the result, never that it is approved. Reviews and
corrections made in the demo remain unauthenticated and session-only.

Document dates, source hashes, pages, excerpts, metric IDs, and evidence IDs remain visible in the
application. The fixture assertions fail closed if reviewed provenance or status changes.

## Candidate preflight

Run from a clean checkout of the candidate branch:

```bash
uv lock --check
uv sync --frozen --all-groups
uv run --frozen ruff check .
uv run --offline --frozen python scripts/scan_tracked_secrets.py
APP_MODE=demo UV_OFFLINE=1 uv run --offline --frozen pytest -q \
  tests/integration/test_block9_demo_release.py
APP_MODE=demo UV_OFFLINE=1 uv run --offline --frozen pytest -q
git diff --check
```

The secret scanner examines only Git-tracked text files and prints file, line, rule, and
`[REDACTED]` for a finding—never the matched value. It is a focused high-confidence scan, not a
substitute for repository-host secret protection, history scanning, or credential rotation.

## Publication procedure

Publication is manual and was not performed while preparing Block 9:

1. Review the complete candidate diff and commit it on the dedicated Block 9 branch.
2. Push that exact candidate commit and require the GitHub Actions workflow to pass.
3. In Streamlit Community Cloud, select the candidate branch, `app.py`, and Python 3.12.
4. Set `APP_MODE=demo` if the platform configuration requires an explicit value.
5. Leave Secrets empty; do not configure PostgreSQL, Anthropic, or another service.
6. Deploy or reboot the application and record the URL, exact commit, and UTC verification time.
7. Perform the anonymous desktop and physical/mobile checks below against the deployed URL.
8. If a gate fails, stop publication or roll back to the last verified commit; do not switch the
   public app to live mode as a workaround.

## Smoke-test checklist

### Configuration and local candidate

- [ ] Exact candidate commit and passing CI recorded.
- [ ] Python is 3.12 and the lockfile passes `uv lock --check`.
- [ ] `APP_MODE=demo`; Streamlit Secrets is empty.
- [ ] Masked tracked-file secret scan passes.
- [ ] Offline boundary and full test suites pass after dependencies are installed.
- [ ] Local server health endpoint returns `ok` with outbound Python sockets blocked.
- [ ] Browser renders a non-empty page with no error overlay or console error.

### Anonymous post-publication desktop

- [ ] URL loads in a private window without authentication.
- [ ] Six views are accessible: Overview, Quant, Climate Evidence, Validation & Review, Quality,
  and Methodology.
- [ ] Admissible scenario shows `eligible_for_review` and no pre-existing `HumanReview`.
- [ ] Blocked scenario shows `review_required`, failed-validation and untrusted/non-reliable
  labels, critical findings, and no approved export.
- [ ] Provenance dates, hashes, pages, excerpts, and limitations are visible.
- [ ] A fresh anonymous session starts without a persisted review.
- [ ] No exception, traceback, broken internal navigation, or broken external link is visible.

### Public mobile

- [ ] Test the deployed URL on a phone or a 390×844 viewport.
- [ ] All six views remain accessible with no global horizontal overflow.
- [ ] The blocked scenario can be selected and its findings remain readable.

The anonymous remote and mobile boxes must remain unchecked until a real deployment is tested.
Local browser verification cannot be reported as either of those public checks.

## Known limits

- Demo content is historical or synthetic and is not live market data, a forecast, or investment
  advice.
- The reviewed public fixture was derived from one historical provider response; no provider is
  called during the demo.
- Reviews are session-only, unauthenticated, and non-persistent. PostgreSQL persistence exists only
  in the separate local Block 8 stack.
- Retrieval and validation metrics apply only to the small versioned evaluation sets and covered
  attack families; they are not universal safety claims.
- The Python socket guard is a reproducible test boundary with the limitations stated above, not a
  production egress-control policy.
