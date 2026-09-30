from __future__ import annotations

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, current_app, g, jsonify, redirect, request, session, url_for

from ..control_db import repository as control_repo
from .tenancy import resolve_cliente_activo

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

oauth = OAuth()


def init_oauth(app) -> None:
    """Registra el cliente OAuth de Google. Se llama una vez desde `create_app`."""
    client_id, client_secret = app.config["SETTINGS"].require_google_oauth()
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def _external_base_url() -> str:
    """Origen (scheme://host) tal como lo ve el navegador — NO necesariamente el
    que ve Flask.

    En dev, `/api/*` llega a través del proxy de Vite con `changeOrigin: true`,
    que reescribe el header Host para que Flask siempre vea `localhost:<FLASK_PORT>`,
    sin importar desde qué host (LAN, hostname interno) entró el usuario real.
    Si `redirect_uri` se construyera con ese host "disfrazado", la cookie de
    sesión que guarda el `state` de OAuth queda atada al host real (ej.
    `my-pc.lan.example.com:5173`, que es lo que el navegador ve), pero
    Google redirige de vuelta a `localhost` — un origen distinto, así que el
    navegador no manda esa cookie y Authlib revienta con `MismatchingStateError`.

    `xfwd: true` en el proxy de Vite (ver frontend/vite.config.ts) reenvía el
    host real en `X-Forwarded-Host`, que se usa acá con prioridad.
    """
    host = request.headers.get("X-Forwarded-Host") or request.host
    scheme = request.headers.get("X-Forwarded-Proto") or request.scheme
    return f"{scheme}://{host}"


@auth_bp.route("/google/login")
def google_login():
    redirect_uri = f"{_external_base_url()}{url_for('auth.google_callback')}"
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback")
def google_callback():
    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo") or oauth.google.userinfo(token=token)
    email = userinfo["email"]
    google_sub = userinfo["sub"]

    with current_app.config["CONTROL_SESSION_FACTORY"]() as control_session:
        usuario = control_repo.get_usuario_by_email(control_session, email)
        if usuario is None or not usuario.activo:
            return jsonify({"error": f"The email {email} is not authorized to sign in."}), 403
        if usuario.google_sub != google_sub:
            usuario.google_sub = google_sub
            control_session.commit()
        session.clear()
        session["user_id"] = usuario.id_usuario

    # Vuelve al mismo host desde el que se inició sesión (ver _external_base_url),
    # no a una URL fija — así funciona igual desde localhost, la IP de la LAN o
    # un hostname interno.
    return redirect(f"{_external_base_url()}/")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@auth_bp.route("/me")
def me():
    if g.user is None:
        return jsonify({"error": "Not authenticated."}), 401

    activo = resolve_cliente_activo()
    return jsonify(
        {
            "id_usuario": g.user.id_usuario,
            "nombre_usuario": g.user.nombre_usuario,
            "email": g.user.email,
            "rol": g.user.rol_nombre,
            "permisos": g.user.permisos,
            "es_super_admin": g.user.es_super_admin,
            "clientes": [{"id_cliente": c.id_cliente, "nombre_cliente": c.nombre_cliente} for c in g.user.clientes],
            "cliente_activo": None if activo is None else {"id_cliente": activo[0], "nombre_cliente": activo[1]},
        }
    )


@auth_bp.route("/session/cliente-activo", methods=["POST"])
def set_cliente_activo():
    if g.user is None:
        return jsonify({"error": "Not authenticated."}), 401
    if not g.user.es_super_admin and len(g.user.clientes) <= 1:
        return jsonify({"error": "You do not have more than one client to choose from."}), 403

    body = request.get_json(silent=True) or {}
    cliente_id = body.get("cliente_id")
    if cliente_id is not None:
        if not g.user.es_super_admin and cliente_id not in {c.id_cliente for c in g.user.clientes}:
            return jsonify({"error": "That client is not one of yours."}), 403
        with current_app.config["CONTROL_SESSION_FACTORY"]() as control_session:
            cliente = control_repo.get_cliente(control_session, cliente_id)
            if cliente is None or not cliente.activo:
                return jsonify({"error": "Invalid client."}), 400
    session["cliente_activo_id"] = cliente_id
    return jsonify({"ok": True})
