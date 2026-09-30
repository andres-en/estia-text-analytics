from __future__ import annotations

from clasificador.control_db import repository as control_repo
from clasificador.control_db.permissions import ROL_ADMIN, ROL_SUPER_ADMIN
from clasificador.db.engine import create_all_tables, create_db_engine

from .test_api import _make_app


def _crear_cliente(app, tmp_path, *, db_name: str, nombre_cliente: str) -> int:
    create_all_tables(create_db_engine(f"sqlite:///{tmp_path / (db_name + '.db')}"))
    with app.config["CONTROL_SESSION_FACTORY"]() as session:
        cliente = control_repo.create_cliente(session, nombre_cliente=nombre_cliente, db_name=db_name)
        session.commit()
        return cliente.id_cliente


def _login_as(test_client, id_usuario: int) -> None:
    with test_client.session_transaction() as sess:
        sess["user_id"] = id_usuario


def _crear_usuario_control(app, *, nombre_rol: str, id_clientes: list[int], email: str) -> int:
    with app.config["CONTROL_SESSION_FACTORY"]() as session:
        rol = next(r for r in control_repo.list_roles(session) if r.nombre_rol == nombre_rol)
        usuario = control_repo.create_usuario(
            session, nombre_usuario="Prueba", email=email, id_rol=rol.id_rol, id_clientes=id_clientes
        )
        session.commit()
        return usuario.id_usuario


def test_usuario_con_dos_clientes_puede_cambiar_entre_ellos(monkeypatch, tmp_path):
    app = _make_app(tmp_path, monkeypatch)

    with app.test_client() as client:
        id_cliente_a = _crear_cliente(app, tmp_path, db_name="cliente_prueba", nombre_cliente="Cliente A")
        id_cliente_b = _crear_cliente(app, tmp_path, db_name="cliente_b", nombre_cliente="Cliente B")

        usuario_id = _crear_usuario_control(
            app, nombre_rol=ROL_ADMIN, id_clientes=[id_cliente_a, id_cliente_b], email="multi@example.com"
        )
        _login_as(client, usuario_id)

        me = client.get("/api/auth/me").get_json()
        assert {c["id_cliente"] for c in me["clientes"]} == {id_cliente_a, id_cliente_b}
        assert me["cliente_activo"] is None  # todavía no eligió ninguno

        # No puede pedir un cliente que no es suyo.
        otro = client.post("/api/auth/session/cliente-activo", json={"cliente_id": 999999})
        assert otro.status_code in (400, 403)

        ok = client.post("/api/auth/session/cliente-activo", json={"cliente_id": id_cliente_a})
        assert ok.status_code == 200
        assert client.get("/api/conversations").status_code == 200

        client.post("/api/auth/session/cliente-activo", json={"cliente_id": id_cliente_b})
        me2 = client.get("/api/auth/me").get_json()
        assert me2["cliente_activo"]["id_cliente"] == id_cliente_b


def test_admin_no_puede_asignar_cliente_ajeno_a_usuario_nuevo(monkeypatch, tmp_path):
    app = _make_app(tmp_path, monkeypatch)
    with app.test_client() as client:
        id_cliente_a = _crear_cliente(app, tmp_path, db_name="cliente_prueba", nombre_cliente="Cliente A")
        id_cliente_b = _crear_cliente(app, tmp_path, db_name="cliente_b", nombre_cliente="Cliente B")

        admin_id = _crear_usuario_control(
            app, nombre_rol=ROL_ADMIN, id_clientes=[id_cliente_a], email="admin@example.com"
        )
        _login_as(client, admin_id)

        resp = client.post(
            "/api/admin/usuarios",
            json={"nombre_usuario": "Intruso", "email": "intruso@example.com", "id_clientes": [id_cliente_b]},
        )
        assert resp.status_code == 403


def test_crear_usuario_no_super_admin_sin_clientes_falla(monkeypatch, tmp_path):
    app = _make_app(tmp_path, monkeypatch)
    with app.test_client() as client:
        super_admin_id = _crear_usuario_control(
            app, nombre_rol=ROL_SUPER_ADMIN, id_clientes=[], email="super@example.com"
        )
        _login_as(client, super_admin_id)

        with app.config["CONTROL_SESSION_FACTORY"]() as session:
            rol_admin = next(r for r in control_repo.list_roles(session) if r.nombre_rol == ROL_ADMIN)

        resp = client.post(
            "/api/admin/usuarios",
            json={
                "nombre_usuario": "Sin cliente",
                "email": "sincliente@example.com",
                "id_rol": rol_admin.id_rol,
                "id_clientes": [],
            },
        )
        assert resp.status_code == 400
