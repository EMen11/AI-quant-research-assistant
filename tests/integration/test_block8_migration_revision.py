from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

FINAL_REVISION = "20260924_0002"
EPHEMERAL_REVISION = "20260924_0001"


def _database_url() -> str:
    url = os.environ.get("BLOCK8_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("BLOCK8_TEST_DATABASE_URL is required for migration integration tests")
    if not any(marker in url for marker in ("block8_finalfix", "block8-finalfix")):
        pytest.fail("migration revision tests require the dedicated finalfix database")
    return url


def test_final_revision_is_unique_and_old_ephemeral_stamp_fails_closed() -> None:
    versions = sorted(Path("migrations/versions").glob("*.py"))
    assert [path.name for path in versions] == ["20260924_0002_block8_final.py"]
    migration_text = versions[0].read_text(encoding="utf-8")
    assert f'revision = "{FINAL_REVISION}"' in migration_text
    assert f'revision = "{EPHEMERAL_REVISION}"' not in migration_text

    url = _database_url()
    engine = create_engine(url)
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == FINAL_REVISION
        connection.execute(
            text("UPDATE alembic_version SET version_num = :revision"),
            {"revision": EPHEMERAL_REVISION},
        )

    environment = {**os.environ, "DATABASE_URL": url}
    try:
        failed = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert failed.returncode != 0
        assert EPHEMERAL_REVISION in f"{failed.stdout}\n{failed.stderr}"
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == EPHEMERAL_REVISION
            )
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num = :revision"),
                {"revision": FINAL_REVISION},
            )
        engine.dispose()

    checked = subprocess.run(
        ["alembic", "check"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert checked.returncode == 0, checked.stderr
    assert "No new upgrade operations detected" in checked.stdout
