from __future__ import annotations

from sqlalchemy import Engine

from ..db.engine import create_db_engine  # mismo pool_pre_ping / pragma sqlite
from .models import Base


def create_control_engine(db_url: str) -> Engine:
    return create_db_engine(db_url)


def create_control_tables(engine: Engine) -> None:
    Base.metadata.create_all(engine)
