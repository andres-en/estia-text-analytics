"""Authentication, role-based permissions and tenant isolation of the web API."""

from __future__ import annotations

import pytest

from clasificador.control_db import repository as control_repo
from clasificador.control_db.permissions import ROL_ADMIN, ROL_SUPER_ADMIN, ROL_USER
from clasificador.db.engine import create_all_tables, create_db_engine
from clasificador.webapp.app import create_app


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr("clasificador.webapp.app.PROJECT_ROOT", tmp_path)
    for db_name in ("tenant_a", "tenant_b"):
        create_all_tables(create_db_engine(f"sqlite:///{tmp_path / (db_name + '.db')}"))
    app = create_app(db_url=f"sqlite:///{tmp_path / 'control.db'}")
    app.config["TESTING"] = True
    with app.config["CONTROL_SESSION_FACTORY"]() as session:
        for name, db_name in (("Tenant A", "tenant_a"), ("Tenant B", "tenant_b")):
            control_repo.create_cliente(session, nombre_cliente=name, db_name=db_name)
        session.commit()
    return app


def _tenant_id(app, db_name: str) -> int:
    with app.config["CONTROL_SESSION_FACTORY"]() as session:
        return next(c.id_cliente for c in control_repo.list_clientes(session) if c.db_name == db_name)


def _create_user(app, *, role: str, tenants: list[str], email: str, active: bool = True) -> int:
    with app.config["CONTROL_SESSION_FACTORY"]() as session:
        rol = next(r for r in control_repo.list_roles(session) if r.nombre_rol == role)
        ids = [c.id_cliente for c in control_repo.list_clientes(session) if c.db_name in tenants]
        user = control_repo.create_usuario(
            session, nombre_usuario=email.split("@")[0], email=email, id_rol=rol.id_rol, id_clientes=ids
        )
        if not active:
            control_repo.update_usuario(session, user, activo=False)
        session.commit()
        return user.id_usuario


def _login(test_client, user_id: int) -> None:
    with test_client.session_transaction() as sess:
        sess["user_id"] = user_id


# --- Authentication -------------------------------------------------------------


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/api/auth/me"),
        ("get", "/api/conversations"),
        ("get", "/api/dashboard"),
        ("post", "/api/upload"),
        ("get", "/api/admin/clientes"),
        ("get", "/api/admin/usuarios"),
    ],
)
def test_protected_endpoints_require_a_session(app, method, path):
    with app.test_client() as c:
        resp = getattr(c, method)(path)
    assert resp.status_code == 401
    assert resp.get_json() == {"error": "Not authenticated."}


def test_me_returns_the_signed_in_user_and_its_active_tenant(app):
    user_id = _create_user(app, role=ROL_USER, tenants=["tenant_a"], email="ana@example.com")
    with app.test_client() as c:
        _login(c, user_id)
        body = c.get("/api/auth/me").get_json()
    assert body["email"] == "ana@example.com"
    assert body["rol"] == ROL_USER
    assert body["es_super_admin"] is False
    assert body["cliente_activo"]["nombre_cliente"] == "Tenant A"


def test_deactivated_user_is_treated_as_signed_out(app):
    user_id = _create_user(app, role=ROL_USER, tenants=["tenant_a"], email="old@example.com", active=False)
    with app.test_client() as c:
        _login(c, user_id)
        assert c.get("/api/auth/me").status_code == 401


def test_logout_clears_the_session(app):
    user_id = _create_user(app, role=ROL_USER, tenants=["tenant_a"], email="bye@example.com")
    with app.test_client() as c:
        _login(c, user_id)
        assert c.get("/api/auth/me").status_code == 200
        assert c.post("/api/auth/logout").get_json() == {"ok": True}
        assert c.get("/api/auth/me").status_code == 401


# --- Role-based permissions -------------------------------------------------------


def test_plain_user_cannot_reach_admin_endpoints(app):
    user_id = _create_user(app, role=ROL_USER, tenants=["tenant_a"], email="user@example.com")
    with app.test_client() as c:
        _login(c, user_id)
        for path in ("/api/admin/clientes", "/api/admin/usuarios", "/api/admin/roles"):
            resp = c.get(path)
            assert resp.status_code == 403, path
            assert resp.get_json() == {"error": "You do not have permission for this action."}


def test_admin_can_manage_users_but_not_tenants(app):
    admin_id = _create_user(app, role=ROL_ADMIN, tenants=["tenant_a"], email="admin@example.com")
    with app.test_client() as c:
        _login(c, admin_id)
        assert c.get("/api/admin/usuarios").status_code == 200
        assert c.get("/api/admin/clientes").status_code == 403
        assert c.post("/api/admin/clientes", json={"nombre_cliente": "Nope"}).status_code == 403


def test_super_admin_can_list_and_rename_tenants(app):
    # Tenant *creation* provisions a MySQL database: see tests/test_mysql_integration.py.
    super_id = _create_user(app, role=ROL_SUPER_ADMIN, tenants=[], email="root@example.com")
    tenant_a = _tenant_id(app, "tenant_a")
    with app.test_client() as c:
        _login(c, super_id)
        assert {t["nombre_cliente"] for t in c.get("/api/admin/clientes").get_json()} == {"Tenant A", "Tenant B"}
        resp = c.patch(f"/api/admin/clientes/{tenant_a}", json={"nombre_cliente": "Tenant A (renamed)"})
        assert resp.status_code == 200
        assert resp.get_json()["nombre_cliente"] == "Tenant A (renamed)"


# --- Tenant isolation -----------------------------------------------------------


def test_super_admin_must_pick_an_active_tenant_before_reading_data(app):
    super_id = _create_user(app, role=ROL_SUPER_ADMIN, tenants=[], email="root@example.com")
    with app.test_client() as c:
        _login(c, super_id)
        resp = c.get("/api/conversations")
        assert resp.status_code == 400
        assert resp.get_json() == {"error": "Please select an active client."}

        ok = c.post("/api/auth/session/cliente-activo", json={"cliente_id": _tenant_id(app, "tenant_b")})
        assert ok.status_code == 200
        assert c.get("/api/conversations").status_code == 200
        assert c.get("/api/auth/me").get_json()["cliente_activo"]["nombre_cliente"] == "Tenant B"


def test_single_tenant_user_cannot_switch_tenants(app):
    user_id = _create_user(app, role=ROL_USER, tenants=["tenant_a"], email="one@example.com")
    with app.test_client() as c:
        _login(c, user_id)
        resp = c.post("/api/auth/session/cliente-activo", json={"cliente_id": _tenant_id(app, "tenant_b")})
    assert resp.status_code == 403


def test_multi_tenant_user_cannot_select_a_tenant_that_is_not_theirs(app):
    with app.config["CONTROL_SESSION_FACTORY"]() as session:
        control_repo.create_cliente(session, nombre_cliente="Tenant C", db_name="tenant_c")
        session.commit()
    user_id = _create_user(app, role=ROL_USER, tenants=["tenant_a", "tenant_b"], email="two@example.com")
    with app.test_client() as c:
        _login(c, user_id)
        resp = c.post("/api/auth/session/cliente-activo", json={"cliente_id": _tenant_id(app, "tenant_c")})
        assert resp.status_code == 403
        assert resp.get_json() == {"error": "That client is not one of yours."}
        allowed = c.post("/api/auth/session/cliente-activo", json={"cliente_id": _tenant_id(app, "tenant_b")})
        assert allowed.status_code == 200


def test_inactive_tenant_cannot_be_selected(app):
    tenant_b = _tenant_id(app, "tenant_b")
    with app.config["CONTROL_SESSION_FACTORY"]() as session:
        control_repo.update_cliente(session, control_repo.get_cliente(session, tenant_b), activo=False)
        session.commit()
    super_id = _create_user(app, role=ROL_SUPER_ADMIN, tenants=[], email="root@example.com")
    with app.test_client() as c:
        _login(c, super_id)
        resp = c.post("/api/auth/session/cliente-activo", json={"cliente_id": tenant_b})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "Invalid client."}
