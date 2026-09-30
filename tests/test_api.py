from __future__ import annotations

import io
import threading
import time

import pytest

from clasificador.analysis.analyzer import AnalysisReport
from clasificador.config import build_client_db_url
from clasificador.control_db import repository as control_repo
from clasificador.control_db.permissions import ROL_ADMIN
from clasificador.db import repository as client_repo
from clasificador.db.engine import create_all_tables, create_db_engine, make_session_factory
from clasificador.webapp.app import create_app


def _make_app(tmp_path, monkeypatch, *, client_db_name: str = "cliente_prueba"):
    """Levanta la app con una base de control y una base de cliente, ambas
    SQLite en `tmp_path`, y crea las tablas de la base del cliente (en
    producción eso lo hace `/api/admin/clientes` al crear el cliente)."""
    monkeypatch.setattr("clasificador.webapp.app.PROJECT_ROOT", tmp_path)
    control_url = f"sqlite:///{tmp_path / 'control.db'}"
    create_all_tables(create_db_engine(f"sqlite:///{tmp_path / (client_db_name + '.db')}"))

    app = create_app(db_url=control_url)
    app.config["TESTING"] = True
    return app


def _login_as_cliente_user(
    app, test_client, *, db_name: str = "cliente_prueba", nombre_cliente: str = "Cliente de prueba"
):
    """Crea (si hace falta) un cliente + un usuario de rol `admin` asignado a
    ese cliente en la base de control, y autentica al test client como ese
    usuario (sin pasar por el flujo real de Google: `session_transaction`
    escribe directamente la cookie de sesión firmada, igual que haría el
    callback de OAuth)."""
    with app.config["CONTROL_SESSION_FACTORY"]() as session:
        cliente = next((c for c in control_repo.list_clientes(session) if c.db_name == db_name), None)
        if cliente is None:
            cliente = control_repo.create_cliente(session, nombre_cliente=nombre_cliente, db_name=db_name)
        rol_admin = next(r for r in control_repo.list_roles(session) if r.nombre_rol == ROL_ADMIN)
        usuario = control_repo.create_usuario(
            session,
            nombre_usuario="Usuario de prueba",
            email=f"test-{cliente.id_cliente}@example.com",
            id_rol=rol_admin.id_rol,
            id_clientes=[cliente.id_cliente],
        )
        session.commit()
        usuario_id = usuario.id_usuario

    with test_client.session_transaction() as sess:
        sess["user_id"] = usuario_id


def _crear_campana(app, *, db_name: str = "cliente_prueba", nombre: str = "Campaña de prueba") -> int:
    client_url = build_client_db_url(app.config["SETTINGS"].control_db_url, db_name)
    session_factory = make_session_factory(create_db_engine(client_url))
    with session_factory() as session:
        campana = client_repo.create_campana(session, nombre_campana=nombre)
        session.commit()
        return campana.id_campana


@pytest.fixture
def client(monkeypatch, tmp_path):
    app = _make_app(tmp_path, monkeypatch)
    with app.test_client() as test_client:
        _login_as_cliente_user(app, test_client)
        test_client.campana_id = _crear_campana(app)
        yield test_client


def _upload_sample(client, sample_xlsx_path):
    with open(sample_xlsx_path, "rb") as f:
        data = {"file": (f, "CDR Chatbot y conversacion.xlsx"), "campana_id": str(client.campana_id)}
        return client.post("/api/upload", data=data, content_type="multipart/form-data")


def _wait_for_background_analysis(client, timeout: float = 60.0) -> None:
    """`/api/upload` dispara la fase 2 en un hilo de fondo (ver AnalysisRunner).
    A diferencia del SQLite `:memory:` de antes (aislado por conexión/hilo),
    ahora las bases de cliente son archivos compartidos entre hilos, así que
    un `run_analysis` manual en el hilo principal puede pisarse con el que ya
    está corriendo en background — hay que esperar a que termine primero."""
    deadline = time.monotonic() + timeout
    status = client.get("/api/analyze/status").get_json()
    while status["state"] == "running" and time.monotonic() < deadline:
        time.sleep(0.05)
        status = client.get("/api/analyze/status").get_json()
    assert status["state"] != "running", "El análisis de fondo no terminó a tiempo"


def test_conversations_empty_db_returns_empty_list(client):
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 50}


def test_upload_without_file_returns_400(client):
    resp = client.post("/api/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert "No file" in resp.get_json()["error"]


def test_upload_rejects_non_xlsx(client):
    data = {"file": (io.BytesIO(b"hola"), "archivo.csv")}
    resp = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert ".xlsx" in resp.get_json()["error"]


def test_upload_sample_returns_report(client, sample_xlsx_path):
    resp = _upload_sample(client, sample_xlsx_path)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "COMPLETED_WITH_WARNINGS"
    assert body["rows_received"] == 1163
    assert body["conversations_created"] == 958
    assert body["messages_created"] == 1338
    assert len(body["warnings"]) == 4


def test_upload_auto_triggers_background_analysis(monkeypatch, tmp_path, sample_xlsx_path):
    """El análisis (fase 2) arranca solo tras la carga, sin bloquear la respuesta.

    `run_analysis` se reemplaza por una versión mínima y rápida: su corrección
    (reglas, IA, idempotencia) ya está cubierta por test_analysis_integration.py
    contra SQLite en memoria. Lo que este test verifica es la parte nueva —
    la orquestación web: que `/api/upload` dispare un hilo de fondo y que
    `/api/analyze/status` refleje su progreso hasta terminar — sin pagar el
    costo de reclasificar todas las conversaciones de la muestra en cada corrida.
    """
    monkeypatch.setattr("clasificador.webapp.app.PROJECT_ROOT", tmp_path)

    def fake_run_analysis(
        session_factory,
        ai_client=None,
        limit=None,
        force=False,
        on_progress=None,
        commit_every=100,
        ai_client_esquema=None,
    ):
        report = AnalysisReport(total_evaluadas=3, resueltas_por_regla=3)
        if on_progress is not None:
            on_progress(report, 3)
        return report

    monkeypatch.setattr("clasificador.webapp.analysis_runner.run_analysis", fake_run_analysis)

    app = _make_app(tmp_path, monkeypatch)

    with app.test_client() as client:
        _login_as_cliente_user(app, client)
        client.campana_id = _crear_campana(app)

        resp = _upload_sample(client, sample_xlsx_path)
        assert resp.get_json()["analysis_started"] is True

        deadline = time.monotonic() + 10
        status = client.get("/api/analyze/status").get_json()
        while status["state"] == "running" and time.monotonic() < deadline:
            time.sleep(0.2)
            status = client.get("/api/analyze/status").get_json()

        assert status["state"] == "done"
        assert status["usa_ia"] is False  # sin OPENAI_API_KEY (fixture _sin_openai_key_real)
        assert status["evaluadas"] == 3
        assert status["resueltas_por_regla"] == 3
        assert status["errores"] == 0


def test_upload_does_not_start_a_second_analysis_while_one_is_running(monkeypatch, tmp_path, sample_xlsx_path):
    """Dos cargas seguidas no deben pisarse: la segunda no lanza otra corrida
    mientras la primera sigue en curso (mismas conversaciones pendientes)."""
    monkeypatch.setattr("clasificador.webapp.app.PROJECT_ROOT", tmp_path)

    release = threading.Event()

    def fake_run_analysis(
        session_factory,
        ai_client=None,
        limit=None,
        force=False,
        on_progress=None,
        commit_every=100,
        ai_client_esquema=None,
    ):
        # Sin timeout a propósito: una carga real (incluida la segunda, que este test
        # dispara mientras la primera sigue "corriendo") puede tardar más de unos
        # segundos. `release.set()` siempre se llama al final del test; el hilo es
        # `daemon=True`, así que un test que fallara antes de esa línea no cuelga la suite.
        release.wait()
        return AnalysisReport()

    monkeypatch.setattr("clasificador.webapp.analysis_runner.run_analysis", fake_run_analysis)

    app = _make_app(tmp_path, monkeypatch)

    with app.test_client() as client:
        _login_as_cliente_user(app, client)
        client.campana_id = _crear_campana(app)

        first = _upload_sample(client, sample_xlsx_path)
        assert first.get_json()["analysis_started"] is True

        second = _upload_sample(client, sample_xlsx_path)
        assert second.get_json()["analysis_started"] is False

        release.set()


def test_conversation_detail_matches_known_conversation(client, sample_xlsx_path):
    _upload_sample(client, sample_xlsx_path)

    session_id = "573001000002.botco-4402-acme_venta.1001"
    resp = client.get(f"/api/conversations/{session_id}")
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["session_id"] == session_id
    assert body["conn_id_count"] == 4
    system_events = [m for m in body["messages"] if m["sender"] == "SYSTEM"]
    assert len(system_events) == 3  # hallazgo 2/3: sin duplicados
    assert any(m["message"] == "Quiero usar mi cupo" for m in body["messages"])
    assert body["categoria"] is None  # aún no se corrió la clasificación


def test_conversation_detail_404_for_unknown_session(client):
    resp = client.get("/api/conversations/no-existe-123")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_search_by_phone_filters_results(client, sample_xlsx_path):
    _upload_sample(client, sample_xlsx_path)

    resp = client.get("/api/conversations?q=573001000003")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] >= 1
    assert all(c["customer_phone"] == "573001000003" for c in body["items"])


def test_pagination_splits_results(client, sample_xlsx_path):
    _upload_sample(client, sample_xlsx_path)

    page1 = client.get("/api/conversations?page=1&page_size=10").get_json()
    page2 = client.get("/api/conversations?page=2&page_size=10").get_json()

    assert page1["total"] == 958
    assert len(page1["items"]) == 10
    assert len(page2["items"]) == 10
    ids_page1 = {c["session_id"] for c in page1["items"]}
    ids_page2 = {c["session_id"] for c in page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_date_range_filters_results(client, sample_xlsx_path):
    _upload_sample(client, sample_xlsx_path)

    resp = client.get("/api/conversations?desde=2026-08-02&hasta=2026-08-02&page_size=500")
    body = resp.get_json()
    assert body["total"] > 0
    assert all(c["started_at"].startswith("2026-08-02") for c in body["items"])


def test_category_filter_after_running_rule_based_analysis(client, sample_xlsx_path):
    _upload_sample(client, sample_xlsx_path)
    _wait_for_background_analysis(client)  # solo reglas, determinístico, sin red (sin OPENAI_API_KEY)

    resp = client.get("/api/conversations?categoria=INTERESADO&page_size=500")
    body = resp.get_json()
    assert body["total"] > 0
    assert all(c["categoria"] == "INTERESADO" for c in body["items"])


def test_dashboard_shape_and_values_after_analysis(client, sample_xlsx_path):
    _upload_sample(client, sample_xlsx_path)
    _wait_for_background_analysis(client)

    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    body = resp.get_json()

    assert set(body.keys()) == {
        "category_counts",
        "subcategory_counts",
        "category_counts_trend",
        "method_counts",
        "business_indicators",
        "business_indicators_trend",
        "daily_trend",
    }
    assert body["category_counts"]["SIN_RESPUESTA"] == 896
    assert body["method_counts"] == {"RULE": body["method_counts"]["RULE"]}  # sin IA, todo por regla
    assert isinstance(body["business_indicators"]["rechazos_explicitos"], int)
    assert set(body["business_indicators_trend"].keys()) == {"current", "previous"}
    assert set(body["category_counts_trend"].keys()) == {"current", "previous"}
    assert len(body["daily_trend"]) > 0


def test_categorias_endpoint_incluye_default_y_sin_analizar(client, sample_xlsx_path):
    _upload_sample(client, sample_xlsx_path)
    _wait_for_background_analysis(client)

    resp = client.get("/api/categorias")
    assert resp.status_code == 200
    body = resp.get_json()
    ids = [c["id"] for c in body]
    assert "INTERESADO" in ids
    assert ids[-1] == "SIN_ANALIZAR"
    assert all({"id", "label", "color", "orden"} <= set(c.keys()) for c in body)


def test_spa_fallback_returns_404_without_build(client):
    resp = client.get("/pagina-cualquiera")
    assert resp.status_code == 404
    assert "frontend" in resp.get_json()["error"].lower()
