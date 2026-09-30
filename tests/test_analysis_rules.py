from __future__ import annotations

import datetime as dt

from clasificador.analysis.rules import clasificar_por_reglas, derive_categoria
from clasificador.analysis.types import (
    INTERESADO,
    NO_INTERESADO,
    RESOLVIO_DUDAS,
    SIN_RESPUESTA,
    AnalysisFlags,
)
from clasificador.conversation_view import ConversationTranscript, TranscriptMessage

T0 = dt.datetime(2026, 8, 1, 9, 0, 0)


def _msg(sender, texto, i=1):
    return TranscriptMessage(
        sequence_number=i,
        timestamp=T0,
        sender=sender,
        sender_label=sender,
        message_type="TEXT",
        message=texto,
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


# --- Capa 0 ------------------------------------------------------------------


def test_sin_mensajes_del_cliente_es_sin_respuesta():
    t = _transcript(("BOT", "👋 Hola, tienes un cupo disponible de $4.775.000"))
    r = clasificar_por_reglas(t)
    assert r.categoria == SIN_RESPUESTA
    assert r.requiere_ia is False
    assert r.regla_aplicada == "sin_mensajes_cliente"


# --- Capa 1: interés ---------------------------------------------------------


def test_boton_quiero_usar_mi_cupo_solo_no_es_interesado():
    # Declarar intención NO es adquirir el cupo: sin texto libre ni confirmación,
    # la conversación no llegó a nada.
    t = _transcript(("CUSTOMER", "Quiero usar mi cupo"), ("BOT", "¡Qué buena noticia!"))
    r = clasificar_por_reglas(t)
    assert r.categoria == NO_INTERESADO
    assert r.flags.interes_declarado is True  # se conserva como señal informativa
    assert r.flags.interes_confirmado is False
    assert r.requiere_ia is False


def test_bot_confirma_interes_es_la_unica_via_a_interesado():
    t = _transcript(
        ("CUSTOMER", "Sí"),
        ("BOT", "✅ Hemos registrado tu interés. 📌 Categoría: *Motos*"),
    )
    r = clasificar_por_reglas(t)
    assert r.categoria == INTERESADO
    assert r.flags.interes_confirmado is True
    assert r.regla_aplicada == "interes_confirmado_por_bot"


def test_interes_confirmado_gana_por_jerarquia_y_evita_llamar_a_la_ia():
    t = _transcript(
        ("CUSTOMER", "Cuanto es mi cupo"),
        ("BOT", "✅ Hemos registrado tu interés."),
    )
    r = clasificar_por_reglas(t)
    assert r.categoria == INTERESADO
    assert r.requiere_ia is False


def test_boton_de_interes_con_texto_libre_va_a_la_ia():
    # Pulsó el botón pero no concretó: hay que averiguar si preguntó algo.
    t = _transcript(
        ("CUSTOMER", "Quiero usar mi cupo"),
        ("BOT", "¿Qué producto buscas?"),
        ("CUSTOMER", "Cuanto es mi cupo"),
    )
    r = clasificar_por_reglas(t)
    assert r.requiere_ia is True
    assert r.categoria is None


# --- Autorespondedores de empresas -------------------------------------------


def test_autorespondedor_de_empresa_es_no_interesado_por_regla():
    # El número de la campaña pertenece a un negocio: su respuesta automática
    # contiene "¿Cómo podemos ayudarte?", que no es una pregunta de un cliente.
    t = _transcript(
        ("CUSTOMER", "Gracias por comunicarte con Consultorio Dental Sonrisas. ¿Cómo podemos ayudarte?"),
        ("BOT", "¡Hola! Soy tu asesor digital de Acme..."),
    )
    r = clasificar_por_reglas(t)
    assert r.categoria == NO_INTERESADO
    assert r.flags.es_autorespondedor is True
    assert r.regla_aplicada == "autorespondedor_de_empresa"
    assert r.requiere_ia is False


def test_autorespondedor_con_bienvenida_de_otro_negocio():
    t = _transcript(
        ("CUSTOMER", "Hola! Bienvenid@ a Ferretería El Tornillo . ¿Como podemos ayudarte?"),
        ("BOT", "¡Hola! Soy tu asesor digital de Acme..."),
    )
    r = clasificar_por_reglas(t)
    assert r.flags.es_autorespondedor is True
    assert r.categoria == NO_INTERESADO


def test_autorespondedor_seguido_de_persona_real_va_a_la_ia():
    # Caso real: la empresa autorresponde, pero después una persona sigue escribiendo
    # y sí hace consultas. No se puede cortar por regla: debe evaluarlo la IA.
    t = _transcript(
        ("CUSTOMER", "Gracias por comunicarte con nosotros. ¿Cómo podemos ayudarte?"),
        ("BOT", "¡Hola! Soy tu asesor digital de Acme..."),
        ("CUSTOMER", "Me pueden compartir el catálogo"),
        ("BOT", "Claro, con estos aliados..."),
        ("CUSTOMER", "Se puede un avance en efectivo"),
    )
    r = clasificar_por_reglas(t)
    assert r.flags.es_autorespondedor is True  # el contacto sigue marcado
    assert r.requiere_ia is True  # pero no se clasifica por regla
    assert r.categoria is None


# --- Capa 2: rechazo ---------------------------------------------------------


def test_boton_no_estoy_interesado_solo_es_no_interesado():
    t = _transcript(
        ("CUSTOMER", "No estoy interesado"),
        ("BOT", "Lamentamos que por ahora no desees utilizar tu cupo Acme..."),
    )
    r = clasificar_por_reglas(t)
    assert r.categoria == NO_INTERESADO
    assert r.flags.rechazo_explicito is True
    assert r.requiere_ia is False


def test_digito_de_encuesta_no_manda_a_la_ia():
    # El '1' responde la encuesta de motivos del bot: es parte del rechazo,
    # no una pregunta ni texto libre.
    t = _transcript(
        ("CUSTOMER", "No estoy interesado"),
        ("BOT", "Lamentamos que por ahora no desees... 1️⃣ No necesito comprar..."),
        ("CUSTOMER", "1"),
    )
    r = clasificar_por_reglas(t)
    assert r.categoria == NO_INTERESADO
    assert r.requiere_ia is False


def test_cortesias_no_mandan_a_la_ia():
    t = _transcript(
        ("CUSTOMER", "No estoy interesado"),
        ("BOT", "Lamentamos que por ahora no desees..."),
        ("CUSTOMER", "Gracias"),
    )
    r = clasificar_por_reglas(t)
    assert r.categoria == NO_INTERESADO
    assert r.requiere_ia is False


def test_rechazo_con_texto_libre_si_va_a_la_ia():
    # Rechazó, pero antes escribió algo que podría ser una pregunta:
    # por la jerarquía podría corresponder RESOLVIO_DUDAS, así que decide la IA.
    t = _transcript(
        ("CUSTOMER", "Que intereses manejan"),
        ("BOT", "La tasa es variable..."),
        ("CUSTOMER", "No estoy interesado"),
    )
    r = clasificar_por_reglas(t)
    assert r.categoria is None
    assert r.requiere_ia is True
    assert r.flags.rechazo_explicito is True  # la señal ya viene detectada


# --- Capa 3: zona gris -------------------------------------------------------


def test_texto_libre_sin_senal_requiere_ia():
    t = _transcript(("CUSTOMER", "Los intereses"), ("BOT", "Los intereses de tu crédito..."))
    r = clasificar_por_reglas(t)
    assert r.requiere_ia is True
    assert r.categoria is None


def test_bot_no_resolvio_se_detecta_por_regla():
    t = _transcript(
        ("CUSTOMER", "Donde queda la sede"),
        ("BOT", "En este momento no cuento con información de sedes ni horarios."),
    )
    r = clasificar_por_reglas(t)
    assert r.flags.bot_no_resolvio is True


# --- Jerarquía ---------------------------------------------------------------


def test_jerarquia_interes_confirmado_vence_a_preguntas_y_rechazo():
    f = AnalysisFlags(interes_confirmado=True, busco_informacion=True, rechazo_explicito=True)
    assert derive_categoria(f, tiene_respuesta_cliente=True) == INTERESADO


def test_interes_solo_declarado_no_basta_para_interesado():
    # Declaró intención y preguntó, pero no concretó: es RESOLVIO_DUDAS.
    f = AnalysisFlags(interes_declarado=True, busco_informacion=True)
    assert derive_categoria(f, tiene_respuesta_cliente=True) == RESOLVIO_DUDAS


def test_jerarquia_preguntas_vence_a_rechazo():
    f = AnalysisFlags(busco_informacion=True, rechazo_explicito=True)
    assert derive_categoria(f, tiene_respuesta_cliente=True) == RESOLVIO_DUDAS


def test_jerarquia_solo_rechazo():
    f = AnalysisFlags(rechazo_explicito=True)
    assert derive_categoria(f, tiene_respuesta_cliente=True) == NO_INTERESADO


def test_sin_respuesta_gana_sobre_todo():
    assert derive_categoria(AnalysisFlags(), tiene_respuesta_cliente=False) == SIN_RESPUESTA


def test_respondio_pero_sin_ninguna_senal_es_no_interesado():
    # Decisión tomada tras la validación manual: no se fuerza una categoría aparte.
    assert derive_categoria(AnalysisFlags(), tiene_respuesta_cliente=True) == NO_INTERESADO


# --- Combinación de señales reglas + IA --------------------------------------


def test_merge_es_or_logico_y_la_ia_no_puede_apagar_una_regla():
    regla = AnalysisFlags(rechazo_explicito=True)
    ia = AnalysisFlags(busco_informacion=True, rechazo_explicito=False)
    combinado = regla.merge(ia)
    assert combinado.rechazo_explicito is True  # la regla se mantiene
    assert combinado.busco_informacion is True  # la IA aporta lo suyo
