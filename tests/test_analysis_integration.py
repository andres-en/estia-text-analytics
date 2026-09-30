from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from clasificador.analysis.analyzer import run_analysis
from clasificador.analysis.repository import resumen_por_categoria
from clasificador.analysis.types import (
    INTERESADO,
    NO_INTERESADO,
    RESOLVIO_DUDAS,
    SIN_RESPUESTA,
    AnalysisFlags,
)
from clasificador.db.engine import create_all_tables, create_db_engine, make_session_factory
from clasificador.db.models import Conversation, ConversationAnalysis, Import, Message


class FakeIA:
    """IA simulada: marca busco_informacion si el cliente escribió la palabra clave."""

    modelo = "fake-model"

    def __init__(self, palabra="interes"):
        self.palabra = palabra
        self.llamadas = 0

    def clasificar(self, transcript):
        self.llamadas += 1
        texto = " ".join(m.message.lower() for m in transcript.messages if m.sender == "CUSTOMER")
        hizo = self.palabra in texto
        return AnalysisFlags(busco_informacion=hizo), "justificación simulada", {"fake": True}


class IAQueFalla:
    modelo = "fake-roto"

    def clasificar(self, transcript):
        raise RuntimeError("API caída")


@pytest.fixture
def session_factory():
    engine = create_db_engine("sqlite:///:memory:")
    create_all_tables(engine)
    return make_session_factory(engine)


def _sembrar(session_factory, conversaciones):
    """conversaciones: lista de (session_id, [(sender, texto), ...])"""
    with session_factory() as s:
        imp = Import(file_name="t.xlsx", status="COMPLETED", started_at=dt.datetime.now())
        s.add(imp)
        s.flush()
        for i, (sid, mensajes) in enumerate(conversaciones):
            conv = Conversation(
                session_id=sid,
                session_pattern="REAL",
                customer_phone="573000000000",
                started_at=dt.datetime(2026, 8, 1, 9, 0, 0),
                ended_at=dt.datetime(2026, 8, 1, 9, 30, 0),
                message_count=len(mensajes),
                conn_id_count=1,
                iniciada_por=mensajes[0][0] if mensajes else "BOT",
                first_import_id=imp.id,
                last_import_id=imp.id,
            )
            s.add(conv)
            s.flush()
            for j, (sender, texto) in enumerate(mensajes, start=1):
                s.add(
                    Message(
                        conversation_id=conv.id,
                        conn_id="1",
                        message_timestamp=dt.datetime(2026, 8, 1, 9, j),
                        sequence_number=j,
                        sender=sender,
                        message_type="TEXT",
                        message=texto,
                        source_row=j,
                        source_import_id=imp.id,
                        dedup_hash=f"h{i}-{j}",
                    )
                )
        s.commit()


def test_cascada_completa_reglas_e_ia(session_factory):
    _sembrar(
        session_factory,
        [
            ("s-sin-respuesta", [("BOT", "👋 Hola, tienes cupo disponible")]),
            # INTERESADO exige que el cliente concretara: el bot registró la solicitud.
            ("s-interes", [("CUSTOMER", "Sí"), ("BOT", "✅ Hemos registrado tu interés.")]),
            (
                "s-rechazo",
                [
                    ("CUSTOMER", "No estoy interesado"),
                    ("BOT", "Lamentamos que por ahora no desees utilizar tu cupo"),
                ],
            ),
            ("s-gris", [("CUSTOMER", "Los interes que manejan"), ("BOT", "La tasa es...")]),
        ],
    )

    ia = FakeIA()
    report = run_analysis(session_factory, ai_client=ia)

    assert report.total_evaluadas == 4
    assert report.resueltas_por_regla == 3
    assert report.resueltas_por_ia == 1
    assert ia.llamadas == 1  # solo la zona gris llegó a la IA

    with session_factory() as s:
        cats = dict(resumen_por_categoria(s))
    assert cats[SIN_RESPUESTA] == 1
    assert cats[INTERESADO] == 1
    assert cats[NO_INTERESADO] == 1
    assert cats[RESOLVIO_DUDAS] == 1


def test_no_llama_a_la_ia_cuando_las_reglas_bastan(session_factory):
    _sembrar(
        session_factory,
        [
            ("s1", [("BOT", "proactivo")]),
            ("s2", [("CUSTOMER", "Sí"), ("BOT", "✅ Hemos registrado tu interés.")]),
            ("s3", [("CUSTOMER", "Quiero usar mi cupo"), ("BOT", "ok")]),  # solo botón
        ],
    )
    ia = FakeIA()
    run_analysis(session_factory, ai_client=ia)
    assert ia.llamadas == 0


def test_es_idempotente_no_reanaliza(session_factory):
    _sembrar(session_factory, [("s1", [("CUSTOMER", "Quiero usar mi cupo"), ("BOT", "ok")])])

    primera = run_analysis(session_factory)
    assert primera.nuevas == 1

    segunda = run_analysis(session_factory)
    assert segunda.total_evaluadas == 0  # ya estaba analizada, no se vuelve a tocar

    tercera = run_analysis(session_factory, force=True)
    assert tercera.total_evaluadas == 1
    assert tercera.actualizadas == 1
    assert tercera.nuevas == 0

    with session_factory() as s:
        filas = s.execute(select(ConversationAnalysis)).scalars().all()
    assert len(filas) == 1  # nunca se duplica


def test_sin_cliente_de_ia_la_zona_gris_queda_pendiente(session_factory):
    _sembrar(session_factory, [("s-gris", [("CUSTOMER", "Los intereses"), ("BOT", "...")])])
    report = run_analysis(session_factory, ai_client=None)
    assert report.pendientes_de_ia == 1
    assert report.nuevas == 0


def test_fallo_de_la_api_no_aborta_el_lote(session_factory):
    _sembrar(
        session_factory,
        [
            ("s-gris", [("CUSTOMER", "Los intereses"), ("BOT", "...")]),
            ("s-ok", [("CUSTOMER", "Quiero usar mi cupo"), ("BOT", "ok")]),
        ],
    )
    report = run_analysis(session_factory, ai_client=IAQueFalla())

    assert len(report.errores) == 1
    assert "API caída" in report.errores[0].mensaje
    assert report.resueltas_por_regla == 1  # la otra sí se procesó


def test_la_ia_no_puede_apagar_una_senal_de_regla(session_factory):
    # El cliente rechazó (regla) y además preguntó (IA): por jerarquía gana
    # RESOLVIO_DUDAS, pero el rechazo debe seguir registrado en los flags.
    _sembrar(
        session_factory,
        [
            (
                "s-mixta",
                [
                    ("CUSTOMER", "Que interes manejan"),
                    ("BOT", "La tasa es variable"),
                    ("CUSTOMER", "No estoy interesado"),
                ],
            )
        ],
    )
    run_analysis(session_factory, ai_client=FakeIA())

    with session_factory() as s:
        fila = s.execute(select(ConversationAnalysis)).scalar_one()

    assert fila.categoria_final == RESOLVIO_DUDAS  # jerarquía
    assert fila.rechazo_explicito is True  # señal conservada
    assert fila.busco_informacion is True
    assert fila.metodo == "AI"
    assert fila.modelo_ia == "fake-model"


def test_limit_controla_cuantas_se_procesan(session_factory):
    _sembrar(session_factory, [(f"s{i}", [("BOT", "proactivo")]) for i in range(5)])
    report = run_analysis(session_factory, limit=2)
    assert report.total_evaluadas == 2
