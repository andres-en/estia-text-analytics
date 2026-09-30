"""Migración puntual: agrega `conversations.campana_id` (con backfill desde el
import que creó cada conversación) y `campanas.configuracion` a una base de
cliente que ya existía antes de que esto fuera soportado.

Idempotente — se puede correr más de una vez sin error.

Uso:
    python scripts/migrate_campana_config.py --db-url mysql+mysqlconnector://usuario:clave@host:3306/cliente_x
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import inspect, text  # noqa: E402

from clasificador.db.engine import create_db_engine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", dest="db_url", required=True, help="URL de la base del cliente")
    args = parser.parse_args()

    engine = create_db_engine(args.db_url)
    inspector = inspect(engine)

    columnas_conversations = {c["name"] for c in inspector.get_columns("conversations")}
    if "campana_id" not in columnas_conversations:
        print("Agregando conversations.campana_id...")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN campana_id BIGINT NULL"))
            conn.execute(
                text(
                    "ALTER TABLE conversations ADD CONSTRAINT fk_conv_campana "
                    "FOREIGN KEY (campana_id) REFERENCES campanas(id_campana)"
                )
            )
            conn.execute(text("CREATE INDEX idx_conversations_campana_id ON conversations (campana_id)"))
    else:
        print("conversations.campana_id ya existe, se omite.")

    with engine.begin() as conn:
        actualizados = conn.execute(
            text(
                """
                UPDATE conversations c
                JOIN imports i ON c.first_import_id = i.id
                SET c.campana_id = i.campana_id
                WHERE c.campana_id IS NULL AND i.campana_id IS NOT NULL
                """
            )
        ).rowcount
        print(f"{actualizados} conversación(es) con campana_id asignado desde su import.")

    columnas_campanas = {c["name"] for c in inspector.get_columns("campanas")}
    if "configuracion" not in columnas_campanas:
        print("Agregando campanas.configuracion...")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE campanas ADD COLUMN configuracion JSON NULL"))
    else:
        print("campanas.configuracion ya existe, se omite.")

    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
