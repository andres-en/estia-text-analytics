from __future__ import annotations

import dataclasses

from clasificador.analysis.schema import EsquemaClasificacion
from clasificador.control_db.permissions import ROL_SUPER_ADMIN

from .test_admin_multicliente import _crear_cliente, _crear_usuario_control, _login_as
from .test_api import _make_app

ESQUEMA_VALIDO = {
    "categorias": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
    "indicadores": [{"id": "x", "label": "X", "tipo": "ia", "descripcion_ia": "algo"}],
    "arbol_decision": [{"condicion": {"x": True}, "categoria": "A"}, {"condicion": {}, "categoria": "B"}],
    "categoria_sin_respuesta": "B",
}


def _setup(app, tmp_path):
    id_cliente = _crear_cliente(app, tmp_path, db_name="cliente_campanas", nombre_cliente="Cliente Campañas")
    usuario_id = _crear_usuario_control(
        app, nombre_rol=ROL_SUPER_ADMIN, id_clientes=[id_cliente], email="admin@example.com"
    )
    return id_cliente, usuario_id


def test_crear_campana_con_esquema_lo_persiste_y_lo_devuelve(monkeypatch, tmp_path):
    app = _make_app(tmp_path, monkeypatch)
    id_cliente, usuario_id = _setup(app, tmp_path)

    with app.test_client() as client:
        _login_as(client, usuario_id)
        resp = client.post(
            "/api/admin/campanas",
            json={
                "cliente_id": id_cliente,
                "nombre_campana": "Campaña con esquema",
                "configuracion": {"esquema_clasificacion": ESQUEMA_VALIDO},
            },
        )
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()
        assert [c["id"] for c in body["configuracion"]["esquema_clasificacion"]["categorias"]] == ["A", "B"]
        # Los campos de CampanaRulesConfig siguen presentes con sus defaults —
        # el esquema no los reemplaza.
        assert body["configuracion"]["boton_cupo"] == "quiero usar mi cupo"


def test_crear_campana_con_esquema_invalido_devuelve_400(monkeypatch, tmp_path):
    app = _make_app(tmp_path, monkeypatch)
    id_cliente, usuario_id = _setup(app, tmp_path)

    esquema_malo = {**ESQUEMA_VALIDO, "arbol_decision": [{"condicion": {}, "categoria": "NO_EXISTE"}]}

    with app.test_client() as client:
        _login_as(client, usuario_id)
        resp = client.post(
            "/api/admin/campanas",
            json={
                "cliente_id": id_cliente,
                "nombre_campana": "Campaña rota",
                "configuracion": {"esquema_clasificacion": esquema_malo},
            },
        )
        assert resp.status_code == 400
        assert "esquema_clasificacion" in resp.get_json()["error"]


def test_editar_solo_nombre_no_borra_el_esquema_existente(monkeypatch, tmp_path):
    """Bug real que se estaba corrigiendo: `_campana_json`/`_parse_configuracion`
    reconstruían `configuracion` solo a partir de los campos de
    `CampanaRulesConfig`, descartando en silencio `esquema_clasificacion`."""
    app = _make_app(tmp_path, monkeypatch)
    id_cliente, usuario_id = _setup(app, tmp_path)

    with app.test_client() as client:
        _login_as(client, usuario_id)
        creada = client.post(
            "/api/admin/campanas",
            json={
                "cliente_id": id_cliente,
                "nombre_campana": "Original",
                "configuracion": {"esquema_clasificacion": ESQUEMA_VALIDO},
            },
        ).get_json()

        editada = client.patch(
            f"/api/admin/campanas/{creada['id_campana']}",
            json={"cliente_id": id_cliente, "nombre_campana": "Renombrada"},
        )
        assert editada.status_code == 200
        body = editada.get_json()
        assert body["nombre_campana"] == "Renombrada"
        assert [c["id"] for c in body["configuracion"]["esquema_clasificacion"]["categorias"]] == ["A", "B"]


def test_generar_esquema_endpoint_devuelve_esquema_generado(monkeypatch, tmp_path):
    app = _make_app(tmp_path, monkeypatch)
    id_cliente, usuario_id = _setup(app, tmp_path)
    # El fixture autouse `_sin_openai_key_real` (conftest.py) vacía OPENAI_API_KEY
    # para todos los tests — acá se simula que sí está configurada.
    app.config["SETTINGS"] = dataclasses.replace(app.config["SETTINGS"], openai_api_key="fake-key")

    def _fake_generar_esquema(prompt, api_key, modelo, timeout=60.0):
        assert prompt == "Vendo cursos online"
        assert api_key == "fake-key"
        return EsquemaClasificacion.from_json(ESQUEMA_VALIDO), {"tokens_prompt": 100, "tokens_completion": 20}

    monkeypatch.setattr("clasificador.webapp.admin.generar_esquema", _fake_generar_esquema)

    with app.test_client() as client:
        _login_as(client, usuario_id)
        resp = client.post(
            "/api/admin/campanas/generar-esquema",
            json={"prompt": "Vendo cursos online", "cliente_id": id_cliente},
        )
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()
        assert [c["id"] for c in body["esquema_clasificacion"]["categorias"]] == ["A", "B"]

    # Los tokens de la llamada quedaron registrados en la base de ESE cliente.
    with app.test_client() as client:
        _login_as(client, usuario_id)
        uso = client.get(f"/api/admin/uso-ia?cliente_id={id_cliente}").get_json()
    assert uso["tokens_totales"] == 120
    assert any(f["tipo"] == "generar_esquema" for f in uso["filas"])
    assert len(uso["por_mes"]) == 1
    assert uso["por_mes"][0]["tokens_prompt"] == 100
    assert uso["por_mes"][0]["tokens_completion"] == 20


def test_generar_esquema_sin_prompt_devuelve_400(monkeypatch, tmp_path):
    app = _make_app(tmp_path, monkeypatch)
    id_cliente, usuario_id = _setup(app, tmp_path)

    with app.test_client() as client:
        _login_as(client, usuario_id)
        resp = client.post("/api/admin/campanas/generar-esquema", json={"prompt": "   ", "cliente_id": id_cliente})
        assert resp.status_code == 400


def test_generar_esquema_sin_api_key_devuelve_400(monkeypatch, tmp_path):
    app = _make_app(tmp_path, monkeypatch)
    id_cliente, usuario_id = _setup(app, tmp_path)

    with app.test_client() as client:
        _login_as(client, usuario_id)
        resp = client.post("/api/admin/campanas/generar-esquema", json={"prompt": "algo", "cliente_id": id_cliente})
        assert resp.status_code == 400
        assert "OPENAI_API_KEY" in resp.get_json()["error"]
