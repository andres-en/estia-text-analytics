from __future__ import annotations

from .app import create_app

if __name__ == "__main__":
    app = create_app()
    settings = app.config["SETTINGS"]
    app.run(host=settings.flask_host, port=settings.flask_port, debug=True, threaded=True)
