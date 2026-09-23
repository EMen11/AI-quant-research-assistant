import os
import socket
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ai_quant.config import Settings
from ai_quant.streamlit_app import build_demo_view

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_installed_package_imports_outside_repository(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "-c", "import ai_quant; print(ai_quant.__version__)"],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.1.0"


def test_demo_view_builds_without_secret_or_network(monkeypatch) -> None:
    def forbid_network(*args, **kwargs):
        raise AssertionError("Demo startup attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbid_network)

    view = build_demo_view(Settings.from_env({}))

    assert view.analysis.snapshot.provider == "frozen-demo-fixture"
    assert tuple(result.assessment.status for result in view.scenarios.values()) == (
        "eligible_for_review",
        "review_required",
    )


def test_streamlit_entrypoint_starts_in_demo_without_secret(monkeypatch) -> None:
    monkeypatch.delenv("APP_MODE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=10).run()

    assert not app.exception
    assert app.title[0].value == "AI Quant Research Workbench"
    assert [tab.label for tab in app.tabs] == [
        "Overview",
        "Quant",
        "Climate Evidence",
        "Validation & Review",
        "Quality",
        "Methodology",
    ]
    assert any("APP_MODE=demo" in info.value for info in app.info)
    assert any("not a forecast" in warning.value for warning in app.warning)
