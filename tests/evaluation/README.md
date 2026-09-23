# Evaluation tests

`workflow_eval.v1.jsonl` contains 24 deterministic cases: 8 development, 8 validation,
and 8 holdout cases. Each split has two clean controls and six adversarial cases. The
holdout labels are evaluated by the same frozen validators but must not be used to tune
their rules.

Regenerate the report and its timing sidecar without network or Anthropic access:

```bash
uv run --frozen python -m ai_quant.evaluation.cli
```

Use `--timing-output PATH` to choose the sidecar location. The default is
`reports/evaluation/workflow_eval.v1.timing.json`, next to the deterministic report.

The canonical report deliberately excludes wall-clock timestamps and timing measurements so
that it remains byte-reproducible. Its `latency` field reports deterministic validator work
units. The separately versioned, closed-schema sidecar records three warmups and 20 sequential
full-pipeline observations from `time.perf_counter_ns`, including dataset loading, validation,
assessment creation, and report aggregation.

Sidecar durations depend on hardware, caches, scheduling, and system load. They are not
byte-for-byte reproducible and are not a portable benchmark; ordinary variation between
regenerations is expected. Any statement about zero false `eligible_for_review` outcomes is
scoped only to the exact dataset SHA-256 in the canonical report.
