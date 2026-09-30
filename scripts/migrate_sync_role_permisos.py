"""Migración puntual/recurrente: sincroniza `roles.permisos` (base de control)
con las listas PERMISOS_* definidas en `control_db/permissions.py`.

Los roles fijos (super_admin/admin/user) se crean una sola vez (`seed_roles`,
ver `control_db/repository.py`) si la fila todavía no existe — pero esa
función es idempotente por EXISTENCIA de la fila, no por su contenido: si
después se agrega un permiso nuevo a un rol en el código (ej.
CONVERSACIONES_ELIMINAR), un rol ya sembrado en producción no lo recibe solo.
Este script resincroniza los tres roles fijos a lo que dice el código en ese
momento, sin tocar roles custom que alguien haya creado a mano. Correrlo de
nuevo después de cualquier cambio a PERMISOS_SUPER_ADMIN/PERMISOS_ADMIN/
PERMISOS_USER es seguro (idempotente).

Uso:
    python scripts/migrate_sync_role_permisos.py --control-db-url mysql+mysqlconnector://usuario:clave@host:3306/clasificador_control
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from clasificador.control_db import permissions as perm  # noqa: E402
from clasificador.control_db.models import Rol  # noqa: E402
from clasificador.db.engine import create_db_engine  # noqa: E402

PERMISOS_POR_ROL = {
    perm.ROL_SUPER_ADMIN: perm.PERMISOS_SUPER_ADMIN,
    perm.ROL_ADMIN: perm.PERMISOS_ADMIN,
    perm.ROL_USER: perm.PERMISOS_USER,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--control-db-url", required=True, help="URL de la base de control")
    args = parser.parse_args()

    engine = create_db_engine(args.control_db_url)
    with Session(engine) as session:
        actualizados = 0
        for nombre_rol, permisos_esperados in PERMISOS_POR_ROL.items():
            rol = session.execute(select(Rol).where(Rol.nombre_rol == nombre_rol)).scalar_one_or_none()
            if rol is None:
                print(f"Rol '{nombre_rol}' no existe todavía — lo crea seed_roles() al arrancar la app.")
                continue
            if set(rol.permisos) == set(permisos_esperados):
                print(f"Rol '{nombre_rol}' ya está sincronizado.")
                continue
            agregados = sorted(set(permisos_esperados) - set(rol.permisos))
            quitados = sorted(set(rol.permisos) - set(permisos_esperados))
            rol.permisos = list(permisos_esperados)
            actualizados += 1
            print(
                f"Rol '{nombre_rol}' actualizado — agregados: {agregados or 'ninguno'}, quitados: {quitados or 'ninguno'}."
            )
        session.commit()

    print(f"Listo. {actualizados} rol(es) actualizado(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
