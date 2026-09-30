from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_FLASK_HOST = "0.0.0.0"
DEFAULT_FLASK_PORT = 5050


@dataclass(frozen=True)
class Settings:
    control_db_url: str
    secret_key: str
    google_client_id: str | None = None
    google_client_secret: str | None = None
    openai_api_key: str | None = None
    openai_model: str = DEFAULT_OPENAI_MODEL
    flask_host: str = DEFAULT_FLASK_HOST
    flask_port: int = DEFAULT_FLASK_PORT
    # A dónde redirigir tras el login con Google. En dev es el puerto de Vite
    # (ej. http://localhost:5173/); en prod, "/" (Flask sirve el build).
    frontend_url: str = "/"

    def require_openai_api_key(self) -> str:
        """Devuelve la API key o explica cómo configurarla.

        Se valida solo cuando realmente se va a llamar a la API, para que todo el
        resto del pipeline (incluida la clasificación por reglas) funcione sin ella.
        """
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY no está configurada. Agrégala a .env para poder usar "
                "la capa de IA. La clasificación por reglas funciona sin ella."
            )
        return self.openai_api_key

    def require_google_oauth(self) -> tuple[str, str]:
        if not self.google_client_id or not self.google_client_secret:
            raise RuntimeError(
                "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET no están configurados. "
                "Agrégalos a .env para habilitar el login con Google."
            )
        return self.google_client_id, self.google_client_secret


def load_settings(db_url_override: str | None = None) -> Settings:
    """Carga la configuración desde el entorno / `.env`.

    `db_url_override` reemplaza la URL de la base de control — lo usan los
    tests para apuntar a SQLite en memoria en vez de MySQL.
    """
    load_dotenv()
    control_db_url = db_url_override or os.environ.get("CONTROL_DB_URL")
    if not control_db_url:
        raise RuntimeError(
            "CONTROL_DB_URL no está configurado. Define la variable de entorno "
            "CONTROL_DB_URL (en .env o en el shell), o pásala con --db-url. "
            "Ejemplo MySQL: mysql+mysqlconnector://usuario:clave@host:3306/clasificador_control "
            "Ejemplo SQLite: sqlite:///./control.db"
        )
    return Settings(
        control_db_url=control_db_url,
        secret_key=os.environ.get("SECRET_KEY") or "dev-secret-key-cambiar-en-produccion",
        google_client_id=os.environ.get("GOOGLE_CLIENT_ID") or None,
        google_client_secret=os.environ.get("GOOGLE_CLIENT_SECRET") or None,
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        openai_model=os.environ.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL,
        flask_host=os.environ.get("FLASK_HOST") or DEFAULT_FLASK_HOST,
        flask_port=int(os.environ.get("FLASK_PORT") or DEFAULT_FLASK_PORT),
        frontend_url=os.environ.get("FRONTEND_URL") or "/",
    )


def build_client_db_url(base_db_url: str, db_name: str) -> str:
    """Arma la URL de conexión de la base de un cliente a partir de la base de
    control, reutilizando el mismo host/usuario/clave y sustituyendo solo el
    nombre de la base.

    Soporta tanto URLs de MySQL (`mysql+mysqlconnector://user:pass@host:port/db`)
    como de SQLite (`sqlite:///./archivo.db`, usado en tests): en ese caso
    `db_name` reemplaza el nombre del archivo, en el mismo directorio.
    """
    if not re.match(r"^[A-Za-z0-9_]+$", db_name):
        raise ValueError(f"Nombre de base de datos inválido: {db_name!r}")

    if base_db_url.startswith("sqlite"):
        prefix = "sqlite:///"
        if not base_db_url.startswith(prefix):
            raise ValueError(f"URL de SQLite no soportada: {base_db_url!r}")
        # Se arma con pathlib (no partición de string) porque en Windows la ruta
        # del archivo usa backslashes, no "/" — partir por "/" se rompe ahí.
        raw_path = base_db_url[len(prefix) :]
        new_path = Path(raw_path).parent / f"{db_name}.db"
        return f"{prefix}{new_path}"

    prefix, _, _ = base_db_url.rpartition("/")
    return f"{prefix}/{db_name}"
