"""Database setup and session management."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import models  # noqa: F401 - ensure all models registered
from .models import Base

_db_dir = os.path.join(os.path.dirname(__file__), "..", "..")
DATABASE_URL = f"sqlite:///{os.path.join(_db_dir, 'escrow.db')}"


def init_db(url: str = DATABASE_URL) -> None:
    """Create tables."""
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)


def get_engine(url: str = DATABASE_URL):
    """Get SQLAlchemy engine."""
    return create_engine(url, connect_args={"check_same_thread": False})


def get_session_factory(url: str = DATABASE_URL):
    """Get session factory."""
    engine = get_engine(url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
