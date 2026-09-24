"""Scan tracked text files for likely secrets without ever printing matched values."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIPPED_SUFFIXES = {
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".woff",
    ".woff2",
}
PLACEHOLDER_MARKERS = (
    "example",
    "fake",
    "placeholder",
    "redacted",
    "sample",
    "test",
    "your-",
    "your_",
)


@dataclass(frozen=True, slots=True)
class Finding:
    """A redacted location and rule name; matched material is intentionally discarded."""

    path: str
    line: int
    rule: str

    def masked(self) -> str:
        return f"{self.path}:{self.line}:{self.rule}:[REDACTED]"


TOKEN_RULES = (
    ("private-key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github-token", re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("anthropic-token", re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("openai-token", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")),
)
ASSIGNMENT_RULE = re.compile(
    rb"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*[\"']?([^\s\"'#]{8,})"
)
PYTHON_ASSIGNMENT_RULE = re.compile(
    rb"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*[\"']([^\"']{8,})[\"']"
)


def _is_placeholder(value: bytes) -> bool:
    normalized = value.decode("utf-8", errors="ignore").lower()
    return normalized.startswith("key_") or any(
        marker in normalized for marker in PLACEHOLDER_MARKERS
    )


def scan_bytes(path: str, payload: bytes) -> list[Finding]:
    """Return redacted findings for one payload without retaining matched values."""

    findings: list[Finding] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        for rule, pattern in TOKEN_RULES:
            if pattern.search(line):
                findings.append(Finding(path=path, line=line_number, rule=rule))
        assignment_pattern = PYTHON_ASSIGNMENT_RULE if path.endswith(".py") else ASSIGNMENT_RULE
        assignment = assignment_pattern.search(line)
        if assignment is not None and not _is_placeholder(assignment.group(1)):
            findings.append(Finding(path=path, line=line_number, rule="credential-assignment"))
    return findings


def tracked_files() -> list[Path]:
    """Resolve only Git-tracked paths, excluding binary formats by suffix."""

    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        ROOT / raw.decode("utf-8")
        for raw in result.stdout.split(b"\0")
        if raw and Path(raw.decode("utf-8")).suffix.lower() not in SKIPPED_SUFFIXES
    ]


def main() -> int:
    files = tracked_files()
    findings: list[Finding] = []
    checked = 0
    for path in files:
        if not path.is_file():
            continue
        payload = path.read_bytes()
        if b"\0" in payload:
            continue
        checked += 1
        findings.extend(scan_bytes(str(path.relative_to(ROOT)), payload))

    if findings:
        print(f"Secret scan FAIL: {len(findings)} redacted finding(s).")
        for finding in findings:
            print(finding.masked())
        return 1

    print(f"Secret scan PASS: {checked} tracked text files checked; values were never printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
