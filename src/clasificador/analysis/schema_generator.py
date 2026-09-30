from __future__ import annotations

import json

from .schema import CategoriaDef, CondicionIndicador, EsquemaClasificacion, IndicadorDef, ReglaDecision

SYSTEM_PROMPT_GENERADOR = """\
Eres un ingeniero que diseña esquemas de clasificación de conversaciones de WhatsApp
entre un cliente y un chatbot de ventas/atención, a partir de una descripción en texto
libre que escribe un administrador NO técnico. Responde SOLO con el JSON pedido.

Tu tarea es proponer:

1. CATEGORÍAS finales (entre 2 y 6), mutuamente excluyentes, en orden de PRIORIDAD (la
   primera cuya condición calce en el árbol de decisión gana). SIEMPRE incluye al final
   una categoría catch-all que cubra "no aplicó ninguna de las anteriores", y SIEMPRE
   incluye una categoría separada para "el cliente nunca respondió" (repórtala también
   en `categoria_sin_respuesta`).
   - `id`: MAYUSCULAS_CON_GUION_BAJO, corto, sin espacios ni tildes, único.
   - `color`: un hex distinto y legible por categoría (verde para lo positivo, rojo para
     rechazo, azul/ámbar/gris para el resto).

2. INDICADORES: señales objetivas, independientes entre sí, que combinadas en el árbol de
   decisión producen la categoría final. Cada uno es `tipo="regla"` o `tipo="ia"`:
   - `tipo="regla"`: SOLO cuando el usuario describe una frase LITERAL que dice el bot, o
     un texto exacto que escribe el cliente (ej. una opción de menú). El regex va en
     minúsculas, sin `^`/`$` (se usa con `re.search`, no tiene que matchear toda la
     línea), capturando la esencia de la frase sin ser frágil ante variaciones menores de
     redacción. `condiciones` es una lista de 1 o más — se combinan con OR (basta con que
     una calce). Deja `descripcion_ia` como cadena vacía.
     - `regex_bot`: el patrón aparece en un mensaje del BOT.
     - `regex_customer`: el patrón aparece en un mensaje del CLIENTE.
     - `boton`: el cliente escribió EXACTAMENTE ese texto.
   - `tipo="ia"`: para cualquier criterio que requiera entender la intención o el
     contenido semántico del mensaje (ej. "el cliente preguntó por precios", "el cliente
     mostró interés real en comprar"). Escribe `descripcion_ia` como una instrucción clara
     y objetiva para quien la vaya a evaluar, dejando explícito que SOLO cuenta lo que dice
     el CLIENTE, nunca el bot. Deja `condiciones` como lista vacía.

3. ÁRBOL DE DECISIÓN: filas evaluadas en orden, la primera cuya `condicion` calce (TODOS
   sus pares indicador/valor deben cumplirse a la vez) define la categoría de esa fila. La
   ÚLTIMA fila DEBE tener `condicion` vacía (catch-all, siempre calza) apuntando a la
   categoría catch-all. No repitas el mismo indicador de tipo "ia" en más de dos o tres
   filas — mientras menos dependa el árbol de la IA, más rápido y barato es clasificar.

4. `contexto_negocio`: 1 a 3 frases describiendo el producto o servicio de esta campaña,
   para dárselo como contexto a quien clasifique cada conversación.

No inventes reglas que el usuario no describió: si no menciona una frase literal del bot
o del cliente, usa `tipo="ia"` con una `descripcion_ia` clara en vez de adivinar un regex."""


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "categorias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "color": {"type": "string"},
                },
                "required": ["id", "label", "color"],
                "additionalProperties": False,
            },
        },
        "indicadores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "tipo": {"type": "string", "enum": ["regla", "ia"]},
                    "condiciones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tipo": {"type": "string", "enum": ["regex_bot", "regex_customer", "boton"]},
                                "patron": {"type": "string"},
                            },
                            "required": ["tipo", "patron"],
                            "additionalProperties": False,
                        },
                    },
                    "descripcion_ia": {"type": "string"},
                },
                "required": ["id", "label", "tipo", "condiciones", "descripcion_ia"],
                "additionalProperties": False,
            },
        },
        "arbol_decision": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "condicion": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "indicador_id": {"type": "string"},
                                "valor": {"type": "boolean"},
                            },
                            "required": ["indicador_id", "valor"],
                            "additionalProperties": False,
                        },
                    },
                    "categoria": {"type": "string"},
                },
                "required": ["condicion", "categoria"],
                "additionalProperties": False,
            },
        },
        "categoria_sin_respuesta": {"type": "string"},
        "contexto_negocio": {"type": "string"},
    },
    "required": ["categorias", "indicadores", "arbol_decision", "categoria_sin_respuesta", "contexto_negocio"],
    "additionalProperties": False,
}


class GeneradorEsquemaError(Exception):
    """El prompt del usuario no produjo un esquema utilizable."""


def construir_mensajes_generador(prompt_usuario: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT_GENERADOR},
        {"role": "user", "content": f"Descripción del administrador:\n\n{prompt_usuario}"},
    ]


def parsear_respuesta_generador(datos: dict) -> EsquemaClasificacion:
    """Convierte la respuesta cruda de la IA (JSON, con `condicion` como lista de
    pares por restricción del structured output de OpenAI) al `EsquemaClasificacion`
    que usa el resto del sistema (`condicion` como dict)."""
    categorias = tuple(
        CategoriaDef(id=c["id"], label=c["label"], color=c.get("color") or "#6b7280", orden=i)
        for i, c in enumerate(datos["categorias"])
    )
    indicadores = tuple(
        IndicadorDef(
            id=i["id"],
            label=i["label"],
            tipo=i["tipo"],
            condiciones=tuple(CondicionIndicador(tipo=c["tipo"], patron=c["patron"]) for c in i.get("condiciones", [])),
            descripcion_ia=i.get("descripcion_ia") or None,
        )
        for i in datos["indicadores"]
    )
    arbol_decision = tuple(
        ReglaDecision(
            condicion={p["indicador_id"]: bool(p["valor"]) for p in regla.get("condicion", [])},
            categoria=regla["categoria"],
        )
        for regla in datos["arbol_decision"]
    )
    return EsquemaClasificacion(
        categorias=categorias,
        indicadores=indicadores,
        arbol_decision=arbol_decision,
        categoria_sin_respuesta=datos["categoria_sin_respuesta"],
        contexto_negocio=datos.get("contexto_negocio", ""),
    )


def generar_esquema(
    prompt_usuario: str, api_key: str, modelo: str, timeout: float = 60.0
) -> tuple[EsquemaClasificacion, dict[str, int]]:
    """Genera un `EsquemaClasificacion` a partir de la descripción en texto libre
    de un administrador. Lanza `GeneradorEsquemaError` si la IA propone algo que
    no pasa `EsquemaClasificacion.validar()` — nunca devuelve un esquema roto.

    Devuelve también los tokens de la llamada (`{"tokens_prompt", "tokens_completion"}`,
    0 si la respuesta no trae `usage`) — quien llama decide si los registra
    (ver `analysis/repository.registrar_uso_ia`)."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=timeout)
    respuesta = client.chat.completions.create(
        model=modelo,
        messages=construir_mensajes_generador(prompt_usuario),
        temperature=0.2,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "esquema_clasificacion", "strict": True, "schema": RESPONSE_SCHEMA},
        },
    )
    uso = (
        {"tokens_prompt": respuesta.usage.prompt_tokens, "tokens_completion": respuesta.usage.completion_tokens}
        if respuesta.usage is not None
        else {"tokens_prompt": 0, "tokens_completion": 0}
    )

    datos = json.loads(respuesta.choices[0].message.content)
    esquema = parsear_respuesta_generador(datos)

    error = esquema.validar()
    if error is not None:
        raise GeneradorEsquemaError(f"The AI proposed an invalid schema: {error}")
    return esquema, uso
