"""Migración puntual: agrega el índice de `conversations.started_at` a una base
de datos ya existente (creada antes de que este índice se agregara al esquema).

`apply_ddl.py` no sirve para esto porque usa `CREATE TABLE IF NOT EXISTS`: no
altera una tabla que ya existe. Este script es idempotente — puede correrse
más de una vez sin error.

Uso:
    python scripts/migrate_add_started_at_index.py
    python scripts/migrate_add_started_at_index.py --db-url mysql+mysqlconnector://usuario:clave@host:3306/bd
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import inspect, text  # noqa: E402

from clasificador.db.engine import create_db_engine  # noqa: E402

INDEX_NAME = "idx_conversations_started_at"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-url", dest="db_url", required=True, help="URL de la base del cliente")
    args = parser.parse_args()

    engine = create_db_engine(args.db_url)

    inspector = inspect(engine)
    existentes = {ix["name"] for ix in inspector.get_indexes("conversations")}
    ya_cubierto = any(
        ix["column_names"] == ["started_at"] or "started_at" in ix["column_names"][:1]
        for ix in inspector.get_indexes("conversations")
    )

    if INDEX_NAME in existentes or ya_cubierto:
        print("El índice de started_at ya existe. No hay nada que hacer.")
        return 0

    with engine.begin() as conn:
        conn.execute(text(f"CREATE INDEX {INDEX_NAME} ON conversations (started_at)"))

    print(f"Índice '{INDEX_NAME}' creado en conversations(started_at).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
