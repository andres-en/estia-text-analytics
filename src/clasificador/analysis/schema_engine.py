from __future__ import annotations

import dataclasses
import itertools
import re

from ..conversation_view import ConversationTranscript
from .rules_config import CompiledRules, normalizar
from .schema import EsquemaClasificacion


@dataclasses.dataclass(frozen=True)
class _IndicadorCompilado:
    id: str
    tipo: str
    # cada condición ya resuelta a (tipo, patrón_compilado_o_texto_normalizado)
    condiciones: tuple[tuple[str, re.Pattern[str] | str], ...]


@dataclasses.dataclass(frozen=True)
class EsquemaCompilado:
    """`EsquemaClasificacion` con los regex pre-compilados y los botones
    normalizados una sola vez — se arma una vez por campaña, no por conversación."""

    esquema: EsquemaClasificacion
    _indicadores: tuple[_IndicadorCompilado, ...]
    _regex_customer: tuple[tuple[str, re.Pattern[str]], ...]  # (indicador_id, patrón)


def compilar_esquema(esquema: EsquemaClasificacion) -> EsquemaCompilado:
    indicadores = []
    regex_customer = []
    for ind in esquema.indicadores:
        condiciones = []
        for c in ind.condiciones:
            if c.tipo == "boton":
                condiciones.append((c.tipo, normalizar(c.patron)))
            else:
                patron = re.compile(c.patron, re.IGNORECASE)
                condiciones.append((c.tipo, patron))
                if c.tipo == "regex_customer":
                    regex_customer.append((ind.id, patron))
        indicadores.append(_IndicadorCompilado(id=ind.id, tipo=ind.tipo, condiciones=tuple(condiciones)))
    return EsquemaCompilado(
        esquema=esquema,
        _indicadores=tuple(indicadores),
        _regex_customer=tuple(regex_customer),
    )


@dataclasses.dataclass(frozen=True)
class EsquemaOutcome:
    senales: dict[str, bool]
    categoria: str | None  # None => indeterminado, pasa a IA
    requiere_ia: bool
    tiene_respuesta_cliente: bool
    subcategoria: str | None = None


def _detectar_senales_regla(transcript: ConversationTranscript, compilado: EsquemaCompilado) -> dict[str, bool]:
    bot_textos = [m.message for m in transcript.messages if m.sender == "BOT"]
    cliente_msgs = [m for m in transcript.messages if m.sender == "CUSTOMER"]
    cliente_textos = [m.message for m in cliente_msgs]
    cliente_textos_norm = {normalizar(m.message) for m in cliente_msgs}

    senales: dict[str, bool] = {}
    for ind in compilado._indicadores:
        if ind.tipo != "regla":
            continue
        cumple = False
        for tipo, patron in ind.condiciones:
            if tipo == "regex_bot":
                cumple = any(patron.search(t) for t in bot_textos)
            elif tipo == "regex_customer":
                cumple = any(patron.search(t) for t in cliente_textos)
            elif tipo == "boton":
                cumple = patron in cliente_textos_norm
            if cumple:
                break
        senales[ind.id] = cumple
    return senales


def _mensaje_explicado_por_regla(mensaje: str, compilado: EsquemaCompilado) -> bool:
    """True si el texto del cliente coincide con ALGÚN indicador de tipo 'regla'
    con una condición `regex_customer` — señal de que ese mensaje ya está
    explicado por una regla (ej. autorespondedor de empresa) y no aporta texto
    libre que interpretar."""
    return any(patron.search(mensaje) for _, patron in compilado._regex_customer)


def resolver_arbol(senales: dict[str, bool], esquema: EsquemaClasificacion) -> str:
    for regla in esquema.arbol_decision:
        if all(senales.get(k, False) == v for k, v in regla.condicion.items()):
            return regla.categoria
    # Red de seguridad si el árbol no cubre el caso (no debería pasar si
    # `validar()` se corrió antes de guardar el esquema).
    return esquema.arbol_decision[-1].categoria if esquema.arbol_decision else esquema.categorias[-1].id


def resolver_subcategoria(senales: dict[str, bool], esquema: EsquemaClasificacion) -> str | None:
    """Primera regla de `arbol_subcategoria` que calza; `None` si el esquema no
    define subcategorías o ninguna calza (no hay red de seguridad: la última
    regla debería ser un catch-all `{}`, ver `EsquemaClasificacion.validar`)."""
    for regla in esquema.arbol_subcategoria:
        if all(senales.get(k, False) == v for k, v in regla.condicion.items()):
            return regla.categoria
    return None


def resolver_clasificacion(senales: dict[str, bool], esquema: EsquemaClasificacion) -> tuple[str, str | None]:
    """(categoría, subcategoría) para un set de señales. La subcategoría solo se
    calcula para las categorías de `subcategoria_aplica_a`."""
    categoria = resolver_arbol(senales, esquema)
    if esquema.arbol_subcategoria and categoria in esquema.subcategoria_aplica_a:
        return categoria, resolver_subcategoria(senales, esquema)
    return categoria, None


def clasificar_por_esquema(
    transcript: ConversationTranscript,
    compilado: EsquemaCompilado,
    rules: CompiledRules,
) -> EsquemaOutcome:
    """Cascada reglas → IA sobre un esquema de clasificación configurable.

    Réplica genérica, sobre datos, de `rules.clasificar_por_reglas` +
    `rules.derive_categoria`: mismo principio (reglas primero, IA solo para el
    texto libre que ninguna regla explica), pero las señales y la jerarquía
    salen del esquema de la campaña en vez de estar hardcodeadas.
    """
    esquema = compilado.esquema
    cliente = [m for m in transcript.messages if m.sender == "CUSTOMER"]

    if not cliente:
        return EsquemaOutcome(
            senales={}, categoria=esquema.categoria_sin_respuesta, requiere_ia=False, tiene_respuesta_cliente=False
        )

    senales_regla = _detectar_senales_regla(transcript, compilado)
    ids_ia = [i.id for i in esquema.indicadores if i.tipo == "ia"]

    # Texto del cliente que ninguna regla (botón/cortesía/dígito de encuesta/
    # regex_customer) explica — solo eso hace falta que interprete la IA.
    residual = [
        m
        for m in cliente
        if not rules.es_ignorable(m.message) and not _mensaje_explicado_por_regla(m.message, compilado)
    ]

    # Sin texto libre por interpretar, o sin ningún indicador de tipo "ia" que
    # pudiera explicarlo (esquema 100% basado en reglas) — no hay nada más que
    # la IA pueda aportar, así que se resuelve ya con las señales de reglas.
    # Importante: antes, con ids_ia vacío, esto caía al último return con
    # `categoria=None` (categoria_final NOT NULL en la base) en vez de resolver
    # el árbol — bug real visto en producción con un esquema sin indicadores IA.
    if not residual or not ids_ia:
        senales_completas = {**senales_regla, **{i: False for i in ids_ia}}
        categoria, subcategoria = resolver_clasificacion(senales_completas, esquema)
        return EsquemaOutcome(
            senales=senales_completas,
            categoria=categoria,
            subcategoria=subcategoria,
            requiere_ia=False,
            tiene_respuesta_cliente=True,
        )

    # Atajo: si el árbol resuelve a la MISMA categoría sin importar qué valor
    # tengan las señales de IA (ej. "interes_confirmado" ya gana la jerarquía
    # por sí sola), no hace falta llamar al modelo aunque quede texto libre.
    # (la subcategoría también cuenta: si el árbol fija la categoría pero la
    # subcategoría depende de una señal de IA, hay que preguntarle al modelo).
    clasificaciones_posibles = {
        resolver_clasificacion({**senales_regla, **dict(zip(ids_ia, combo))}, esquema)
        for combo in itertools.product([False, True], repeat=len(ids_ia))
    }
    if len(clasificaciones_posibles) == 1:
        senales_completas = {**senales_regla, **{i: False for i in ids_ia}}
        categoria, subcategoria = clasificaciones_posibles.pop()
        return EsquemaOutcome(
            senales=senales_completas,
            categoria=categoria,
            subcategoria=subcategoria,
            requiere_ia=False,
            tiene_respuesta_cliente=True,
        )

    return EsquemaOutcome(senales=senales_regla, categoria=None, requiere_ia=True, tiene_respuesta_cliente=True)
