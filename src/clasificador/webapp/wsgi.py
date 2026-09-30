"""Punto de entrada para un servidor WSGI de producción (gunicorn/waitress),
a diferencia de `__main__.py` (`python -m clasificador.webapp`), que usa el
servidor de desarrollo de Flask (`app.run(debug=True)`) — no apto para
producción: de un solo hilo real por request y expone el debugger interactivo.

Uso: gunicorn clasificador.webapp.wsgi:app
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from .app import create_app

# Production must never fall back to the development session-signing key:
# anyone who knows it could forge a session cookie. Fail fast instead.
load_dotenv()
if not os.environ.get("SECRET_KEY"):
    raise RuntimeError(
        "SECRET_KEY is not set. Generate one with "
        '`python -c "import secrets; print(secrets.token_hex(32))"` and add it to .env.'
    )

app = create_app()
