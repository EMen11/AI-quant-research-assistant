from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "scan_tracked_secrets.py"
SPEC = importlib.util.spec_from_file_location("scan_tracked_secrets", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
scan_bytes = MODULE.scan_bytes


def test_secret_scanner_reports_only_redacted_metadata() -> None:
    secret = "sk-ant-" + "A" * 32

    findings = scan_bytes("fixture.txt", f"provider_key={secret}\n".encode())

    assert findings
    assert secret not in repr(findings)
    assert secret not in findings[0].masked()
    assert findings[0].masked() == "fixture.txt:1:anthropic-token:[REDACTED]"


def test_secret_scanner_allows_explicit_placeholders() -> None:
    findings = scan_bytes(".env.example", b"API_KEY=placeholder-demo-key\n")

    assert findings == []
