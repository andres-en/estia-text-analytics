from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import text

from ..analysis import repository as analysis_repo
from ..analysis.pricing import estimar_costo_usd
from ..analysis.rules_config import CampanaRulesConfig
from ..analysis.schema import EsquemaClasificacion
from ..analysis.schema_generator import GeneradorEsquemaError, generar_esquema
from ..control_db import permissions as perm
from ..control_db import repository as control_repo
from ..db import repository as client_repo
from ..db.engine import apply_ddl_file, create_all_tables
from .authz import require_permission
from .tenancy import get_client_engine, get_client_session_factory

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

DDL_PATH = Path(__file__).resolve().parent.parent.parent.parent / "sql" / "ddl.sql"


def _control_session_factory():
    return current_app.config["CONTROL_SESSION_FACTORY"]


def _slugify_db_name(nombre_cliente: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", nombre_cliente.strip().lower()).strip("_")
    return f"{slug}_clasificador_chat" if slug else "clasificador_chat"


def _cliente_json(c) -> dict:
    return {
        "id_cliente": c.id_cliente,
        "nombre_cliente": c.nombre_cliente,
        "db_name": c.db_name,
        "fecha_registro": c.fecha_registro.isoformat() if c.fecha_registro else None,
        "activo": c.activo,
    }


def _usuario_json(u) -> dict:
    return {
        "id_usuario": u.id_usuario,
        "nombre_usuario": u.nombre_usuario,
        "email": u.email,
        "rol": {"id_rol": u.rol.id_rol, "nombre_rol": u.rol.nombre_rol},
        "clientes": [{"id_cliente": c.id_cliente, "nombre_cliente": c.nombre_cliente} for c in u.clientes],
        "fecha_creacion": u.fecha_creacion.isoformat() if u.fecha_creacion else None,
        "activo": u.activo,
    }


def _campana_json(c) -> dict:
    # `esquema_clasificacion` vive como una clave más DENTRO de `configuracion`,
    # pero no es un campo de `CampanaRulesConfig` — hay que resolverlo aparte y
    # volver a incrustarlo, si no `CampanaRulesConfig.from_json(...).to_json()`
    # lo descarta silenciosamente (solo conoce sus propios campos).
    configuracion = CampanaRulesConfig.from_json(c.configuracion).to_json()
    esquema = EsquemaClasificacion.from_json((c.configuracion or {}).get("esquema_clasificacion"))
    configuracion["esquema_clasificacion"] = esquema.to_json() if esquema is not None else None
    return {
        "id_campana": c.id_campana,
        "nombre_campana": c.nombre_campana,
        "fecha_inicio": c.fecha_inicio.isoformat() if c.fecha_inicio else None,
        "estado": c.estado,
        # Siempre resuelta con los defaults (aunque configuracion sea NULL en la
        # base), para que el frontend tenga algo editable desde el primer momento.
        "configuracion": configuracion,
    }


# --- Clientes -----------------------------------------------------------


@admin_bp.route("/clientes", methods=["GET"])
@require_permission(perm.CLIENTES_CREAR)
def list_clientes():
    with _control_session_factory()() as session:
        return jsonify([_cliente_json(c) for c in control_repo.list_clientes(session)])


@admin_bp.route("/clientes", methods=["POST"])
@require_permission(perm.CLIENTES_CREAR)
def create_cliente():
    body = request.get_json(silent=True) or {}
    nombre_cliente = (body.get("nombre_cliente") or "").strip()
    if not nombre_cliente:
        return jsonify({"error": "nombre_cliente is required."}), 400

    with _control_session_factory()() as session:
        base_slug = _slugify_db_name(nombre_cliente)
        existentes = {c.db_name for c in control_repo.list_clientes(session)}
        db_name = base_slug
        suffix = 2
        while db_name in existentes:
            db_name = f"{base_slug}_{suffix}"
            suffix += 1

        control_engine = current_app.config["CONTROL_ENGINE"]
        if not str(control_engine.url).startswith("sqlite"):
            with control_engine.begin() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))

        client_engine = get_client_engine(db_name)
        apply_ddl_file(client_engine, DDL_PATH)
        # Red de seguridad: crea cualquier tabla del modelo SQLAlchemy que falte
        # en ddl.sql (idempotente — checkfirst=True — no toca lo que ya existe).
        # Ver scripts/migrate_add_ai_usage_table.py, mismo mecanismo.
        create_all_tables(client_engine)

        cliente = control_repo.create_cliente(session, nombre_cliente=nombre_cliente, db_name=db_name)
        session.commit()
        return jsonify(_cliente_json(cliente)), 201


@admin_bp.route("/clientes/<int:id_cliente>", methods=["PATCH"])
@require_permission(perm.CLIENTES_EDITAR)
def update_cliente(id_cliente: int):
    body = request.get_json(silent=True) or {}
    with _control_session_factory()() as session:
        cliente = control_repo.get_cliente(session, id_cliente)
        if cliente is None:
            return jsonify({"error": "Client not found."}), 404
        control_repo.update_cliente(
            session, cliente, nombre_cliente=body.get("nombre_cliente"), activo=body.get("activo")
        )
        session.commit()
        return jsonify(_cliente_json(cliente))


# --- Usuarios -------------------------------------------------------------


@admin_bp.route("/roles", methods=["GET"])
@require_permission(perm.USUARIOS_CREAR)
def list_roles():
    with _control_session_factory()() as session:
        roles = control_repo.list_roles(session)
        return jsonify([{"id_rol": r.id_rol, "nombre_rol": r.nombre_rol} for r in roles])


def _validar_id_clientes(session, id_rol: int, id_clientes: list[int]) -> str | None:
    """None si está bien; si no, el mensaje de error listo para 400."""
    for cid in id_clientes:
        if control_repo.get_cliente(session, cid) is None:
            return f"Cliente inválido: {cid}."
    rol = control_repo.get_rol(session, id_rol)
    if rol is not None and rol.nombre_rol != perm.ROL_SUPER_ADMIN and not id_clientes:
        return "Un usuario que no es super admin necesita al menos un cliente asignado."
    return None


@admin_bp.route("/usuarios", methods=["GET"])
@require_permission(perm.USUARIOS_CREAR)
def list_usuarios():
    id_clientes = None if g.user.es_super_admin else [c.id_cliente for c in g.user.clientes]
    with _control_session_factory()() as session:
        return jsonify([_usuario_json(u) for u in control_repo.list_usuarios(session, id_clientes=id_clientes)])


@admin_bp.route("/usuarios", methods=["POST"])
@require_permission(perm.USUARIOS_CREAR)
def create_usuario():
    body = request.get_json(silent=True) or {}
    nombre_usuario = (body.get("nombre_usuario") or "").strip()
    email = (body.get("email") or "").strip().lower()
    if not nombre_usuario or not email:
        return jsonify({"error": "nombre_usuario and email are required."}), 400

    with _control_session_factory()() as session:
        if control_repo.get_usuario_by_email(session, email) is not None:
            return jsonify({"error": f"A user with the email {email} already exists."}), 400

        if g.user.es_super_admin:
            id_rol = body.get("id_rol")
            id_clientes = body.get("id_clientes") or []
            if not id_rol:
                return jsonify({"error": "id_rol is required."}), 400
            if control_repo.get_rol(session, id_rol) is None:
                return jsonify({"error": "Invalid role."}), 400
            error = _validar_id_clientes(session, id_rol, id_clientes)
            if error is not None:
                return jsonify({"error": error}), 400
        else:
            # Un admin (no super admin) solo puede sumar gente de su equipo con
            # el rol base ("user"), a uno o varios de SUS PROPIOS clientes — no
            # puede elevar privilegios ni asignar clientes ajenos.
            rol_user = next(r for r in control_repo.list_roles(session) if r.nombre_rol == perm.ROL_USER)
            id_rol = rol_user.id_rol
            id_clientes = body.get("id_clientes") or []
            propios = {c.id_cliente for c in g.user.clientes}
            if not id_clientes or not set(id_clientes) <= propios:
                return jsonify({"error": "You can only assign clients that belong to you."}), 403

        usuario = control_repo.create_usuario(
            session, nombre_usuario=nombre_usuario, email=email, id_rol=id_rol, id_clientes=id_clientes
        )
        session.commit()
        return jsonify(_usuario_json(usuario)), 201


@admin_bp.route("/usuarios/<int:id_usuario>", methods=["PATCH"])
@require_permission(perm.USUARIOS_EDITAR)
def update_usuario(id_usuario: int):
    body = request.get_json(silent=True) or {}
    with _control_session_factory()() as session:
        usuario = control_repo.get_usuario_by_id(session, id_usuario)
        if usuario is None:
            return jsonify({"error": "User not found."}), 404

        id_rol_final = body.get("id_rol", usuario.id_rol)
        if "id_clientes" in body:
            error = _validar_id_clientes(session, id_rol_final, body["id_clientes"])
            if error is not None:
                return jsonify({"error": error}), 400

        kwargs: dict = {}
        if "nombre_usuario" in body:
            kwargs["nombre_usuario"] = body["nombre_usuario"]
        if "id_rol" in body:
            kwargs["id_rol"] = body["id_rol"]
        if "id_clientes" in body:
            kwargs["id_clientes"] = body["id_clientes"]
        if "activo" in body:
            kwargs["activo"] = body["activo"]
        control_repo.update_usuario(session, usuario, **kwargs)
        session.commit()
        return jsonify(_usuario_json(usuario))


# --- Campañas ---------------------------------------------------------------


@admin_bp.route("/campanas", methods=["GET"])
@require_permission(perm.CAMPANAS_CREAR)
def list_campanas():
    cliente_id = request.args.get("cliente_id", type=int)
    if cliente_id is None:
        return jsonify({"error": "cliente_id is required."}), 400
    with _control_session_factory()() as session:
        cliente = control_repo.get_cliente(session, cliente_id)
    if cliente is None:
        return jsonify({"error": "Client not found."}), 404
    with get_client_session_factory(cliente.db_name)() as client_session:
        return jsonify([_campana_json(c) for c in client_repo.list_campanas(client_session)])


def _parse_configuracion(body: dict) -> tuple[dict | None, tuple[dict, int] | None]:
    """Valida `configuracion` si viene en el body. Devuelve (config_json, error)
    — `error` es `(payload, status)` listo para `jsonify(*error)` si algo no compila.

    `esquema_clasificacion` (opcional, categorías/indicadores propios de la
    campaña — ver `analysis/schema.py`) vive como una clave más dentro de
    `configuracion`; se valida y se re-incrusta aparte porque no es un campo de
    `CampanaRulesConfig`."""
    if "configuracion" not in body or body["configuracion"] is None:
        return None, None
    if not isinstance(body["configuracion"], dict):
        return None, ({"error": "configuracion must be a JSON object."}, 400)

    raw = body["configuracion"]
    config = CampanaRulesConfig.from_json(raw)
    error = config.validar()
    if error is not None:
        return None, ({"error": error}, 400)
    resultado = config.to_json()

    esquema_raw = raw.get("esquema_clasificacion")
    if esquema_raw:
        esquema = EsquemaClasificacion.from_json(esquema_raw)
        error = esquema.validar()
        if error is not None:
            return None, ({"error": f"esquema_clasificacion: {error}"}, 400)
        resultado["esquema_clasificacion"] = esquema.to_json()

    return resultado, None


@admin_bp.route("/campanas/generar-esquema", methods=["POST"])
@require_permission(perm.CAMPANAS_CREAR)
def generar_esquema_campana():
    """Genera un `esquema_clasificacion` (categorías + indicadores + árbol de
    decisión) a partir de una descripción en texto libre, vía IA. NO guarda la
    campaña — el admin la revisa/edita en el frontend y la persiste llamando a
    crear/editar campaña como de costumbre. Sí registra los tokens gastados
    (ver `analysis/repository.registrar_uso_ia`), en la base del `cliente_id`
    dado — por eso es obligatorio, a diferencia del resto del body."""
    body = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "").strip()
    cliente_id = body.get("cliente_id")
    if not prompt:
        return jsonify({"error": "prompt is required."}), 400
    if not cliente_id:
        return jsonify({"error": "cliente_id is required."}), 400

    with _control_session_factory()() as session:
        cliente = control_repo.get_cliente(session, cliente_id)
    if cliente is None:
        return jsonify({"error": "Client not found."}), 404

    settings = current_app.config["SETTINGS"]
    try:
        api_key = settings.require_openai_api_key()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        esquema, uso = generar_esquema(prompt, api_key=api_key, modelo=settings.openai_model)
    except GeneradorEsquemaError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:  # fallo de red/API de OpenAI — no debe tumbar el request
        return jsonify({"error": f"Could not generate the schema: {exc}"}), 502

    with get_client_session_factory(cliente.db_name)() as client_session:
        analysis_repo.registrar_uso_ia(
            client_session,
            modelo=settings.openai_model,
            tipo="generar_esquema",
            tokens_prompt=uso["tokens_prompt"],
            tokens_completion=uso["tokens_completion"],
        )
        client_session.commit()

    return jsonify({"esquema_clasificacion": esquema.to_json()})


@admin_bp.route("/campanas", methods=["POST"])
@require_permission(perm.CAMPANAS_CREAR)
def create_campana():
    body = request.get_json(silent=True) or {}
    cliente_id = body.get("cliente_id")
    nombre_campana = (body.get("nombre_campana") or "").strip()
    if not cliente_id or not nombre_campana:
        return jsonify({"error": "cliente_id and nombre_campana are required."}), 400

    configuracion, error = _parse_configuracion(body)
    if error is not None:
        return jsonify(error[0]), error[1]

    with _control_session_factory()() as session:
        cliente = control_repo.get_cliente(session, cliente_id)
    if cliente is None:
        return jsonify({"error": "Client not found."}), 404

    with get_client_session_factory(cliente.db_name)() as client_session:
        campana = client_repo.create_campana(client_session, nombre_campana=nombre_campana, configuracion=configuracion)
        client_session.commit()
        return jsonify(_campana_json(campana)), 201


@admin_bp.route("/campanas/<int:id_campana>", methods=["PATCH"])
@require_permission(perm.CAMPANAS_CREAR)
def update_campana(id_campana: int):
    body = request.get_json(silent=True) or {}
    cliente_id = body.get("cliente_id")
    if not cliente_id:
        return jsonify({"error": "cliente_id is required."}), 400

    configuracion, error = _parse_configuracion(body)
    if error is not None:
        return jsonify(error[0]), error[1]

    with _control_session_factory()() as session:
        cliente = control_repo.get_cliente(session, cliente_id)
    if cliente is None:
        return jsonify({"error": "Client not found."}), 404

    with get_client_session_factory(cliente.db_name)() as client_session:
        campana = client_repo.get_campana(client_session, id_campana)
        if campana is None:
            return jsonify({"error": "Campaign not found."}), 404
        kwargs: dict = {}
        if "nombre_campana" in body:
            kwargs["nombre_campana"] = body["nombre_campana"]
        if "estado" in body:
            kwargs["estado"] = body["estado"]
        if "configuracion" in body:
            kwargs["configuracion"] = configuracion
        client_repo.update_campana(client_session, campana, **kwargs)
        client_session.commit()
        return jsonify(_campana_json(campana))


@admin_bp.route("/uso-ia")
@require_permission(perm.ADMINISTRACION_ACCESO)
def uso_ia():
    """Tokens gastados en OpenAI para el cliente dado — clasificación de
    conversaciones y generación de esquemas por IA. Con costo estimado (ver
    `analysis/pricing.py`; `None` si no hay precio conocido para ese modelo)."""
    cliente_id = request.args.get("cliente_id", type=int)
    if cliente_id is None:
        return jsonify({"error": "cliente_id is required."}), 400
    desde = dt.date.fromisoformat(request.args["desde"]) if request.args.get("desde") else None
    hasta = dt.date.fromisoformat(request.args["hasta"]) if request.args.get("hasta") else None

    with _control_session_factory()() as session:
        cliente = control_repo.get_cliente(session, cliente_id)
    if cliente is None:
        return jsonify({"error": "Client not found."}), 404

    with get_client_session_factory(cliente.db_name)() as client_session:
        filas = analysis_repo.resumen_uso_ia(client_session, date_from=desde, date_to=hasta)
        por_mes = analysis_repo.resumen_uso_ia_mensual(client_session, date_from=desde, date_to=hasta)

    for fila in filas:
        fila["costo_usd"] = estimar_costo_usd(fila["modelo"], fila["tokens_prompt"], fila["tokens_completion"])
    for fila in por_mes:
        fila["costo_usd"] = estimar_costo_usd(fila["modelo"], fila["tokens_prompt"], fila["tokens_completion"])

    return jsonify(
        {
            "filas": filas,
            "por_mes": por_mes,
            "tokens_totales": sum(f["tokens_prompt"] + f["tokens_completion"] for f in filas),
            "costo_total_usd": sum(f["costo_usd"] for f in filas if f["costo_usd"] is not None) or None,
        }
    )


@admin_bp.route("/conversaciones", methods=["DELETE"])
@require_permission(perm.CONVERSACIONES_ELIMINAR)
def eliminar_conversaciones():
    """Borra las conversaciones (mensajes y análisis) de una fecha, para que un
    super admin pueda reprocesar una carga con datos incorrectos. Ver
    `db.repository.eliminar_conversaciones_por_fecha` — no toca `imports` ni
    `staging_messages`, y el registro de uso de IA (`ai_usage`) se conserva."""
    body = request.get_json(silent=True) or {}
    cliente_id = body.get("cliente_id")
    fecha_raw = body.get("fecha")
    if not cliente_id or not fecha_raw:
        return jsonify({"error": "cliente_id and fecha are required."}), 400
    try:
        fecha = dt.date.fromisoformat(fecha_raw)
    except ValueError:
        return jsonify({"error": "Invalid fecha, expected format YYYY-MM-DD."}), 400

    with _control_session_factory()() as session:
        cliente = control_repo.get_cliente(session, cliente_id)
    if cliente is None:
        return jsonify({"error": "Client not found."}), 404

    with get_client_session_factory(cliente.db_name)() as client_session:
        resultado = client_repo.eliminar_conversaciones_por_fecha(client_session, fecha)
        client_session.commit()

    return jsonify(
        {
            "conversaciones_eliminadas": resultado.conversaciones_eliminadas,
            "mensajes_eliminados": resultado.mensajes_eliminados,
        }
    )
