from __future__ import annotations

import dataclasses
import functools

from flask import current_app, g, jsonify, session

from ..control_db import repository as control_repo
from ..control_db.permissions import ADMINISTRACION_ACCESO


@dataclasses.dataclass(frozen=True)
class ClienteRef:
    id_cliente: int
    nombre_cliente: str
    db_name: str


@dataclasses.dataclass(frozen=True)
class CurrentUser:
    id_usuario: int
    nombre_usuario: str
    email: str
    id_rol: int
    rol_nombre: str
    permisos: list[str]
    clientes: list[ClienteRef]

    @property
    def es_super_admin(self) -> bool:
        return len(self.clientes) == 0 and ADMINISTRACION_ACCESO in self.permisos


def load_current_user() -> CurrentUser | None:
    """Reconstruye el usuario actual desde la cookie de sesión, leyendo la base
    de control. Se llama en cada request (`before_request`); devuelve un
    dataclass en vez de un objeto ORM para no arrastrar problemas de sesión
    detached una vez que la conexión de control se cierra."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    with current_app.config["CONTROL_SESSION_FACTORY"]() as control_session:
        usuario = control_repo.get_usuario_by_id(control_session, user_id)
        if usuario is None or not usuario.activo:
            return None
        return CurrentUser(
            id_usuario=usuario.id_usuario,
            nombre_usuario=usuario.nombre_usuario,
            email=usuario.email,
            id_rol=usuario.id_rol,
            rol_nombre=usuario.rol.nombre_rol,
            permisos=list(usuario.rol.permisos),
            clientes=sorted(
                (ClienteRef(c.id_cliente, c.nombre_cliente, c.db_name) for c in usuario.clientes),
                key=lambda c: c.nombre_cliente,
            ),
        )


def require_login(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return jsonify({"error": "Not authenticated."}), 401
        return view(*args, **kwargs)

    return wrapped


def require_permission(permiso: str):
    def decorator(view):
        @functools.wraps(view)
        @require_login
        def wrapped(*args, **kwargs):
            if permiso not in g.user.permisos:
                return jsonify({"error": "You do not have permission for this action."}), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator
