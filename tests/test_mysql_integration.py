"""End-to-end tests against a real MySQL server (the production database engine).

They cover what SQLite cannot: provisioning a tenant database from `sql/ddl.sql`
(MySQL DDL) and running the whole upload -> import -> classify flow on it.

Skipped unless `MYSQL_TEST_URL` points to a server the tests may create and drop
databases on, e.g.:

    docker run -d --name mysql-test -e MYSQL_ROOT_PASSWORD=root -p 3306:3306 mysql:8.4
    MYSQL_TEST_URL=mysql+mysqlconnector://root:root@127.0.0.1:3306 pytest -m mysql
"""

from __future__ import annotations

import os
import time

import pytest
from sqlalchemy import create_engine, text

from clasificador.control_db import repository as control_repo
from clasificador.control_db.permissions import ROL_SUPER_ADMIN
from clasificador.webapp.app import create_app

MYSQL_TEST_URL = os.environ.get("MYSQL_TEST_URL")
CONTROL_DB = "clasificador_control_test"
TENANT_NAME = "Integration Tenant"
TENANT_DB = "integration_tenant_clasificador_chat"

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(not MYSQL_TEST_URL, reason="MYSQL_TEST_URL is not set"),
]


def _drop_test_databases() -> None:
    engine = create_engine(MYSQL_TEST_URL)
    with engine.begin() as conn:
        for db in (CONTROL_DB, TENANT_DB):
            conn.execute(text(f"DROP DATABASE IF EXISTS `{db}`"))
        conn.execute(text(f"CREATE DATABASE `{CONTROL_DB}`"))
    engine.dispose()


@pytest.fixture
def signed_in_super_admin(monkeypatch, tmp_path):
    _drop_test_databases()
    monkeypatch.setattr("clasificador.webapp.app.PROJECT_ROOT", tmp_path)
    app = create_app(db_url=f"{MYSQL_TEST_URL}/{CONTROL_DB}")
    app.config["TESTING"] = True
    with app.config["CONTROL_SESSION_FACTORY"]() as session:
        rol = next(r for r in control_repo.list_roles(session) if r.nombre_rol == ROL_SUPER_ADMIN)
        user = control_repo.create_usuario(
            session, nombre_usuario="root", email="root@example.com", id_rol=rol.id_rol, id_clientes=[]
        )
        session.commit()
        user_id = user.id_usuario
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
        yield client
    for engine in app.config["CLIENT_ENGINES"].values():
        engine.dispose()
    app.config["CONTROL_ENGINE"].dispose()
    _drop_test_databases()


def _wait_for_analysis(client, timeout: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout
    status = client.get("/api/analyze/status").get_json()
    while status["state"] == "running" and time.monotonic() < deadline:
        time.sleep(0.2)
        status = client.get("/api/analyze/status").get_json()
    return status


def test_tenant_provisioning_and_full_pipeline_on_mysql(signed_in_super_admin, sample_xlsx_path):
    client = signed_in_super_admin

    # 1. Creating a tenant provisions its own MySQL database from sql/ddl.sql.
    created = client.post("/api/admin/clientes", json={"nombre_cliente": TENANT_NAME})
    assert created.status_code == 201
    tenant = created.get_json()
    assert tenant["db_name"] == TENANT_DB

    assert client.post("/api/auth/session/cliente-activo", json={"cliente_id": tenant["id_cliente"]}).status_code == 200
    campaign = client.post(
        "/api/admin/campanas", json={"cliente_id": tenant["id_cliente"], "nombre_campana": "Integration"}
    )
    assert campaign.status_code == 201

    # 2. Upload -> import (idempotent) -> background classification.
    def upload():
        with open(sample_xlsx_path, "rb") as f:
            data = {"file": (f, "sample_cdr.xlsx"), "campana_id": str(campaign.get_json()["id_campana"])}
            return client.post("/api/upload", data=data, content_type="multipart/form-data")

    first = upload().get_json()
    assert first["conversations_created"] == 958
    assert first["messages_created"] == 1338
    status = _wait_for_analysis(client)
    assert status["state"] == "done"
    assert status["errores"] == 0

    second = upload().get_json()
    assert second["conversations_created"] == 0
    assert second["messages_skipped_duplicate"] == 1338

    # 3. Reads work against the tenant database.
    dashboard = client.get("/api/dashboard").get_json()
    assert dashboard["category_counts"]["SIN_RESPUESTA"] == 896
    assert dashboard["category_counts"]["INTERESADO"] == 15
    assert client.get("/api/conversations?q=573001000003").get_json()["total"] >= 1
