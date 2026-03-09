from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from imdr.config.settings import Settings


class MSSQLConnector:
    """Manages SQLAlchemy engine and session factory for MS SQL Server."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: Engine = create_engine(
            settings.mssql_connection_url,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_timeout=settings.pool_timeout,
            pool_pre_ping=True,
            echo=False,
        )
        self._session_factory: sessionmaker[Session] = sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Transactional session scope. Commits on success, rolls back on error."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        """Dispose the engine and release all pooled connections."""
        self._engine.dispose()
