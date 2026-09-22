# Trust boundaries — Block 3

## Scope

Block 3 is a fully offline, in-memory vertical slice over the deterministic Block 2 Quant Core.
It does not add live model calls, retrieval, a database, PDF generation, background workers or an
approval automation. Both demo responses are versioned JSON fixtures. Market prices, evidence and
generation fixtures are synthetic and must not be interpreted as investment research.

## Authority model

The boundaries are deliberately asymmetric:

- Python loads the immutable snapshot, computes every financial value and creates `MetricRecord`
  objects. The generator never calculates or supplies a metric value.
- Python creates `EvidenceRecord`, draft, claim and run identifiers. The generator may only select
  identifiers supplied in its structured-generation context; it cannot mint trusted identifiers.
- The generator proposes a `DraftProposal`: summary, claim templates, declared references,
  uncertainty and limitations. It cannot emit validation results, assessments, approvals or a
  `HumanReview`.
- Python parses the proposal against a closed Pydantic schema (`extra="forbid"`), validates every
  reference against records owned by the active run, and injects formatted metric values.
- `AutomatedAssessment` is routing metadata with exactly three statuses:
  `eligible_for_review`, `review_required` and `abstain`. It is never an approval.
- `HumanReview` is a separate record created only from an explicit human action. Its dispositions
  are `approved`, `corrected`, `rejected` and `escalated`.

Generated text is therefore untrusted input. The LLM boundary may propose structure and language;
it cannot create evidence, certify correctness or make the human decision.
A JSON document that satisfies the schema proves only its shape and vocabulary, not the truth of
its claims. Truth-adjacent guarantees come from current-run record lookup, deterministic numeric
substitution and human review; even those controls do not turn historical demo data into a forecast.

## Workflow and states

The in-memory workflow is explicit and finite:

1. `validate_request`
2. `load_snapshot`
3. `compute_quant_metrics`
4. `retrieve_evidence_fake`
5. `generate_draft_fake`
6. `validate_draft`
7. `assess`
8. `request_human_review`

Its only allowed state path is `created → generated → validated → pending_review → finalized`.
Block 3 stops at `pending_review`; no demo fixture creates a human decision. Skipped, reversed and
post-finalization transitions raise `WorkflowTransitionError`.

An `eligible_for_review` assessment means structure and references passed automated checks, while a
human decision is still required. `review_required` means an ambiguity or violation needs explicit
attention. `abstain` means trusted data or evidence is insufficient to answer. None means approved.

## Structured generation and budgets

`GenerationController` permits a configured maximum number of calls and measures elapsed time with
an injected monotonic clock. The demo maximum is one call with a two-second budget. There are no
retries, agent loops or real waits. Budget exhaustion, timeout and schema violations are explicit
errors. Audit metadata records provider, model ID, parameters, prompt version, response ID and a
timezone-aware UTC timestamp without depending on a specific commercial provider.
The Block 3 synchronous timeout is measured at the boundary after the deterministic fake returns;
a future network adapter must additionally configure its own transport-level cancellation timeout.

## Numeric policy

A quantitative claim uses placeholders such as `{{metric:metric-run-demo-valid-cumulative-return}}`.
Its declared metric IDs must exactly match its placeholders and must resolve to `MetricRecord`
objects owned by the active run. Only Python formats and substitutes their values and creates
`ClaimMetricReference` records.

Any free numeric literal in a quantitative template—including a percentage, integer or decimal—is
treated as an invented value. It creates a blocking `free_numeric_literal` issue, routes the draft
to `review_required`, and prevents all reliable rendered claims and final text. This intentionally
strict policy prefers false positives over silently publishing an untraceable financial number.
Unknown IDs, cross-run references and placeholder/reference mismatches are blocking for the same
reason.

## Offline scenarios

- **Valid:** two Python-created metric records and one synthetic evidence record are referenced by
  a structured fixture. Validation has no blocking issue; Python injects the final values; the
  assessment is `eligible_for_review`; the state remains `pending_review`; no approval exists.
- **Blocked:** the fixture contains cross-run identifiers and an invented percentage. Validation
  reports the exact failures; assessment is `review_required`; `RenderedDraft.reliable` is false;
  no reliable final text or `HumanReview` is emitted.

All identifiers are deterministic and run-scoped in demo mode. Tests exercise valid and malformed
JSON, schema closure, reference isolation, numeric injection and blocking, state transitions,
budgets, timeout behavior, determinism, and execution without a network or secret.
