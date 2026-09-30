"""Migración puntual: `conversation_analysis.categoria_final` deja de ser un
ENUM fijo de MySQL (con las 5 categorías hardcodeadas del bot de venta de
cupos Acme) y pasa a ser VARCHAR(50) — necesario para que cada campaña
pueda definir sus propias categorías (ver `analysis/schema.py`).

No hay pérdida de datos: todo valor que ya estaba en el ENUM es una cadena
válida en el VARCHAR. Idempotente — correrla dos veces no hace nada la
segunda vez.

Uso:
    python scripts/migrate_categoria_final_varchar.py --db-url mysql+mysqlconnector://usuario:clave@host:3306/bd
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", dest="db_url", required=True, help="URL de la base del cliente")
    args = parser.parse_args()

    engine = create_db_engine(args.db_url)

    if engine.dialect.name != "mysql":
        print("No es MySQL: SQLite ya guarda esta columna como texto, nada que migrar.")
        return 0

    inspector = inspect(engine)
    columna = next(c for c in inspector.get_columns("conversation_analysis") if c["name"] == "categoria_final")

    tipo_actual = str(columna["type"]).upper()
    if tipo_actual.startswith("VARCHAR"):
        print("La columna ya es VARCHAR — nada que hacer.")
        return 0

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE conversation_analysis MODIFY COLUMN categoria_final VARCHAR(50) NOT NULL"))
    print("categoria_final migrada de ENUM a VARCHAR(50).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
