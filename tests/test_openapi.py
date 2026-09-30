"""Contract tests: the hand-written OpenAPI spec is valid and matches the Flask routes."""

from __future__ import annotations

import re

import pytest
import yaml
from openapi_spec_validator import validate

from clasificador.webapp.app import create_app
from clasificador.webapp.docs import SPEC_PATH

IGNORED_METHODS = {"HEAD", "OPTIONS"}


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr("clasificador.webapp.app.PROJECT_ROOT", tmp_path)
    return create_app(db_url=f"sqlite:///{tmp_path / 'control.db'}")


def _flask_api_operations(app) -> set[tuple[str, str]]:
    """`(openapi_path, method)` for every `/api/*` route, e.g. `/api/x/<int:id>` -> `/api/x/{id}`."""
    ops = set()
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/") or rule.endpoint.startswith("docs."):
            continue
        path = re.sub(r"<(?:[^:<>]+:)?([^<>]+)>", r"{\1}", rule.rule)
        ops |= {(path, m.lower()) for m in rule.methods - IGNORED_METHODS}
    return ops


def _spec_operations(spec: dict) -> set[tuple[str, str]]:
    return {(path, method) for path, item in spec["paths"].items() for method in item if method != "parameters"}


def test_spec_is_a_valid_openapi_document(spec):
    validate(spec)


def test_every_route_is_documented(app, spec):
    missing = _flask_api_operations(app) - _spec_operations(spec)
    assert not missing, f"Routes missing from openapi.yaml: {sorted(missing)}"


def test_spec_documents_no_route_that_does_not_exist(app, spec):
    stale = _spec_operations(spec) - _flask_api_operations(app)
    assert not stale, f"openapi.yaml documents routes that do not exist: {sorted(stale)}"


def test_spec_and_swagger_ui_are_served(app):
    with app.test_client() as c:
        spec_resp = c.get("/api/openapi.yaml")
        ui_resp = c.get("/api/docs")
    assert spec_resp.status_code == 200
    assert spec_resp.mimetype == "application/yaml"
    assert yaml.safe_load(spec_resp.data)["info"]["title"] == "Estia API"
    assert ui_resp.status_code == 200
    assert b"swagger-ui" in ui_resp.data
