"""Migra el despliegue single-tenant actual al esquema multi-cliente.

Qué hace (idempotente — se puede correr más de una vez sin duplicar nada):
  1. Crea la base de control (tablas roles/clientes/usuarios) si no existe, y
     siembra los roles `super_admin`/`admin`.
  2. Crea (si no existe) el usuario super_admin con el correo indicado, para
     poder entrar la primera vez.
  3. Registra la base de datos actual (la que ya tiene los datos reales) como
     el primer cliente en la tabla `clientes` — NO copia datos, la base
     existente pasa a ser, tal cual, la base de ese cliente.
  4. Contra esa base existente: crea la tabla `campanas` (si no existe),
     agrega la columna `imports.campana_id` (si no existe) y crea una
     campaña "Campaña histórica" a la que se le asignan los imports que no
     tenían campaña todavía.

Uso:
    python scripts/migrate_multicliente.py \
        --control-db-url mysql+mysqlconnector://usuario:clave@host:3306/clasificador_control \
        --client-db-url  mysql+mysqlconnector://usuario:clave@host:3306/clasificador_cdr_whatsapp \
        --nombre-cliente "Cliente actual" \
        --super-admin-email tu_correo@dominio.com \
        --super-admin-nombre "Tu Nombre"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import inspect, text  # noqa: E402

from clasificador.control_db import repository as control_repo  # noqa: E402
from clasificador.control_db.engine import create_control_engine, create_control_tables  # noqa: E402
from clasificador.db.engine import create_db_engine, make_session_factory  # noqa: E402

CAMPANA_HISTORICA = "Campaña histórica"


def _db_name_from_url(db_url: str) -> str:
    return db_url.rstrip("/").rsplit("/", 1)[-1]


def _migrar_esquema_cliente(client_db_url: str) -> None:
    engine = create_db_engine(client_db_url)
    inspector = inspect(engine)

    if "campanas" not in inspector.get_table_names():
        print("  Creando tabla campanas...")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE campanas (
                        id_campana BIGINT AUTO_INCREMENT PRIMARY KEY,
                        nombre_campana VARCHAR(150) NOT NULL,
                        fecha_inicio DATE NULL,
                        estado VARCHAR(50) NOT NULL DEFAULT 'ACTIVA',
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            )
    else:
        print("  Tabla campanas ya existe, se omite.")

    columnas_imports = {c["name"] for c in inspector.get_columns("imports")}
    if "campana_id" not in columnas_imports:
        print("  Agregando columna imports.campana_id...")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE imports ADD COLUMN campana_id BIGINT NULL"))
            conn.execute(
                text(
                    "ALTER TABLE imports ADD CONSTRAINT fk_imports_campana "
                    "FOREIGN KEY (campana_id) REFERENCES campanas(id_campana)"
                )
            )
            conn.execute(text("CREATE INDEX idx_imports_campana_id ON imports (campana_id)"))
    else:
        print("  Columna imports.campana_id ya existe, se omite.")

    with engine.begin() as conn:
        historica_id = conn.execute(
            text("SELECT id_campana FROM campanas WHERE nombre_campana = :n"), {"n": CAMPANA_HISTORICA}
        ).scalar()
        if historica_id is None:
            print(f"  Creando campaña '{CAMPANA_HISTORICA}'...")
            result = conn.execute(
                text("INSERT INTO campanas (nombre_campana, estado) VALUES (:n, 'CERRADA')"),
                {"n": CAMPANA_HISTORICA},
            )
            historica_id = result.lastrowid

        actualizados = conn.execute(
            text("UPDATE imports SET campana_id = :cid WHERE campana_id IS NULL"), {"cid": historica_id}
        ).rowcount
        print(f"  {actualizados} import(s) asignados a '{CAMPANA_HISTORICA}'.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--control-db-url", required=True)
    parser.add_argument("--client-db-url", required=True, help="URL de la base de datos actual (con los datos reales)")
    parser.add_argument("--nombre-cliente", required=True)
    parser.add_argument("--super-admin-email", required=True)
    parser.add_argument("--super-admin-nombre", required=True)
    args = parser.parse_args()

    if not args.control_db_url.startswith("sqlite"):
        # La base de control es nueva: hay que crearla antes de poder conectarse
        # (a diferencia de SQLite, MySQL exige que la base ya exista). Se usa la
        # conexión a la base del cliente — que sí existe — para crearla.
        control_db_name = _db_name_from_url(args.control_db_url)
        print(f"0. Creando base de control '{control_db_name}' si no existe...")
        bootstrap_engine = create_db_engine(args.client_db_url)
        with bootstrap_engine.begin() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{control_db_name}`"))

    print("1. Base de control...")
    control_engine = create_control_engine(args.control_db_url)
    create_control_tables(control_engine)
    control_session_factory = make_session_factory(control_engine)

    with control_session_factory() as session:
        control_repo.seed_roles(session)
        session.commit()
        print("   Roles sembrados (super_admin, admin).")

        usuario = control_repo.get_usuario_by_email(session, args.super_admin_email)
        if usuario is None:
            control_repo.get_or_create_super_admin(session, args.super_admin_email, args.super_admin_nombre)
            session.commit()
            print(f"   Usuario super_admin creado: {args.super_admin_email}")
        else:
            print(f"   Usuario {args.super_admin_email} ya existe, se omite.")

        db_name = _db_name_from_url(args.client_db_url)
        clientes_existentes = {c.db_name: c for c in control_repo.list_clientes(session)}
        if db_name not in clientes_existentes:
            control_repo.create_cliente(session, nombre_cliente=args.nombre_cliente, db_name=db_name)
            session.commit()
            print(f"   Cliente '{args.nombre_cliente}' registrado (db_name={db_name}).")
        else:
            print(f"   Cliente con db_name={db_name} ya existe, se omite.")

    print("2. Esquema de la base del cliente existente...")
    _migrar_esquema_cliente(args.client_db_url)

    print("\nListo. Agrega a tu .env: CONTROL_DB_URL=" + args.control_db_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
