# Evaluation tests

`workflow_eval.v1.jsonl` contains 24 deterministic cases: 8 development, 8 validation,
and 8 holdout cases. Each split has two clean controls and six adversarial cases. The
holdout labels are evaluated by the same frozen validators but must not be used to tune
their rules.

Regenerate the report without network or Anthropic access:

```bash
uv run --frozen python -m ai_quant.evaluation.cli
```

The report deliberately excludes wall-clock timestamps and timing measurements so that it
is byte-reproducible. Its `latency` field reports deterministic validator work units rather
than claiming machine-independent wall-clock performance. Any statement about zero false
`eligible_for_review` outcomes is scoped only to the exact dataset SHA-256 in the report.
