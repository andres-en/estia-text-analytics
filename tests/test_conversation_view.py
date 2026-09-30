from __future__ import annotations

import datetime as dt

import pytest

from clasificador.conversation_view import (
    business_indicators,
    categorias_disponibles,
    category_counts,
    category_counts_trend,
    daily_category_trend,
    list_conversations,
    method_counts,
)
from clasificador.db.engine import create_all_tables, create_db_engine, make_session_factory
from clasificador.db.models import Campana, Conversation, ConversationAnalysis, Import


@pytest.fixture
def session_factory():
    engine = create_db_engine("sqlite:///:memory:")
    create_all_tables(engine)
    return make_session_factory(engine)


def _seed(session_factory):
    """3 conversaciones: una INTERESADO (01/08), una NO_INTERESADO (01/08),
    una RESOLVIO_DUDAS (02/08); más una cuarta sin analizar."""
    with session_factory() as s:
        imp = Import(file_name="t.xlsx", status="COMPLETED", started_at=dt.datetime.now())
        s.add(imp)
        s.flush()

        datos = [
            ("s-interes", dt.datetime(2026, 8, 1, 9, 0), "573000000001", "INTERESADO", "RULE"),
            ("s-no-interes", dt.datetime(2026, 8, 1, 10, 0), "573000000002", "NO_INTERESADO", "RULE"),
            ("s-dudas", dt.datetime(2026, 8, 2, 9, 0), "573000000003", "RESOLVIO_DUDAS", "AI"),
        ]
        for sid, started, phone, categoria, metodo in datos:
            conv = Conversation(
                session_id=sid,
                session_pattern="REAL",
                customer_phone=phone,
                started_at=started,
                ended_at=started,
                message_count=2,
                conn_id_count=1,
                iniciada_por="CUSTOMER",
                first_import_id=imp.id,
                last_import_id=imp.id,
            )
            s.add(conv)
            s.flush()
            s.add(
                ConversationAnalysis(
                    conversation_id=conv.id,
                    categoria_final=categoria,
                    interes_confirmado=(categoria == "INTERESADO"),
                    interes_declarado=(categoria == "INTERESADO"),
                    busco_informacion=(categoria == "RESOLVIO_DUDAS"),
                    rechazo_explicito=(categoria == "NO_INTERESADO"),
                    bot_no_resolvio=False,
                    es_autorespondedor=False,
                    metodo=metodo,
                    analyzed_at=dt.datetime.now(),
                )
            )

        conv_sin_analizar = Conversation(
            session_id="s-sin-analizar",
            session_pattern="REAL",
            customer_phone="573000000004",
            started_at=dt.datetime(2026, 8, 1, 11, 0),
            ended_at=dt.datetime(2026, 8, 1, 11, 0),
            message_count=1,
            conn_id_count=1,
            iniciada_por="CUSTOMER",
            first_import_id=imp.id,
            last_import_id=imp.id,
        )
        s.add(conv_sin_analizar)
        s.commit()


def test_list_conversations_filters_by_categoria(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        items, total = list_conversations(s, categorias=["INTERESADO"])
    assert total == 1
    assert items[0].session_id == "s-interes"


def test_list_conversations_categoria_sin_analizar(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        items, total = list_conversations(s, categorias=["SIN_ANALIZAR"])
    assert total == 1
    assert items[0].session_id == "s-sin-analizar"
    assert items[0].categoria is None


def test_list_conversations_combines_categoria_and_sin_analizar(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        items, total = list_conversations(s, categorias=["INTERESADO", "SIN_ANALIZAR"])
    assert total == 2
    assert {i.session_id for i in items} == {"s-interes", "s-sin-analizar"}


def test_list_conversations_date_range(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        items, total = list_conversations(s, date_from=dt.date(2026, 8, 2), date_to=dt.date(2026, 8, 2))
    assert total == 1
    assert items[0].session_id == "s-dudas"


def test_list_conversations_pagination(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        page1, total = list_conversations(s, page=1, page_size=2)
        page2, _ = list_conversations(s, page=2, page_size=2)
    assert total == 4
    assert len(page1) == 2
    assert len(page2) == 2
    assert {c.session_id for c in page1}.isdisjoint({c.session_id for c in page2})


def test_category_counts(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        counts = category_counts(s)
    assert counts == {"INTERESADO": 1, "NO_INTERESADO": 1, "RESOLVIO_DUDAS": 1, "SIN_ANALIZAR": 1}


def test_category_counts_with_date_range(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        counts = category_counts(s, date_from=dt.date(2026, 8, 2))
    assert counts == {"RESOLVIO_DUDAS": 1}


def test_method_counts(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        counts = method_counts(s)
    assert counts == {"RULE": 2, "AI": 1}


def test_business_indicators(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        indicators = business_indicators(s)
    assert indicators["interesados_confirmados"] == 1
    assert indicators["rechazos_explicitos"] == 1
    assert indicators["autorespondedores"] == 0


def test_daily_category_trend(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        trend = daily_category_trend(s)
    dias = {(t["fecha"], t["categoria"]): t["cantidad"] for t in trend}
    assert dias[("2026-08-01", "INTERESADO")] == 1
    assert dias[("2026-08-01", "NO_INTERESADO")] == 1
    assert dias[("2026-08-02", "RESOLVIO_DUDAS")] == 1


def test_category_counts_trend_misma_forma_que_business_indicators_trend(session_factory):
    _seed(session_factory)
    with session_factory() as s:
        # Ventana explícita (no la de "últimos 30 días desde hoy" por defecto):
        # las conversaciones de prueba están fechadas en 2026-08, así que sin
        # esto el resultado dependería de qué día es "hoy" al correr el test.
        trend = category_counts_trend(s, date_from=dt.date(2026, 8, 1), date_to=dt.date(2026, 8, 2))
    assert set(trend.keys()) == {"current", "previous"}
    assert trend["current"]["INTERESADO"] == 1
    assert trend["current"]["RESOLVIO_DUDAS"] == 1
    assert trend["previous"] == {}


def test_categorias_disponibles_sin_campanas_usa_default_esquema(session_factory):
    with session_factory() as s:
        categorias = categorias_disponibles(s)
    ids = [c["id"] for c in categorias]
    assert "INTERESADO" in ids
    assert "RESOLVIO_DUDAS" in ids
    assert "NO_INTERESADO" in ids
    assert ids[-1] == "SIN_ANALIZAR"  # siempre al final


def test_categorias_disponibles_une_esquemas_de_varias_campanas(session_factory):
    with session_factory() as s:
        s.add_all(
            [
                Campana(
                    nombre_campana="Custom",
                    configuracion={
                        "esquema_clasificacion": {
                            "categorias": [{"id": "MATRICULADO", "label": "Se matriculó", "color": "#111"}],
                            "indicadores": [{"id": "x", "label": "X", "tipo": "ia", "descripcion_ia": "algo"}],
                            "arbol_decision": [{"condicion": {}, "categoria": "MATRICULADO"}],
                            "categoria_sin_respuesta": "MATRICULADO",
                        }
                    },
                ),
                Campana(nombre_campana="Acme"),  # sin esquema propio -> usa el default
            ]
        )
        s.commit()
        categorias = categorias_disponibles(s)
    ids = {c["id"] for c in categorias}
    assert "MATRICULADO" in ids  # de la campaña custom
    assert "INTERESADO" in ids  # de la campaña sin esquema (default)
    assert "SIN_ANALIZAR" in ids


def test_list_conversations_resuelve_categoria_label_de_esquema_propio(session_factory):
    with session_factory() as s:
        campana = Campana(
            nombre_campana="Custom",
            configuracion={
                "esquema_clasificacion": {
                    "categorias": [{"id": "MATRICULADO", "label": "Se matriculó de verdad"}],
                    "indicadores": [{"id": "x", "label": "X", "tipo": "ia", "descripcion_ia": "algo"}],
                    "arbol_decision": [{"condicion": {}, "categoria": "MATRICULADO"}],
                    "categoria_sin_respuesta": "MATRICULADO",
                }
            },
        )
        s.add(campana)
        s.flush()
        imp = Import(
            file_name="t.xlsx", status="COMPLETED", started_at=dt.datetime.now(), campana_id=campana.id_campana
        )
        s.add(imp)
        s.flush()
        conv = Conversation(
            session_id="s-custom",
            session_pattern="REAL",
            campana_id=campana.id_campana,
            started_at=dt.datetime(2026, 8, 1, 9, 0),
            ended_at=dt.datetime(2026, 8, 1, 9, 0),
            message_count=1,
            conn_id_count=1,
            iniciada_por="CUSTOMER",
            first_import_id=imp.id,
            last_import_id=imp.id,
        )
        s.add(conv)
        s.flush()
        s.add(
            ConversationAnalysis(
                conversation_id=conv.id,
                categoria_final="MATRICULADO",
                metodo="AI",
                senales={"x": True},
                analyzed_at=dt.datetime.now(),
            )
        )
        s.commit()

        items, _ = list_conversations(s, categorias=["MATRICULADO"])
    assert items[0].categoria_label == "Se matriculó de verdad"


def test_get_transcript_indicadores_de_esquema_propio(session_factory):
    from clasificador.conversation_view import get_transcript

    with session_factory() as s:
        campana = Campana(
            nombre_campana="Custom",
            configuracion={
                "esquema_clasificacion": {
                    "categorias": [{"id": "MATRICULADO", "label": "Se matriculó"}],
                    "indicadores": [
                        {"id": "pregunto_precio", "label": "Preguntó el precio", "tipo": "ia", "descripcion_ia": "algo"}
                    ],
                    "arbol_decision": [{"condicion": {}, "categoria": "MATRICULADO"}],
                    "categoria_sin_respuesta": "MATRICULADO",
                }
            },
        )
        s.add(campana)
        s.flush()
        imp = Import(
            file_name="t.xlsx", status="COMPLETED", started_at=dt.datetime.now(), campana_id=campana.id_campana
        )
        s.add(imp)
        s.flush()
        conv = Conversation(
            session_id="s-indicadores",
            session_pattern="REAL",
            campana_id=campana.id_campana,
            started_at=dt.datetime(2026, 8, 1, 9, 0),
            ended_at=dt.datetime(2026, 8, 1, 9, 0),
            message_count=1,
            conn_id_count=1,
            iniciada_por="CUSTOMER",
            first_import_id=imp.id,
            last_import_id=imp.id,
        )
        s.add(conv)
        s.flush()
        s.add(
            ConversationAnalysis(
                conversation_id=conv.id,
                categoria_final="MATRICULADO",
                metodo="AI",
                senales={"pregunto_precio": True},
                analyzed_at=dt.datetime.now(),
            )
        )
        s.commit()

        transcript = get_transcript(s, "s-indicadores")

    assert transcript.indicadores == ({"id": "pregunto_precio", "label": "Preguntó el precio", "valor": True},)


def test_get_transcript_indicadores_respaldo_en_columnas_legadas(session_factory):
    """Análisis guardados antes de que existiera la columna `senales` (NULL) se
    siguen mostrando bien — vía las 6 columnas booleanas legadas."""
    from clasificador.conversation_view import get_transcript

    with session_factory() as s:
        imp = Import(file_name="t.xlsx", status="COMPLETED", started_at=dt.datetime.now())
        s.add(imp)
        s.flush()
        conv = Conversation(
            session_id="s-legado",
            session_pattern="REAL",
            started_at=dt.datetime(2026, 8, 1, 9, 0),
            ended_at=dt.datetime(2026, 8, 1, 9, 0),
            message_count=1,
            conn_id_count=1,
            iniciada_por="CUSTOMER",
            first_import_id=imp.id,
            last_import_id=imp.id,
        )
        s.add(conv)
        s.flush()
        s.add(
            ConversationAnalysis(
                conversation_id=conv.id,
                categoria_final="INTERESADO",
                metodo="RULE",
                interes_confirmado=True,
                senales=None,
                analyzed_at=dt.datetime.now(),
            )
        )
        s.commit()

        transcript = get_transcript(s, "s-legado")

    valores = {i["id"]: i["valor"] for i in transcript.indicadores}
    assert valores["interes_confirmado"] is True
    assert valores["busco_informacion"] is False
