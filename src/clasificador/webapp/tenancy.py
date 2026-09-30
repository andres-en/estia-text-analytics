from __future__ import annotations

import functools
import threading

from flask import current_app, g, jsonify, session
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import build_client_db_url
from ..control_db import repository as control_repo
from ..db.engine import create_db_engine, make_session_factory

_engines_lock = threading.Lock()


def get_client_engine(db_name: str) -> Engine:
    """Devuelve (y cachea) el engine de la base de un cliente.

    Cada base de cliente comparte host/usuario/clave con la base de control
    (ver `build_client_db_url`); solo cambia el nombre de la base. El cache
    evita crear un engine (y su pool de conexiones) nuevo en cada request.
    """
    engines: dict[str, Engine] = current_app.config["CLIENT_ENGINES"]
    engine = engines.get(db_name)
    if engine is not None:
        return engine
    with _engines_lock:
        engine = engines.get(db_name)
        if engine is None:
            settings = current_app.config["SETTINGS"]
            url = build_client_db_url(settings.control_db_url, db_name)
            engine = create_db_engine(url)
            engines[db_name] = engine
    return engine


def get_client_session_factory(db_name: str) -> sessionmaker[Session]:
    return make_session_factory(get_client_engine(db_name))


def resolve_cliente_activo() -> tuple[int, str, str] | None:
    """(id_cliente, nombre_cliente, db_name) del cliente que aplica a esta
    request.

    - Exactamente un cliente asignado -> ese, fijo (no hay nada que elegir).
    - Cero o dos-o-más -> el que haya elegido en sesión (`cliente_activo_id`):
      un super admin puede elegir cualquiera; alguien con varios clientes
      propios solo puede elegir uno de LOS SUYOS. `None` si todavía no eligió.
    """
    user = g.user
    if len(user.clientes) == 1:
        c = user.clientes[0]
        return c.id_cliente, c.nombre_cliente, c.db_name

    cliente_id = session.get("cliente_activo_id")
    if cliente_id is None:
        return None
    if not user.es_super_admin and cliente_id not in {c.id_cliente for c in user.clientes}:
        return None

    with current_app.config["CONTROL_SESSION_FACTORY"]() as control_session:
        cliente = control_repo.get_cliente(control_session, cliente_id)
        if cliente is None or not cliente.activo:
            return None
        return cliente.id_cliente, cliente.nombre_cliente, cliente.db_name


def require_cliente_activo(view):
    """Exige sesión válida y un cliente resuelto; deja `g.cliente_activo_*`
    listos para que la vista arme su sesión de BD con
    `get_client_session_factory(g.cliente_activo_db_name)`."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return jsonify({"error": "Not authenticated."}), 401
        activo = resolve_cliente_activo()
        if activo is None:
            return jsonify({"error": "Please select an active client."}), 400
        g.cliente_activo_id, g.cliente_activo_nombre, g.cliente_activo_db_name = activo
        return view(*args, **kwargs)

    return wrapped
