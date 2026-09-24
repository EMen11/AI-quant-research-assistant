from __future__ import annotations

import subprocess
import sys


def test_demo_build_imports_no_live_api_or_persistence_and_uses_no_network() -> None:
    script = """
import socket
import sys
from ai_quant.config import Settings
from ai_quant.streamlit_app import build_demo_view
def reject(*args, **kwargs):
    raise AssertionError('demo attempted network access')
socket.socket = reject
socket.create_connection = reject
dashboard = build_demo_view(Settings.from_env({'APP_MODE': 'demo'}))
assert dashboard.scenarios['admissible'].assessment.status == 'eligible_for_review'
assert 'ai_quant.live_dashboard' not in sys.modules
assert 'ai_quant.persistence' not in sys.modules
assert 'sqlalchemy' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=20
    )

    assert result.returncode == 0, result.stderr
