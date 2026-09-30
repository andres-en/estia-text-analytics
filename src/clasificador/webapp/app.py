from __future__ import annotations

from pathlib import Path

from flask import Flask, g, jsonify, send_from_directory

from ..config import load_settings
from ..control_db import repository as control_repo
from ..control_db.engine import create_control_engine, create_control_tables
from ..db.engine import make_session_factory
from .authz import load_current_user

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def create_app(db_url: str | None = None) -> Flask:
    """`db_url`, si se pasa, reemplaza la URL de la base de control (lo usan
    los tests para apuntar a SQLite). Las bases de cada cliente se resuelven
    dinámicamente por request, ver `webapp/tenancy.py`."""
    settings = load_settings(db_url_override=db_url)

    control_engine = create_control_engine(settings.control_db_url)
    create_control_tables(control_engine)
    control_session_factory = make_session_factory(control_engine)

    with control_session_factory() as session:
        control_repo.seed_roles(session)
        session.commit()

    upload_dir = PROJECT_ROOT / "uploads"
    upload_dir.mkdir(exist_ok=True)

    app = Flask(__name__, static_folder=None)
    app.secret_key = settings.secret_key
    app.config["SETTINGS"] = settings
    app.config["CONTROL_ENGINE"] = control_engine
    app.config["CONTROL_SESSION_FACTORY"] = control_session_factory
    app.config["CLIENT_ENGINES"] = {}
    app.config["ANALYSIS_RUNNERS"] = {}
    app.config["UPLOAD_DIR"] = upload_dir

    if settings.google_client_id and settings.google_client_secret:
        from .auth import init_oauth

        init_oauth(app)

    from .admin import admin_bp
    from .api import api_bp
    from .auth import auth_bp
    from .docs import docs_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    @app.before_request
    def _load_user() -> None:
        g.user = load_current_user()

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa(path: str):
        """Sirve el build de producción de React (`frontend/dist`).

        En desarrollo no se usa esta ruta: el frontend corre con `npm run dev`
        (Vite) en su propio puerto y hace proxy de `/api` hacia este servidor.
        """
        # Se recalcula a partir de PROJECT_ROOT en cada request (en vez de usar
        # la constante FRONTEND_DIST) para que los tests puedan monkeypatchear
        # PROJECT_ROOT y apuntar a un directorio sin build.
        frontend_dist = PROJECT_ROOT / "frontend" / "dist"
        if not frontend_dist.exists():
            return (
                jsonify(
                    {
                        "error": "The frontend is not built. Run 'npm run build' in frontend/, "
                        "or use 'npm run dev' for development (Vite on its own port)."
                    }
                ),
                404,
            )
        target = frontend_dist / path
        if path and target.is_file():
            return send_from_directory(frontend_dist, path)
        return send_from_directory(frontend_dist, "index.html")

    return app
