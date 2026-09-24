from __future__ import annotations

import http.client
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_demo_with_live_environment_cannot_import_or_call_live_boundaries() -> None:
    script = r"""
import importlib.abc
import socket
import sys

BLOCKED = (
    'anthropic',
    'ai_quant.api',
    'ai_quant.live_dashboard',
    'ai_quant.llm.anthropic',
    'ai_quant.persistence',
    'fastapi',
    'psycopg',
    'sqlalchemy',
)

class DenyLiveImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in BLOCKED):
            raise AssertionError(f'demo imported forbidden live boundary: {fullname}')
        return None

def guarded_connect(sock, address):
    if isinstance(address, tuple):
        host = str(address[0])
        if host not in {'127.0.0.1', '::1', 'localhost'}:
            raise AssertionError('demo attempted an outbound network connection')
    return ORIGINAL_CONNECT(sock, address)

ORIGINAL_CONNECT = socket.socket.connect
socket.socket.connect = guarded_connect
sys.meta_path.insert(0, DenyLiveImports())

from ai_quant.config import AppMode, Settings
from ai_quant.llm import FakeLLMClient, client_from_settings
from streamlit.testing.v1 import AppTest

settings = Settings.from_env()
assert settings.app_mode is AppMode.DEMO
assert settings.anthropic_api_key is None
assert settings.anthropic_model is None
assert settings.api_base_url == 'http://api:8000'
assert isinstance(client_from_settings(settings), FakeLLMClient)

app = AppTest.from_file('app.py', default_timeout=20).run()
assert not app.exception
assert [tab.label for tab in app.tabs] == [
    'Overview', 'Quant', 'Climate Evidence', 'Validation & Review', 'Quality', 'Methodology'
]
assert any('no HumanReview' in warning.value for warning in app.warning)
app.selectbox[0].select('blocked').run()
assert not app.exception
assert not app.get('download_button')
assert any('Export blocked' in warning.value for warning in app.warning)

for name in BLOCKED:
    assert not any(module == name or module.startswith(name + '.') for module in sys.modules)
"""
    environment = os.environ.copy()
    environment.update(
        {
            "APP_MODE": "demo",
            "ANTHROPIC_API_KEY": "placeholder-present-but-must-not-be-used",
            "ANTHROPIC_MODEL": "placeholder-model-id",
            "API_BASE_URL": "postgres://invalid-but-must-be-ignored",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=40,
    )

    assert result.returncode == 0, result.stderr


def test_streamlit_server_starts_with_outbound_sockets_blocked(tmp_path: Path) -> None:
    marker = tmp_path / "outbound-attempted"
    guard = tmp_path / "sitecustomize.py"
    guard.write_text(
        """
import ipaddress
import os
import socket

_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_marker = os.environ['BLOCK9_OUTBOUND_MARKER']

def _is_loopback(address):
    if not isinstance(address, tuple):
        return True
    host = str(address[0])
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False

def _reject(address):
    if not _is_loopback(address):
        open(_marker, 'a', encoding='utf-8').write('[REDACTED outbound attempt]\\n')
        raise OSError('outbound network disabled by Block 9 test')

def _connect(sock, address):
    _reject(address)
    return _original_connect(sock, address)

def _connect_ex(sock, address):
    _reject(address)
    return _original_connect_ex(sock, address)

socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex
""".lstrip(),
        encoding="utf-8",
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment.update(
        {
            "APP_MODE": "demo",
            "ANTHROPIC_API_KEY": "placeholder-present-but-must-not-be-used",
            "ANTHROPIC_MODEL": "placeholder-model-id",
            "API_BASE_URL": "postgres://invalid-but-must-be-ignored",
            "BLOCK9_OUTBOUND_MARKER": str(marker),
            "PYTHONPATH": (
                f"{tmp_path}{os.pathsep}{existing_pythonpath}"
                if existing_pythonpath
                else str(tmp_path)
            ),
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless=true",
            "--server.address=127.0.0.1",
            f"--server.port={port}",
            "--browser.gatherUsageStats=false",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    response_body = b""
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
                connection.request("GET", "/_stcore/health")
                response = connection.getresponse()
                response_body = response.read()
                connection.close()
                if response.status == 200:
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise AssertionError("Streamlit did not become healthy within 30 seconds")

        assert process.poll() is None
        assert response_body == b"ok"
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        connection.request("GET", "/")
        response = connection.getresponse()
        html = response.read()
        connection.close()
        assert response.status == 200
        assert b"streamlit" in html.lower()
        assert not marker.exists()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    assert not marker.exists()
