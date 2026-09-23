"""Command line entry point for offline preparation and authorized live capture."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path

from ai_quant.config import ConfigurationError, Settings
from ai_quant.llm.anthropic import AnthropicLLMClient
from ai_quant.llm.live_capture import (
    LiveCaptureError,
    SanitizedCandidateError,
    capture_live_once,
    prepare_live_capture,
    sanitize_rejected_live_capture,
    write_live_capture_plan,
)


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    client: AnthropicLLMClient | None = None,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "sanitize-rejected":
        try:
            candidate = sanitize_rejected_live_capture(
                args.input,
                args.run_input,
                args.output,
            )
        except SanitizedCandidateError as exc:
            print(
                f"Rejected capture normalization failed: error_code={exc.error_code}",
                file=sys.stderr,
            )
            return 2
        print(
            f"candidate_status={candidate.status} run_id={candidate.run_id} "
            f"normalization_version={candidate.normalization_version} "
            f"output={args.output.as_posix()}"
        )
        return 0
    try:
        if args.dry_run:
            source = os.environ if environ is None else environ
            model = source.get("ANTHROPIC_MODEL", "").strip()
            plan = prepare_live_capture(
                args.input,
                args.output,
                model=model,
                overwrite=args.overwrite,
            )
            write_live_capture_plan(plan, args.output, overwrite=args.overwrite)
            print(plan.model_dump_json(indent=2))
            return 0
        settings = Settings.from_env(environ)
        capture = capture_live_once(
            args.input,
            args.output,
            settings=settings,
            confirm_paid_call=args.confirm_paid_call,
            overwrite=args.overwrite,
            rejected_output_path=args.rejected_output,
            client=client,
        )
        print(
            f"capture_status={capture.status} run_id={capture.run_id} "
            f"output={args.output.as_posix()}"
        )
        return 0
    except LiveCaptureError as exc:
        print(_capture_error_line(exc), file=sys.stderr)
        return 2
    except ConfigurationError:
        print(
            "Anthropic capture failed: error_code=configuration_error "
            "http_status=none request_id=unavailable",
            file=sys.stderr,
        )
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture")
    capture.add_argument("--input", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--dry-run", action="store_true")
    capture.add_argument("--confirm-paid-call", action="store_true")
    capture.add_argument("--overwrite", action="store_true")
    capture.add_argument("--rejected-output", type=Path)
    sanitize = subparsers.add_parser("sanitize-rejected")
    sanitize.add_argument("--input", type=Path, required=True)
    sanitize.add_argument("--run-input", type=Path, required=True)
    sanitize.add_argument("--output", type=Path, required=True)
    return parser


def _capture_error_line(error: LiveCaptureError) -> str:
    http_status = "none" if error.http_status is None else str(error.http_status)
    request_id = _safe_public_identifier(error.request_id)
    reason_code = "" if error.reason_code is None else f" reason_code={error.reason_code}"
    fields = [
        f"Anthropic capture failed: error_code={error.error_code}{reason_code} "
        f"http_status={http_status} request_id={request_id}"
    ]
    if error.failure is not None:
        fields.extend(
            (
                "rule_codes=" + _safe_list(error.failure.content_rule_codes),
                "field_paths=" + _safe_list(error.failure.validation_field_paths),
            )
        )
    if error.model_call is not None:
        metadata = error.model_call
        fields.extend(
            (
                f"response_id={_safe_public_identifier(metadata.response_id)}",
                f"stop_reason={metadata.stop_reason or 'unavailable'}",
                f"provider={_safe_public_identifier(metadata.provider)}",
                f"model={_safe_public_identifier(metadata.model_id)}",
                f"prompt_version={_safe_public_identifier(metadata.prompt_version)}",
                f"status={metadata.status}",
                f"latency_ms={metadata.latency_ms}",
                f"input_tokens={_safe_number(metadata.input_tokens)}",
                f"output_tokens={_safe_number(metadata.output_tokens)}",
                f"total_tokens={_safe_number(metadata.total_tokens)}",
                f"retry_count={_safe_number(metadata.retry_count)}",
                f"cost_estimate={_safe_number(metadata.cost_estimate)}",
                f"currency={_safe_public_identifier(metadata.currency)}",
                "pricing_snapshot_id="
                + _safe_public_identifier(metadata.pricing_snapshot_id),
            )
        )
    fields.append(f"rejected_output_status={error.rejected_output_status}")
    if error.rejected_output_error_code is not None:
        fields.append(
            f"rejected_output_error={error.rejected_output_error_code}"
        )
    return " ".join(fields)


_SAFE_PUBLIC_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_SAFE_DIAGNOSTIC = re.compile(r"^[A-Za-z0-9_.$\[\]-]{1,200}$")


def _safe_public_identifier(value: object) -> str:
    if isinstance(value, str) and _SAFE_PUBLIC_IDENTIFIER.fullmatch(value):
        return value
    return "unavailable"


def _safe_list(values: tuple[str, ...]) -> str:
    safe = tuple(value for value in values if _SAFE_DIAGNOSTIC.fullmatch(value))
    return ",".join(sorted(set(safe))) if safe else "none"


def _safe_number(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    return "unavailable"


if __name__ == "__main__":
    raise SystemExit(main())
