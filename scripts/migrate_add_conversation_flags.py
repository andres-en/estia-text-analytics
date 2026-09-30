"""Migración puntual: agrega `conversations.iniciada_por` y `.contiene_array`
a una base de datos ya existente (creada antes de que estos campos se
agregaran al esquema), y rellena su valor para las conversaciones que ya
estaban guardadas.

`apply_ddl.py` no sirve para esto porque usa `CREATE TABLE IF NOT EXISTS`: no
altera una tabla que ya existe. Este script es idempotente — puede correrse
más de una vez sin error (si las columnas ya existen, solo repite el relleno,
que tampoco duplica nada).

Uso:
    python scripts/migrate_add_conversation_flags.py --db-url mysql+mysqlconnector://usuario:clave@host:3306/bd
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import inspect, text  # noqa: E402

from clasificador.db.engine import create_db_engine  # noqa: E402


def _add_columns_if_missing(engine) -> None:
    inspector = inspect(engine)
    columnas = {c["name"] for c in inspector.get_columns("conversations")}
    es_mysql = engine.dialect.name == "mysql"

    with engine.begin() as conn:
        if "iniciada_por" not in columnas:
            tipo = "ENUM('CUSTOMER', 'BOT', 'SYSTEM')" if es_mysql else "VARCHAR(20)"
            # DEFAULT 'BOT' es solo para que el ALTER no falle en las filas ya
            # existentes (NOT NULL sin default); el relleno de abajo lo corrige
            # fila por fila con el valor real.
            conn.execute(text(f"ALTER TABLE conversations ADD COLUMN iniciada_por {tipo} NOT NULL DEFAULT 'BOT'"))
            print("Columna 'iniciada_por' agregada.")
        if "contiene_array" not in columnas:
            tipo = "BOOLEAN" if es_mysql else "BOOLEAN"
            conn.execute(text(f"ALTER TABLE conversations ADD COLUMN contiene_array {tipo} NOT NULL DEFAULT 0"))
            print("Columna 'contiene_array' agregada.")


def _backfill(engine) -> None:
    with engine.begin() as conn:
        r1 = conn.execute(
            text(
                """
                UPDATE conversations
                SET iniciada_por = (
                    SELECT sender FROM messages
                    WHERE messages.conversation_id = conversations.id AND messages.sequence_number = 1
                )
                WHERE EXISTS (
                    SELECT 1 FROM messages
                    WHERE messages.conversation_id = conversations.id AND messages.sequence_number = 1
                )
                """
            )
        )
        print(f"iniciada_por: {r1.rowcount} conversaciones actualizadas a partir de su primer mensaje.")

        r2 = conn.execute(
            text(
                """
                UPDATE conversations
                SET contiene_array = 1
                WHERE contiene_array = 0
                  AND id IN (SELECT DISTINCT conversation_id FROM messages WHERE message LIKE '%Array%')
                """
            )
        )
        print(f"contiene_array: {r2.rowcount} conversaciones marcadas por contener 'Array' en algún mensaje.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", dest="db_url", required=True, help="URL de la base del cliente")
    args = parser.parse_args()

    engine = create_db_engine(args.db_url)
    _add_columns_if_missing(engine)
    _backfill(engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
