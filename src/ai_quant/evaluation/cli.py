"""CLI for regenerating the deterministic workflow evaluation report."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_quant.evaluation.runner import write_evaluation_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("tests/evaluation/workflow_eval.v1.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/evaluation/workflow_eval.v1.json"))
    args = parser.parse_args()
    write_evaluation_report(args.dataset, args.output)


if __name__ == "__main__":
    main()
