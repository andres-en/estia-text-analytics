from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from clasificador.analysis.pricing import estimar_costo_usd
from clasificador.analysis.repository import (
    guardar_analisis,
    registrar_uso_ia,
    resumen_uso_ia,
    resumen_uso_ia_mensual,
)
from clasificador.analysis.types import AnalysisResult
from clasificador.db.engine import create_all_tables, create_db_engine, make_session_factory
from clasificador.db.models import AIUsage, Conversation, Import


@pytest.fixture
def session_factory():
    engine = create_db_engine("sqlite:///:memory:")
    create_all_tables(engine)
    return make_session_factory(engine)


def _crear_conversacion(session, session_id="s1"):
    imp = Import(file_name="t.xlsx", status="COMPLETED", started_at=dt.datetime.now())
    session.add(imp)
    session.flush()
    conv = Conversation(
        session_id=session_id,
        session_pattern="REAL",
        started_at=dt.datetime(2026, 8, 1, 9, 0),
        ended_at=dt.datetime(2026, 8, 1, 9, 0),
        message_count=1,
        conn_id_count=1,
        iniciada_por="CUSTOMER",
        first_import_id=imp.id,
        last_import_id=imp.id,
    )
    session.add(conv)
    session.flush()
    return conv


def test_registrar_y_resumir_uso_ia(session_factory):
    with session_factory() as s:
        registrar_uso_ia(s, modelo="gpt-4o-mini", tipo="clasificacion", tokens_prompt=1000, tokens_completion=100)
        registrar_uso_ia(s, modelo="gpt-4o-mini", tipo="clasificacion", tokens_prompt=500, tokens_completion=50)
        registrar_uso_ia(s, modelo="gpt-4o-mini", tipo="generar_esquema", tokens_prompt=2000, tokens_completion=300)
        s.commit()

        resumen = resumen_uso_ia(s)

    por_tipo = {f["tipo"]: f for f in resumen}
    assert por_tipo["clasificacion"]["llamadas"] == 2
    assert por_tipo["clasificacion"]["tokens_prompt"] == 1500
    assert por_tipo["clasificacion"]["tokens_completion"] == 150
    assert por_tipo["generar_esquema"]["llamadas"] == 1


def test_resumen_uso_ia_filtra_por_fecha(session_factory):
    with session_factory() as s:
        s.add(
            AIUsage(
                ocurrido_en=dt.datetime(2026, 8, 1, 9, 0),
                modelo="gpt-4o-mini",
                tipo="clasificacion",
                tokens_prompt=100,
                tokens_completion=10,
            )
        )
        s.add(
            AIUsage(
                ocurrido_en=dt.datetime(2026, 8, 15, 9, 0),
                modelo="gpt-4o-mini",
                tipo="clasificacion",
                tokens_prompt=200,
                tokens_completion=20,
            )
        )
        s.commit()

        dentro_de_rango = resumen_uso_ia(s, date_from=dt.date(2026, 8, 10), date_to=dt.date(2026, 8, 20))

    assert dentro_de_rango[0]["tokens_prompt"] == 200


def test_resumen_uso_ia_mensual_agrupa_por_mes_y_modelo(session_factory):
    with session_factory() as s:
        for dia, modelo, tp, tc in [
            (dt.datetime(2026, 7, 5), "gpt-4o-mini", 100, 10),
            (dt.datetime(2026, 7, 20), "gpt-4o-mini", 50, 5),
            (dt.datetime(2026, 8, 3), "gpt-4o-mini", 200, 20),
            (dt.datetime(2026, 8, 4), "gpt-4o", 300, 30),
        ]:
            s.add(AIUsage(ocurrido_en=dia, modelo=modelo, tipo="clasificacion", tokens_prompt=tp, tokens_completion=tc))
        s.commit()

        por_mes = resumen_uso_ia_mensual(s)

    claves = {(f["mes"], f["modelo"]) for f in por_mes}
    assert claves == {("2026-07", "gpt-4o-mini"), ("2026-08", "gpt-4o-mini"), ("2026-08", "gpt-4o")}
    julio = next(f for f in por_mes if f["mes"] == "2026-07")
    assert julio["llamadas"] == 2
    assert julio["tokens_prompt"] == 150  # 100 + 50, las dos llamadas de julio


def test_guardar_analisis_registra_uso_automaticamente(session_factory):
    with session_factory() as s:
        conv = _crear_conversacion(s)
        s.commit()

        resultado = AnalysisResult(
            session_id=conv.session_id,
            categoria_final="INTERESADO",
            metodo="AI",
            senales={"x": True},
            modelo_ia="gpt-4o-mini",
            tokens_prompt=1234,
            tokens_completion=56,
        )
        guardar_analisis(s, resultado)
        s.commit()

        uso = s.execute(select(AIUsage)).scalar_one()

    assert uso.tokens_prompt == 1234
    assert uso.tokens_completion == 56
    assert uso.conversation_id == conv.id
    assert uso.tipo == "clasificacion"


def test_guardar_analisis_por_regla_no_registra_uso(session_factory):
    """Sin llamada a la IA (metodo=RULE), no debe crearse ningún renglón de uso."""
    with session_factory() as s:
        conv = _crear_conversacion(s)
        s.commit()

        resultado = AnalysisResult(
            session_id=conv.session_id, categoria_final="NO_INTERESADO", metodo="RULE", senales={}
        )
        guardar_analisis(s, resultado)
        s.commit()

        assert s.execute(select(AIUsage)).scalar_one_or_none() is None


def test_estimar_costo_usd_modelo_conocido():
    costo = estimar_costo_usd("gpt-4o-mini", tokens_prompt=1_000_000, tokens_completion=1_000_000)
    assert costo == pytest.approx(0.15 + 0.60)


def test_estimar_costo_usd_modelo_desconocido_es_none():
    assert estimar_costo_usd("modelo-inventado", 1000, 1000) is None
