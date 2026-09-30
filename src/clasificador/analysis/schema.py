from __future__ import annotations

import dataclasses
import re

from .rules_config import (
    DEFAULT_BOTON_ASESOR,
    DEFAULT_BOTON_CUPO,
    DEFAULT_BOTON_NO_INTERESADO,
    DEFAULT_RX_AUTORESPONDEDOR,
    DEFAULT_RX_BOT_NO_RESOLVIO,
    DEFAULT_RX_ENCUESTA_RECHAZO,
    DEFAULT_RX_INTERES_CONFIRMADO,
)

# Tipos de condición que puede tener un indicador de tipo "regla":
#   regex_bot       — coincide contra los mensajes del BOT
#   regex_customer   — coincide contra los mensajes del CLIENTE
#   boton           — el cliente escribió exactamente este texto (normalizado,
#                     mismo criterio que `rules_config.normalizar`)
CONDICION_TIPOS = frozenset({"regex_bot", "regex_customer", "boton"})
INDICADOR_TIPOS = frozenset({"regla", "ia"})


@dataclasses.dataclass(frozen=True)
class CategoriaDef:
    id: str
    label: str
    color: str = "#6b7280"
    orden: int = 0
    # No aparece en las gráficas/tarjetas del dashboard (ej. "Sin respuesta",
    # que es la gran mayoría y no aporta a analizar el interés). Las
    # conversaciones siguen existiendo y se pueden filtrar en la tabla.
    ocultar_en_dashboard: bool = False

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "color": self.color,
            "orden": self.orden,
            "ocultar_en_dashboard": self.ocultar_en_dashboard,
        }

    @classmethod
    def from_json(cls, data: dict) -> CategoriaDef:
        return cls(
            id=data["id"],
            label=data.get("label", data["id"]),
            color=data.get("color", "#6b7280"),
            orden=int(data.get("orden", 0)),
            ocultar_en_dashboard=bool(data.get("ocultar_en_dashboard", False)),
        )


@dataclasses.dataclass(frozen=True)
class CondicionIndicador:
    tipo: str  # ver CONDICION_TIPOS
    patron: str  # regex (regex_bot/regex_customer) o texto exacto de botón (boton)

    def to_json(self) -> dict:
        return {"tipo": self.tipo, "patron": self.patron}

    @classmethod
    def from_json(cls, data: dict) -> CondicionIndicador:
        return cls(tipo=data["tipo"], patron=data["patron"])


@dataclasses.dataclass(frozen=True)
class IndicadorDef:
    """Una señal detectable en la conversación, independiente de las demás.

    `tipo="regla"`: se evalúa con OR lógico entre todas sus `condiciones` (ninguna
    entrada del cliente/bot necesita cumplirlas todas, basta con una).
    `tipo="ia"`: la evalúa el modelo, usando `descripcion_ia` como criterio.
    """

    id: str
    label: str
    tipo: str  # ver INDICADOR_TIPOS
    condiciones: tuple[CondicionIndicador, ...] = ()
    descripcion_ia: str | None = None

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "tipo": self.tipo,
            "condiciones": [c.to_json() for c in self.condiciones],
            "descripcion_ia": self.descripcion_ia,
        }

    @classmethod
    def from_json(cls, data: dict) -> IndicadorDef:
        return cls(
            id=data["id"],
            label=data.get("label", data["id"]),
            tipo=data["tipo"],
            condiciones=tuple(CondicionIndicador.from_json(c) for c in data.get("condiciones", [])),
            descripcion_ia=data.get("descripcion_ia"),
        )


@dataclasses.dataclass(frozen=True)
class ReglaDecision:
    """Una fila del árbol de decisión: si `condicion` calza (AND de cada clave),
    la conversación se clasifica en `categoria`. Se evalúan en orden, la primera
    que calce gana — `condicion={}` es un catch-all (siempre calza)."""

    condicion: dict[str, bool]
    categoria: str

    def to_json(self) -> dict:
        return {"condicion": self.condicion, "categoria": self.categoria}

    @classmethod
    def from_json(cls, data: dict) -> ReglaDecision:
        return cls(condicion=dict(data.get("condicion", {})), categoria=data["categoria"])


@dataclasses.dataclass(frozen=True)
class EsquemaClasificacion:
    """Categorías + señales + árbol de decisión configurables por campaña.

    Reemplaza, de forma opcional y por campaña, al motor fijo de
    `analysis/rules.py` (hardcodeado para el bot de venta de cupos Acme). Una
    campaña sin esquema (`from_json` devuelve `None`) sigue usando ese motor
    fijo sin ningún cambio de comportamiento.
    """

    categorias: tuple[CategoriaDef, ...]
    indicadores: tuple[IndicadorDef, ...]
    arbol_decision: tuple[ReglaDecision, ...]
    categoria_sin_respuesta: str = "SIN_RESPUESTA"
    contexto_negocio: str = ""
    # Segundo nivel opcional: una subcategoría (ej. el motivo del interés) que
    # solo se calcula para las categorías de `subcategoria_aplica_a`, con su
    # propio árbol (`arbol_subcategoria`, mismo formato que `arbol_decision`
    # pero apuntando a ids de `subcategorias`). Se guarda en una columna aparte
    # de la categoría final, así el dashboard puede graficar ambos niveles.
    subcategorias: tuple[CategoriaDef, ...] = ()
    arbol_subcategoria: tuple[ReglaDecision, ...] = ()
    subcategoria_aplica_a: tuple[str, ...] = ()
    subcategoria_etiqueta: str = "Subcategoría"

    def to_json(self) -> dict:
        return {
            "categorias": [c.to_json() for c in self.categorias],
            "indicadores": [i.to_json() for i in self.indicadores],
            "arbol_decision": [r.to_json() for r in self.arbol_decision],
            "categoria_sin_respuesta": self.categoria_sin_respuesta,
            "contexto_negocio": self.contexto_negocio,
            "subcategorias": [c.to_json() for c in self.subcategorias],
            "arbol_subcategoria": [r.to_json() for r in self.arbol_subcategoria],
            "subcategoria_aplica_a": list(self.subcategoria_aplica_a),
            "subcategoria_etiqueta": self.subcategoria_etiqueta,
        }

    @classmethod
    def from_json(cls, data: dict | None) -> EsquemaClasificacion | None:
        """`data` es el valor de la clave `esquema_clasificacion` dentro de
        `campanas.configuracion` — no todo el JSON de configuración. `None` o
        vacío significa "esta campaña no tiene esquema propio, usa el motor fijo"."""
        if not data:
            return None
        return cls(
            categorias=tuple(CategoriaDef.from_json(c) for c in data.get("categorias", [])),
            indicadores=tuple(IndicadorDef.from_json(i) for i in data.get("indicadores", [])),
            arbol_decision=tuple(ReglaDecision.from_json(r) for r in data.get("arbol_decision", [])),
            categoria_sin_respuesta=data.get("categoria_sin_respuesta", "SIN_RESPUESTA"),
            contexto_negocio=data.get("contexto_negocio", ""),
            subcategorias=tuple(CategoriaDef.from_json(c) for c in data.get("subcategorias", [])),
            arbol_subcategoria=tuple(ReglaDecision.from_json(r) for r in data.get("arbol_subcategoria", [])),
            subcategoria_aplica_a=tuple(data.get("subcategoria_aplica_a", [])),
            subcategoria_etiqueta=data.get("subcategoria_etiqueta", "Subcategoría"),
        )

    def validar(self) -> str | None:
        """Devuelve un mensaje de error si el esquema es inconsistente, o None si está bien."""
        if not self.categorias:
            return "The schema must declare at least one category."
        if not self.indicadores:
            return "The schema must declare at least one indicator."

        ids_categoria = [c.id for c in self.categorias]
        if len(set(ids_categoria)) != len(ids_categoria):
            return "There are duplicated category ids."

        ids_indicador = [i.id for i in self.indicadores]
        if len(set(ids_indicador)) != len(ids_indicador):
            return "There are duplicated indicator ids."

        for ind in self.indicadores:
            if ind.tipo not in INDICADOR_TIPOS:
                return f"{ind.id}: tipo de indicador inválido ({ind.tipo})."
            if ind.tipo == "regla":
                if not ind.condiciones:
                    return f"{ind.id}: un indicador de tipo 'regla' necesita al menos una condición."
                for c in ind.condiciones:
                    if c.tipo not in CONDICION_TIPOS:
                        return f"{ind.id}: tipo de condición inválido ({c.tipo})."
                    if c.tipo != "boton":
                        try:
                            re.compile(c.patron, re.IGNORECASE)
                        except re.error as exc:
                            return f"{ind.id}: expresión regular inválida ({exc})."
            elif ind.tipo == "ia" and not ind.descripcion_ia:
                return f"{ind.id}: un indicador de tipo 'ia' necesita 'descripcion_ia'."

        set_ids_categoria = set(ids_categoria)
        set_ids_indicador = set(ids_indicador)
        for regla in self.arbol_decision:
            if regla.categoria not in set_ids_categoria:
                return f"The decision tree references an undeclared category: {regla.categoria!r}."
            for clave in regla.condicion:
                if clave not in set_ids_indicador:
                    return f"The decision tree references an undeclared indicator: {clave!r}."

        if self.categoria_sin_respuesta not in set_ids_categoria:
            return (
                f"categoria_sin_respuesta ({self.categoria_sin_respuesta!r}) no está entre las categorías declaradas."
            )

        if self.subcategorias or self.arbol_subcategoria or self.subcategoria_aplica_a:
            ids_sub = {c.id for c in self.subcategorias}
            if len(ids_sub) != len(self.subcategorias):
                return "There are duplicated subcategory ids."
            if not ids_sub or not self.arbol_subcategoria or not self.subcategoria_aplica_a:
                return "Subcategories require subcategorias, arbol_subcategoria and subcategoria_aplica_a."
            for cat_id in self.subcategoria_aplica_a:
                if cat_id not in set_ids_categoria:
                    return f"subcategoria_aplica_a referencia una categoría no declarada: {cat_id!r}."
            for regla in self.arbol_subcategoria:
                if regla.categoria not in ids_sub:
                    return f"The subcategory tree references an undeclared subcategory: {regla.categoria!r}."
                for clave in regla.condicion:
                    if clave not in set_ids_indicador:
                        return f"The subcategory tree references an undeclared indicator: {clave!r}."

        return None


# Esquema por defecto: reproduce EXACTAMENTE las 5 categorías / 6 señales /
# jerarquía que hoy están hardcodeadas en `rules.py` + `ai_client.py` para el
# bot de venta de cupos Acme. No se usa para clasificar (ese camino sigue
# siendo el motor fijo, ver `analyzer.analizar_conversacion`) — sirve como
# referencia para el generador de esquemas con IA y para mostrarle al usuario
# "así se ve un esquema" en el frontend.
DEFAULT_ESQUEMA = EsquemaClasificacion(
    categorias=(
        CategoriaDef("SIN_RESPUESTA", "No response", "#898781", 0),
        CategoriaDef("INTERESADO", "Interested", "#1baf7a", 1),
        CategoriaDef("RESOLVIO_DUDAS", "Questions answered", "#2a78d6", 2),
        CategoriaDef("NO_INTERESADO", "Not interested", "#e34948", 3),
    ),
    indicadores=(
        IndicadorDef(
            "interes_confirmado",
            "Confirmed interest",
            "regla",
            condiciones=(CondicionIndicador("regex_bot", DEFAULT_RX_INTERES_CONFIRMADO),),
        ),
        IndicadorDef(
            "interes_declarado",
            "Declared interest",
            "regla",
            condiciones=(
                CondicionIndicador("regex_bot", DEFAULT_RX_INTERES_CONFIRMADO),
                CondicionIndicador("boton", DEFAULT_BOTON_CUPO),
                CondicionIndicador("boton", DEFAULT_BOTON_ASESOR),
            ),
        ),
        IndicadorDef(
            "rechazo_explicito",
            "Explicit rejection",
            "regla",
            condiciones=(
                CondicionIndicador("boton", DEFAULT_BOTON_NO_INTERESADO),
                CondicionIndicador("regex_bot", DEFAULT_RX_ENCUESTA_RECHAZO),
            ),
        ),
        IndicadorDef(
            "bot_no_resolvio",
            "Bot could not help",
            "regla",
            condiciones=(CondicionIndicador("regex_bot", DEFAULT_RX_BOT_NO_RESOLVIO),),
        ),
        IndicadorDef(
            "es_autorespondedor",
            "Business auto-reply",
            "regla",
            condiciones=(CondicionIndicador("regex_customer", DEFAULT_RX_AUTORESPONDEDOR),),
        ),
        IndicadorDef(
            "busco_informacion",
            "Sought information",
            "ia",
            descripcion_ia=(
                "El CLIENTE (nunca el bot) obtuvo información sobre el producto, su cupo, "
                "tasas, condiciones, aliados o puntos de venta — la haya pedido explícitamente "
                "o la haya conseguido avanzando en el flujo guiado del bot."
            ),
        ),
    ),
    arbol_decision=(
        ReglaDecision({"interes_confirmado": True}, "INTERESADO"),
        ReglaDecision({"busco_informacion": True}, "RESOLVIO_DUDAS"),
        ReglaDecision({}, "NO_INTERESADO"),
    ),
)
