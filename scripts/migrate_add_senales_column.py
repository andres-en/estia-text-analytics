"""Migración puntual: agrega `conversation_analysis.senales` (JSON) a una base
ya existente — guarda los indicadores detectados de forma genérica, tanto para
campañas con el motor fijo (Acme) como para campañas con un
`EsquemaClasificacion` propio (ver `analysis/schema.py`).

No rellena filas ya analizadas (quedan con `senales = NULL`): la próxima vez
que se reanalicen (`--force`) o que reciban mensajes nuevos (ver
`db/repository.py::_get_or_create_conversation`, que invalida el análisis al
llegar mensajes nuevos), quedan pobladas. Idempotente.

Uso:
    python scripts/migrate_add_senales_column.py --db-url mysql+mysqlconnector://usuario:clave@host:3306/bd
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
    inspector = inspect(engine)
    columnas = {c["name"] for c in inspector.get_columns("conversation_analysis")}

    if "senales" in columnas:
        print("La columna 'senales' ya existe — nada que hacer.")
        return 0

    tipo = "JSON" if engine.dialect.name == "mysql" else "TEXT"
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE conversation_analysis ADD COLUMN senales {tipo} NULL"))
    print("Columna 'senales' agregada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
