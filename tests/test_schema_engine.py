from __future__ import annotations

import datetime as dt

import pytest

from clasificador.analysis.rules import clasificar_por_reglas
from clasificador.analysis.rules_config import DEFAULT_COMPILED_RULES
from clasificador.analysis.schema import (
    DEFAULT_ESQUEMA,
    CategoriaDef,
    CondicionIndicador,
    EsquemaClasificacion,
    IndicadorDef,
    ReglaDecision,
)
from clasificador.analysis.schema_engine import clasificar_por_esquema, compilar_esquema
from clasificador.conversation_view import ConversationTranscript, TranscriptMessage

T0 = dt.datetime(2026, 8, 1, 9, 0, 0)


def _msg(sender, texto, i=1):
    return TranscriptMessage(
        sequence_number=i, timestamp=T0, sender=sender, sender_label=sender, message_type="TEXT", message=texto
    )


def _transcript(*pares):
    msgs = [_msg(s, t, i) for i, (s, t) in enumerate(pares, start=1)]
    return ConversationTranscript(
        session_id="sid-test",
        customer_phone="573000000000",
        customer_name="Prueba",
        started_at=T0,
        ended_at=T0,
        conn_id_count=1,
        messages=msgs,
    )


# Mismos casos que tests/test_analysis_rules.py — el motor genérico con
# DEFAULT_ESQUEMA debe llegar exactamente a la misma categoría/requiere_ia que
# el motor hardcodeado, conversación por conversación.
CASOS = [
    _transcript(("BOT", "👋 Hola, tienes un cupo disponible de $4.775.000")),
    _transcript(("CUSTOMER", "Quiero usar mi cupo"), ("BOT", "¡Qué buena noticia!")),
    _transcript(("CUSTOMER", "Sí"), ("BOT", "✅ Hemos registrado tu interés. 📌 Categoría: *Motos*")),
    _transcript(("CUSTOMER", "Cuanto es mi cupo"), ("BOT", "✅ Hemos registrado tu interés.")),
    _transcript(
        ("CUSTOMER", "Quiero usar mi cupo"), ("BOT", "¿Qué producto buscas?"), ("CUSTOMER", "Cuanto es mi cupo")
    ),
    _transcript(
        ("CUSTOMER", "Gracias por comunicarte con Consultorio Dental Sonrisas. ¿Cómo podemos ayudarte?"),
        ("BOT", "¡Hola! Soy tu asesor digital de Acme..."),
    ),
    _transcript(
        ("CUSTOMER", "Gracias por comunicarte con nosotros. ¿Cómo podemos ayudarte?"),
        ("BOT", "¡Hola! Soy tu asesor digital de Acme..."),
        ("CUSTOMER", "Me pueden compartir el catálogo"),
        ("BOT", "Claro, con estos aliados..."),
        ("CUSTOMER", "Se puede un avance en efectivo"),
    ),
    _transcript(
        ("CUSTOMER", "No estoy interesado"), ("BOT", "Lamentamos que por ahora no desees utilizar tu cupo Acme...")
    ),
    _transcript(
        ("CUSTOMER", "No estoy interesado"),
        ("BOT", "Lamentamos que por ahora no desees... 1️⃣ No necesito comprar..."),
        ("CUSTOMER", "1"),
    ),
    _transcript(
        ("CUSTOMER", "No estoy interesado"), ("BOT", "Lamentamos que por ahora no desees..."), ("CUSTOMER", "Gracias")
    ),
    _transcript(
        ("CUSTOMER", "Que intereses manejan"), ("BOT", "La tasa es variable..."), ("CUSTOMER", "No estoy interesado")
    ),
    _transcript(("CUSTOMER", "Los intereses"), ("BOT", "Los intereses de tu crédito...")),
    _transcript(
        ("CUSTOMER", "Donde queda la sede"), ("BOT", "En este momento no cuento con información de sedes ni horarios.")
    ),
]


@pytest.mark.parametrize("transcript", CASOS, ids=[t.session_id + str(i) for i, t in enumerate(CASOS)])
def test_motor_generico_con_default_esquema_equivale_al_motor_hardcodeado(transcript):
    esperado = clasificar_por_reglas(transcript)
    compilado = compilar_esquema(DEFAULT_ESQUEMA)
    obtenido = clasificar_por_esquema(transcript, compilado, DEFAULT_COMPILED_RULES)

    assert obtenido.categoria == esperado.categoria
    assert obtenido.requiere_ia == esperado.requiere_ia
    assert obtenido.tiene_respuesta_cliente == esperado.tiene_respuesta_cliente
    for nombre in ("interes_confirmado", "rechazo_explicito", "bot_no_resolvio", "es_autorespondedor"):
        assert obtenido.senales.get(nombre, False) == getattr(esperado.flags, nombre), nombre


def test_default_esquema_es_valido():
    assert DEFAULT_ESQUEMA.validar() is None


def test_validar_detecta_categoria_repetida():
    esquema = EsquemaClasificacion(
        categorias=(CategoriaDef("A", "A"), CategoriaDef("A", "A duplicada")),
        indicadores=(IndicadorDef("x", "X", "ia", descripcion_ia="algo"),),
        arbol_decision=(ReglaDecision({}, "A"),),
        categoria_sin_respuesta="A",
    )
    assert esquema.validar() is not None


def test_validar_detecta_regex_invalido():
    esquema = EsquemaClasificacion(
        categorias=(CategoriaDef("A", "A"),),
        indicadores=(IndicadorDef("x", "X", "regla", condiciones=(CondicionIndicador("regex_bot", "(sin cerrar"),)),),
        arbol_decision=(ReglaDecision({}, "A"),),
        categoria_sin_respuesta="A",
    )
    assert esquema.validar() is not None


def test_validar_detecta_arbol_referencia_categoria_no_declarada():
    esquema = EsquemaClasificacion(
        categorias=(CategoriaDef("A", "A"),),
        indicadores=(IndicadorDef("x", "X", "ia", descripcion_ia="algo"),),
        arbol_decision=(ReglaDecision({}, "NO_EXISTE"),),
        categoria_sin_respuesta="A",
    )
    assert esquema.validar() is not None


def test_validar_detecta_arbol_referencia_indicador_no_declarado():
    esquema = EsquemaClasificacion(
        categorias=(CategoriaDef("A", "A"),),
        indicadores=(IndicadorDef("x", "X", "ia", descripcion_ia="algo"),),
        arbol_decision=(ReglaDecision({"no_declarado": True}, "A"),),
        categoria_sin_respuesta="A",
    )
    assert esquema.validar() is not None


def test_from_json_none_no_hay_esquema():
    assert EsquemaClasificacion.from_json(None) is None
    assert EsquemaClasificacion.from_json({}) is None


def test_to_json_from_json_roundtrip():
    restaurado = EsquemaClasificacion.from_json(DEFAULT_ESQUEMA.to_json())
    assert restaurado == DEFAULT_ESQUEMA


def test_esquema_totalmente_custom_clasifica_con_su_propia_categoria():
    """Una campaña ajena a Acme (ej. venta de un curso online) con categorías
    e indicadores propios, sin ninguna relación con las 5 de Acme."""
    esquema = EsquemaClasificacion(
        categorias=(
            CategoriaDef("MATRICULADO", "Se matriculó"),
            CategoriaDef("DUDA", "Preguntó y no matriculó"),
            CategoriaDef("IGNORO", "No respondió con interés"),
        ),
        indicadores=(
            IndicadorDef(
                "confirmo_pago",
                "Confirmó el pago",
                "regla",
                condiciones=(CondicionIndicador("regex_bot", r"tu matr.cula qued. confirmada"),),
            ),
            IndicadorDef(
                "pregunto_precio",
                "Preguntó el precio",
                "ia",
                descripcion_ia="El cliente preguntó cuánto cuesta el curso",
            ),
        ),
        arbol_decision=(
            ReglaDecision({"confirmo_pago": True}, "MATRICULADO"),
            ReglaDecision({"pregunto_precio": True}, "DUDA"),
            ReglaDecision({}, "IGNORO"),
        ),
        categoria_sin_respuesta="IGNORO",
    )
    compilado = compilar_esquema(esquema)

    t = _transcript(("CUSTOMER", "Listo, ya pagué"), ("BOT", "¡Tu matrícula quedó confirmada!"))
    outcome = clasificar_por_esquema(t, compilado, DEFAULT_COMPILED_RULES)
    assert outcome.categoria == "MATRICULADO"
    assert outcome.requiere_ia is False  # confirmo_pago ya resuelve el árbol sin importar pregunto_precio

    t2 = _transcript(("CUSTOMER", "Cuanto cuesta el curso"), ("BOT", "Cuesta $200.000"))
    outcome2 = clasificar_por_esquema(t2, compilado, DEFAULT_COMPILED_RULES)
    assert outcome2.categoria is None
    assert outcome2.requiere_ia is True


def test_esquema_sin_indicadores_ia_nunca_deja_categoria_en_none():
    """Bug real visto en producción: un esquema de cobranza (ej. ACME_COBRANZA)
    con TODOS sus indicadores de tipo "regla" (ids_ia vacío). Un mensaje del
    cliente que no calza con ningún regex es "texto residual" que nadie puede
    interpretar (no hay ningún indicador IA al que consultarle) — antes eso
    devolvía categoria=None (violaba el NOT NULL de categoria_final en MySQL),
    ahora debe resolver el árbol con las señales de reglas tal cual, igual que
    si no hubiera texto residual."""
    esquema = EsquemaClasificacion(
        categorias=(
            CategoriaDef("PAGO_REALIZADO", "Pago realizado"),
            CategoriaDef("NO_APLICA", "No aplica ninguna de las anteriores"),
        ),
        indicadores=(
            IndicadorDef(
                "IND_PAGO_REALIZADO",
                "Pago ya realizado",
                "regla",
                condiciones=(CondicionIndicador("regex_customer", r"ya pague"),),
            ),
        ),
        arbol_decision=(
            ReglaDecision({"IND_PAGO_REALIZADO": True}, "PAGO_REALIZADO"),
            ReglaDecision({}, "NO_APLICA"),
        ),
        categoria_sin_respuesta="NO_APLICA",
    )
    compilado = compilar_esquema(esquema)

    # Texto libre que no calza con IND_PAGO_REALIZADO ni con ningún otro regex.
    t = _transcript(("CUSTOMER", "no tengo plata para pagar esa deuda ahora mismo"))
    outcome = clasificar_por_esquema(t, compilado, DEFAULT_COMPILED_RULES)
    assert outcome.categoria == "NO_APLICA"
    assert outcome.requiere_ia is False
