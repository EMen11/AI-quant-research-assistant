"""CLI for deterministic validation evaluation and its local timing sidecar."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_quant.evaluation.runner import write_evaluation_artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("tests/evaluation/workflow_eval.v1.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/evaluation/workflow_eval.v1.json"))
    parser.add_argument(
        "--timing-output",
        type=Path,
        help="Timing sidecar path (default: <output stem>.timing.json).",
    )
    args = parser.parse_args()
    timing_output = args.timing_output or args.output.with_name(f"{args.output.stem}.timing.json")
    write_evaluation_artifacts(args.dataset, args.output, timing_output)


if __name__ == "__main__":
    main()
