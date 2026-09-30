"""Migración puntual: crea la tabla `ai_usage` en una base ya existente — un
renglón por cada llamada a OpenAI (clasificación de conversaciones o
generación de esquemas de campaña con IA), con sus tokens de entrada/salida.
Ver `db/models.py::AIUsage` y `analysis/pricing.py` para el costo estimado.

Usa `Base.metadata.create_all(engine)`, que ya es idempotente por su cuenta
(`checkfirst=True`): solo crea las tablas que todavía no existen, así que
correr este script no toca nada de lo que ya está.

Uso:
    python scripts/migrate_add_ai_usage_table.py --db-url mysql+mysqlconnector://usuario:clave@host:3306/bd
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import inspect  # noqa: E402

from clasificador.db.engine import create_all_tables, create_db_engine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", dest="db_url", required=True, help="URL de la base del cliente")
    args = parser.parse_args()

    engine = create_db_engine(args.db_url)
    ya_existia = "ai_usage" in inspect(engine).get_table_names()

    create_all_tables(engine)

    print("La tabla 'ai_usage' ya existía — nada que hacer." if ya_existia else "Tabla 'ai_usage' creada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
