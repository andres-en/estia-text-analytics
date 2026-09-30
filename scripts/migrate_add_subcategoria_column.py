"""Migración puntual: agrega `conversation_analysis.subcategoria` (segundo nivel
opcional de clasificación, ej. el motivo del interés) a una base ya existente.
Idempotente.

Uso:
    python scripts/migrate_add_subcategoria_column.py --db-url mysql+mysqlconnector://usuario:clave@host:3306/bd
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
    columnas = {c["name"] for c in inspect(engine).get_columns("conversation_analysis")}
    if "subcategoria" in columnas:
        print("La columna 'subcategoria' ya existe — nada que hacer.")
        return 0

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE conversation_analysis ADD COLUMN subcategoria VARCHAR(50) NULL"))
        conn.execute(text("CREATE INDEX idx_analysis_subcategoria ON conversation_analysis (subcategoria)"))
    print("Columna 'subcategoria' agregada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
