"""Aplica sql/ddl.sql (esquema de UN cliente) contra la base indicada.

Uso:
    python scripts/apply_ddl.py --db-url mysql+mysqlconnector://usuario:clave@host:3306/cliente_x
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from clasificador.db.engine import apply_ddl_file, create_all_tables, create_db_engine  # noqa: E402

DDL_PATH = Path(__file__).resolve().parent.parent / "sql" / "ddl.sql"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-url", dest="db_url", required=True, help="URL de la base del cliente")
    args = parser.parse_args()

    engine = create_db_engine(args.db_url)
    apply_ddl_file(engine, DDL_PATH)
    # Red de seguridad: crea cualquier tabla del modelo SQLAlchemy que falte en
    # ddl.sql (idempotente — checkfirst=True — no toca lo que ya existe).
    create_all_tables(engine)

    print(f"DDL aplicado correctamente contra {args.db_url.split('@')[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
