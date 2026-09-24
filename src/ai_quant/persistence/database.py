"""SQLAlchemy engine and transaction construction with no import-time connection."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create a pooled engine; callers own its lifecycle."""

    return create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        connect_args={"options": "-c timezone=UTC"},
    )


def create_session_factory(database_url: str, *, echo: bool = False) -> sessionmaker[Session]:
    """Return sessions whose transaction boundary is owned by the application service."""

    engine = create_database_engine(database_url, echo=echo)
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
