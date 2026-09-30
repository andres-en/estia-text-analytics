from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from clasificador.analysis.analyzer import run_analysis
from clasificador.analysis.types import INTERESADO
from clasificador.db.engine import create_all_tables, create_db_engine, make_session_factory
from clasificador.db.models import Campana, Conversation, ConversationAnalysis, Import, Message


@pytest.fixture
def session_factory():
    engine = create_db_engine("sqlite:///:memory:")
    create_all_tables(engine)
    return make_session_factory(engine)


def test_run_analysis_usa_la_configuracion_de_cada_campana(session_factory):
    """Dos campañas en la misma base, cada una con su propio patrón de 'interés
    confirmado'. Cada conversación solo calza con el patrón de SU campaña — si el
    analizador mezclara las configs (ej. usara siempre la misma para las dos),
    al menos una de las dos quedaría mal clasificada."""
    with session_factory() as s:
        campana_custom = Campana(
            nombre_campana="Custom",
            configuracion={"rx_interes_confirmado": "confirmamos tu solicitud"},
        )
        campana_default = Campana(nombre_campana="Default")
        s.add_all([campana_custom, campana_default])
        s.flush()

        imp_custom = Import(
            file_name="a.xlsx", status="COMPLETED", started_at=dt.datetime.now(), campana_id=campana_custom.id_campana
        )
        imp_default = Import(
            file_name="b.xlsx", status="COMPLETED", started_at=dt.datetime.now(), campana_id=campana_default.id_campana
        )
        s.add_all([imp_custom, imp_default])
        s.flush()

        conv_custom = Conversation(
            session_id="s-custom",
            session_pattern="REAL",
            campana_id=campana_custom.id_campana,
            started_at=dt.datetime(2026, 8, 1, 9, 0),
            ended_at=dt.datetime(2026, 8, 1, 9, 30),
            message_count=2,
            conn_id_count=1,
            iniciada_por="CUSTOMER",
            first_import_id=imp_custom.id,
            last_import_id=imp_custom.id,
        )
        conv_default = Conversation(
            session_id="s-default",
            session_pattern="REAL",
            campana_id=campana_default.id_campana,
            started_at=dt.datetime(2026, 8, 1, 9, 0),
            ended_at=dt.datetime(2026, 8, 1, 9, 30),
            message_count=2,
            conn_id_count=1,
            iniciada_por="CUSTOMER",
            first_import_id=imp_default.id,
            last_import_id=imp_default.id,
        )
        s.add_all([conv_custom, conv_default])
        s.flush()

        mensajes = [
            (conv_custom, imp_custom, [("CUSTOMER", "Si"), ("BOT", "Confirmamos tu solicitud, gracias")]),
            (conv_default, imp_default, [("CUSTOMER", "Si"), ("BOT", "Hemos registrado tu interes")]),
        ]
        for conv, imp, pares in mensajes:
            for j, (sender, texto) in enumerate(pares, start=1):
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
                        dedup_hash=f"{conv.session_id}-{j}",
                    )
                )
        s.commit()

    report = run_analysis(session_factory, ai_client=None)
    assert report.total_evaluadas == 2
    assert report.resueltas_por_regla == 2

    with session_factory() as s:
        cat_custom = s.execute(
            select(ConversationAnalysis.categoria_final).join(Conversation).where(Conversation.session_id == "s-custom")
        ).scalar_one()
        cat_default = s.execute(
            select(ConversationAnalysis.categoria_final)
            .join(Conversation)
            .where(Conversation.session_id == "s-default")
        ).scalar_one()

    # Cada una solo calza con el regex de SU campaña — si el analizador
    # aplicara la config equivocada a cualquiera de las dos, esa quedaría
    # como NO_INTERESADO en vez de INTERESADO.
    assert cat_custom == INTERESADO
    assert cat_default == INTERESADO
