"""Migración puntual: convierte `usuarios.id_cliente` (un cliente por usuario)
en la tabla puente `usuario_clientes` (varios clientes por usuario).

Idempotente — se puede correr más de una vez sin error.

Uso:
    python scripts/migrate_usuario_clientes.py --control-db-url mysql+mysqlconnector://usuario:clave@host:3306/clasificador_control
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
    parser.add_argument("--control-db-url", required=True)
    args = parser.parse_args()

    engine = create_db_engine(args.control_db_url)
    inspector = inspect(engine)

    if "usuario_clientes" not in inspector.get_table_names():
        print("Creando tabla usuario_clientes...")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE usuario_clientes (
                        id_usuario BIGINT NOT NULL,
                        id_cliente BIGINT NOT NULL,
                        PRIMARY KEY (id_usuario, id_cliente),
                        CONSTRAINT fk_usuario_clientes_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario),
                        CONSTRAINT fk_usuario_clientes_cliente FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente),
                        INDEX idx_usuario_clientes_cliente (id_cliente)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            )
    else:
        print("Tabla usuario_clientes ya existe, se omite.")

    columnas_usuarios = {c["name"] for c in inspector.get_columns("usuarios")}
    if "id_cliente" in columnas_usuarios:
        with engine.begin() as conn:
            migrados = conn.execute(
                text(
                    """
                    INSERT IGNORE INTO usuario_clientes (id_usuario, id_cliente)
                    SELECT id_usuario, id_cliente FROM usuarios WHERE id_cliente IS NOT NULL
                    """
                )
            ).rowcount
            print(f"{migrados} usuario(s) migrado(s) a usuario_clientes.")

        print("Eliminando la columna usuarios.id_cliente...")
        with engine.begin() as conn:
            fks = inspector.get_foreign_keys("usuarios")
            fk_cliente = next((fk["name"] for fk in fks if fk["constrained_columns"] == ["id_cliente"]), None)
            if fk_cliente:
                conn.execute(text(f"ALTER TABLE usuarios DROP FOREIGN KEY {fk_cliente}"))
            conn.execute(text("ALTER TABLE usuarios DROP COLUMN id_cliente"))
    else:
        print("usuarios.id_cliente ya no existe, se omite.")

    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
