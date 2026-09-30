"""Interactive API documentation: the OpenAPI spec and a Swagger UI page.

The spec is maintained by hand in `openapi.yaml` (Flask does not generate one);
`tests/test_openapi.py` fails if a route is added without documenting it.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response

SPEC_PATH = Path(__file__).resolve().parent / "openapi.yaml"

docs_bp = Blueprint("docs", __name__, url_prefix="/api")

_SWAGGER_UI_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Estia API docs</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({ url: "/api/openapi.yaml", dom_id: "#swagger-ui" });
  </script>
</body>
</html>"""


@docs_bp.route("/openapi.yaml")
def openapi_spec():
    return Response(SPEC_PATH.read_text(encoding="utf-8"), mimetype="application/yaml")


@docs_bp.route("/docs")
def swagger_ui():
    return Response(_SWAGGER_UI_HTML, mimetype="text/html")
