from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def create_db_engine(db_url: str) -> Engine:
    # pool_pre_ping: revalida la conexión antes de usarla y reconecta si el servidor
    # la cerró por inactividad (ej. wait_timeout de MySQL) — sin esto, un proceso de
    # larga duración (como el servidor web) empieza a fallar con
    # "MySQL Connection not available" tras un rato sin tráfico.
    engine = create_engine(db_url, future=True, pool_pre_ping=True)
    if db_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_fk(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_all_tables(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def apply_ddl_file(engine: Engine, ddl_path: Path) -> None:
    """Ejecuta un archivo .sql de DDL (sentencias separadas por `;`) contra un
    engine. Usado tanto por `scripts/apply_ddl.py` como al aprovisionar la
    base de datos de un cliente nuevo (`webapp/admin.py`).

    Quita los comentarios `-- ...` antes de partir por `;`: si no, un `;` que
    aparezca dentro de un comentario (ej. una nota de negocio) corta una
    sentencia CREATE TABLE a la mitad.
    """
    ddl = ddl_path.read_text(encoding="utf-8")
    sin_comentarios = re.sub(r"--[^\n]*", "", ddl)
    statements = [s.strip() for s in sin_comentarios.split(";") if s.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
