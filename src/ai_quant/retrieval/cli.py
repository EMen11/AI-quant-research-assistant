"""Command-line entry point for deterministic retrieval evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_quant.retrieval.evaluation import evaluate_retrieval, write_evaluation_artifact

DEFAULT_GOLD = Path("tests/evaluation/retrieval_gold.v1.jsonl")
DEFAULT_OUTPUT = Path("reports/evaluation/retrieval_baselines.v1.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    evaluate.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    artifact = evaluate_retrieval(args.gold)
    write_evaluation_artifact(artifact, args.output)
    print(
        f"wrote {args.output} questions={len(artifact.question_results) // 2} "
        f"corpus_size={artifact.corpus_size}"
    )


if __name__ == "__main__":
    main()
