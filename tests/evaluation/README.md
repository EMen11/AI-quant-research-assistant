# Validation evaluation tests

`workflow_eval.v1.jsonl` contains 24 versioned evaluation cases: 8 development,
8 validation, and 8 holdout cases. Each split has two clean controls and six adversarial
cases. A canonical input fingerprint test removes only administrative identities and expected
results, preserves the scenario semantics, and rejects any input repeated across splits.
Holdout cases are frozen evaluation inputs and must not be used to tune rules or thresholds.

The evaluation adapter invokes the production `validate_draft` path for every case. Structured
comparisons specific to the versioned dataset then check claim keys, values, units, periods,
Scope 2 methods, cutoff dates, concrete contradiction-source identifiers, and required
coverage. The matrix is calculated from the resulting production-path assessment statuses.

The three statuses are deliberately distinct:

- `eligible_for_review`: at least one server-owned trusted input exists and no blocking issue
  was found; this is not approval;
- `review_required`: trusted inputs exist, but a deterministic blocking issue requires analyst
  attention;
- `abstain`: the trusted inputs needed to evaluate the draft are absent, so the system fails
  closed rather than treating an empty report as positive validation.

Prompt-injection checks cover only the direct, paraphrased, Unicode-normalized, punctuation,
and invisible-character attack families represented by the tests and dataset. Hard negatives
containing terms such as `system prompt`, `instructions`, or `approval` without an attack
instruction are included, but the bounded deterministic detector can still block benign
wording that closely resembles an instruction.

Regenerate the deterministic report and its timing sidecar without network or Anthropic access:

```bash
uv run --frozen python -m ai_quant.evaluation.cli
```

Use `--timing-output PATH` to choose the sidecar location. The default is
`reports/evaluation/workflow_eval.v1.timing.json`, next to the deterministic report.

The canonical report contains workload counts, not latency. Real durations appear exclusively
in the separately versioned, closed-schema sidecar. It records three warmups and 20 sequential
observations of the **deterministic validation evaluation pipeline**: dataset loading,
production-path validation, assessment creation, and report aggregation. It does not time
retrieval, generation, rendering, a live model call, or a full application workflow.

Sidecar durations depend on hardware, caches, scheduling, and system load. They are not
byte-for-byte reproducible and are not a portable benchmark; ordinary variation between
regenerations is expected.

## Remaining limits

Scores and zero-false-eligible statements apply only to the exact dataset SHA-256 and covered
attack families recorded in the canonical report. Thirteen error categories have only one
positive case each. The holdout was constructed during the review correction and is frozen
from this version onward; it is neither an external dataset nor historically unseen.

Checks supplied through `StructuredValidationContext` are exercised by the versioned
evaluation, but they are not all populated by `InMemoryTrustWorkflow`. All assessment statuses
remain Python-computed, and `eligible_for_review` never represents human approval.
