from __future__ import annotations

import json

from ..conversation_view import ConversationTranscript
from .schema import EsquemaClasificacion
from .schema_engine import EsquemaCompilado
from .types import AnalysisFlags

SYSTEM_PROMPT = """\
Eres un analista que clasifica conversaciones entre un cliente y un chatbot de ventas
de "Acme", un cupo de crédito que se paga a través de la factura de servicios públicos.

Tu tarea es leer la conversación y determinar CINCO señales objetivas. NO debes asignar
ninguna categoría final: solo reportar las señales. Responde en el formato JSON indicado.

═══ REGLA 1: solo cuenta lo que dice el CLIENTE ═══
Las señales 1, 2 y 3 se refieren ÚNICAMENTE a lo que dice el CLIENTE.
NUNCA marques una señal por algo que dijo el "Bot". El bot hace preguntas
constantemente ("¿qué producto tienes en mente?", "¿tienes más dudas?"): esas
preguntas del bot NO son preguntas del cliente y deben ignorarse por completo.

═══ REGLA 2: las señales son INDEPENDIENTES entre sí ═══
Una señal NO cancela a otra. Evalúa cada una por separado, mirando TODA la
conversación. En particular, que el cliente rechace al final NO borra la
información que ya había obtenido antes.
Ejemplo real: el cliente pide "Efectivo", el bot le explica que el cupo no entrega
dinero en efectivo, y el cliente responde "No, gracias".
  → busco_informacion = true   (obtuvo la aclaración sobre el efectivo)
  → rechazo_explicito  = true   (dijo que no)
Ambas son verdaderas a la vez. No elijas una sola.

SEÑALES

1. busco_informacion
   El CLIENTE obtuvo información sobre el producto, su cupo, tasas de interés,
   condiciones, aliados o puntos de venta. Cuenta TANTO si la pidió explícitamente
   COMO si la consiguió avanzando en el flujo guiado del bot.
   IMPORTANTE: la mayoría de clientes NO usa signos de interrogación. Reconoce la
   búsqueda de información por su sentido, no por la puntuación.
   SÍ cuenta:
     - Preguntas explícitas: "Que intereses manejan", "Cuanto es mi cupo",
       "Los intereses", "A qué puntaje es el interés", "Donde puedo usarlo"
     - Explorar el catálogo respondiendo al bot, aunque sean palabras sueltas:
       "Un televisor" → "Tienda Central o ElectroHogar" → el cliente terminó sabiendo con qué
       aliados puede comprarlo. Eso ES haber resuelto una duda.
     - Pedir algo que el bot tuvo que aclararle: el cliente dice "Efectivo" y el bot
       le explica que el cupo no entrega dinero en efectivo.
   NO cuenta:
     - Cualquier cosa dicha por el Bot (el bot pregunta todo el tiempo: ignóralo)
     - Solo saludar o agradecer: "Hola", "Buenos días", "Gracias", "Ok"
     - Solo pulsar "No estoy interesado" y responder la encuesta con un dígito
     - Los mensajes de un autorespondedor de otra empresa (ver señal 5)

2. interes_confirmado  ← LEE ESTO CON CUIDADO
   El cliente CONCRETÓ la adquisición del cupo. Es una señal EXIGENTE.
   Solo marca true si el cliente:
     - aceptó que un asesor lo contacte para realizar la compra, o
     - confirmó que va a adquirir un producto concreto con su cupo, o
     - el bot respondió "Hemos registrado tu interés" / asignó la solicitud a un asesor.
   NO basta con (todos estos son false):
     - preguntar precios, cuotas, tasas o requisitos, por mucho detalle que dé
     - decir "quiero usar mi cupo" al inicio de la conversación
     - decir que le interesa pero sin concretar: "estoy interesado en 4 millones,
       cuánto pago al mes" es solo una PREGUNTA, no una adquisición
     - un interés a futuro: "más adelante les hablo", "ahora no, después"
     - mostrar curiosidad por un producto sin cerrar nada
   Ante la duda, marca false.

3. rechazo_explicito
   El CLIENTE dijo claramente que NO está interesado o que no quiere continuar.
   Ejemplos: "No estoy interesado", "No gracias, no me sirve", "No me interesa",
             "por ahora no", "no me molesten".
   NO cuenta el simple silencio, ni un "no" que responde a otra pregunta del bot.

4. bot_no_resolvio
   El BOT admitió no tener la información pedida o no pudo responder la consulta.
   Ejemplos: "no cuento con información de sedes", "no tengo acceso a ese dato".

NOTA SOBRE NUMEROS DE EMPRESAS: algunos numeros de la campana pertenecen a negocios,
y lo que aparece como "Cliente" es su respuesta automatica de WhatsApp ("Gracias por
comunicarte con...", "Como podemos ayudarte?", horarios de atencion). Eso lo detecta el
sistema por su cuenta mediante reglas: tu NO tienes que marcarlo ni reportarlo.
Si ves ese tipo de mensaje corporativo automatico, simplemente ignoralo y evalua las
senales sobre los mensajes que si escribio una persona real (si los hay).

Además entrega una justificacion breve (máximo 200 caracteres) explicando tu decisión,
citando la parte de la conversación en la que te basaste."""


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "busco_informacion": {
            "type": "boolean",
            "description": "EL CLIENTE (nunca el bot) obtuvo información del producto, la haya preguntado o no",
        },
        "interes_confirmado": {
            "type": "boolean",
            "description": "El cliente CONCRETÓ la adquisición del cupo. Preguntar o mostrar curiosidad NO basta",
        },
        "rechazo_explicito": {
            "type": "boolean",
            "description": "El cliente dijo explícitamente que no está interesado",
        },
        "bot_no_resolvio": {
            "type": "boolean",
            "description": "El bot admitió no tener la información solicitada",
        },
        "justificacion": {
            "type": "string",
            "description": "Explicación breve (máx. 200 caracteres) citando la conversación",
        },
    },
    "required": [
        "busco_informacion",
        "interes_confirmado",
        "rechazo_explicito",
        "bot_no_resolvio",
        "justificacion",
    ],
    "additionalProperties": False,
}


def formatear_transcript(transcript: ConversationTranscript) -> str:
    """Convierte la conversación a texto plano para enviarla al modelo."""
    lineas = []
    for m in transcript.messages:
        if m.sender == "SYSTEM":
            lineas.append(f"[cierre del chat: {m.message}]")
        else:
            etiqueta = "Cliente" if m.sender == "CUSTOMER" else "Bot"
            lineas.append(f"{etiqueta}: {m.message}")
    return "\n".join(lineas)


def construir_mensajes(transcript: ConversationTranscript) -> list[dict]:
    """Arma los mensajes de la petición. Función pura: testeable y usable en --dry-run."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Analiza esta conversación:\n\n{formatear_transcript(transcript)}",
        },
    ]


def _extraer_uso(respuesta) -> dict[str, int] | None:
    """Tokens de la respuesta de OpenAI, listos para `AnalysisResult`/`AIUsage`.
    `None` si la respuesta no trae `usage` (no debería pasar en la API real,
    pero un fake de test no tiene por qué simularlo)."""
    if respuesta.usage is None:
        return None
    return {
        "tokens_prompt": respuesta.usage.prompt_tokens,
        "tokens_completion": respuesta.usage.completion_tokens,
    }


class OpenAIClassifier:
    """Capa de IA. Solo se invoca para la zona gris que las reglas no pueden resolver."""

    def __init__(self, api_key: str, modelo: str, timeout: float = 60.0):
        from openai import OpenAI

        self.modelo = modelo
        self._client = OpenAI(api_key=api_key, timeout=timeout)
        # Tokens de la última llamada a `clasificar()` — lo lee `analyzer.py`
        # justo después de llamar, para guardarlo junto al resultado (ver
        # `analysis/pricing.py` para el costo). `None` = sin dato de uso.
        self.ultimo_uso: dict[str, int] | None = None

    def clasificar(self, transcript: ConversationTranscript) -> tuple[AnalysisFlags, str, dict]:
        respuesta = self._client.chat.completions.create(
            model=self.modelo,
            messages=construir_mensajes(transcript),
            temperature=0,  # máxima reproducibilidad posible
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "senales_conversacion",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                },
            },
        )
        self.ultimo_uso = _extraer_uso(respuesta)

        contenido = respuesta.choices[0].message.content
        datos = json.loads(contenido)

        # `es_autorespondedor` NO se le pide a la IA: es texto corporativo con plantilla
        # fija, justo lo que las reglas detectan con precisión y el modelo confunde
        # (llegó a marcar como "empresa" a clientes que solo pulsaron "Quiero usar mi
        # cupo"). Lo aporta `rules.detectar_senales` y se combina en el analyzer.
        flags = AnalysisFlags(
            interes_declarado=False,  # solo lo afirman los botones (reglas)
            interes_confirmado=bool(datos["interes_confirmado"]),
            busco_informacion=bool(datos["busco_informacion"]),
            rechazo_explicito=bool(datos["rechazo_explicito"]),
            bot_no_resolvio=bool(datos["bot_no_resolvio"]),
        )
        return flags, datos.get("justificacion", ""), datos


# ─── Clasificador dinámico (campañas con EsquemaClasificacion propio) ──────────

META_PROMPT_DINAMICO = """\
Eres un analista que clasifica conversaciones entre un cliente y un chatbot.
{contexto_negocio}
Tu tarea es leer la conversación y determinar las señales objetivas de abajo. NO debes
asignar ninguna categoría final: solo reportar las señales. Responde en el formato JSON
indicado.

═══ REGLA 1: solo cuenta lo que dice el CLIENTE ═══
Las señales se refieren ÚNICAMENTE a lo que dice el CLIENTE. NUNCA marques una señal por
algo que dijo el "Bot" — el bot puede preguntar constantemente, eso no cuenta.

═══ REGLA 2: las señales son INDEPENDIENTES entre sí ═══
Una señal NO cancela a otra. Evalúa cada una por separado, mirando TODA la conversación.

SEÑALES A EVALUAR
{lista_senales}

Además entrega una justificación breve (máximo 200 caracteres) explicando tu decisión,
citando la parte de la conversación en la que te basaste."""


def construir_system_prompt_dinamico(esquema: EsquemaClasificacion) -> str:
    ids_ia = [i for i in esquema.indicadores if i.tipo == "ia"]
    lista = "\n".join(f"{n}. {i.id}\n   {i.descripcion_ia}" for n, i in enumerate(ids_ia, start=1))
    contexto = f"Contexto del negocio: {esquema.contexto_negocio}\n" if esquema.contexto_negocio else ""
    return META_PROMPT_DINAMICO.format(contexto_negocio=contexto, lista_senales=lista)


def construir_response_schema_dinamico(esquema: EsquemaClasificacion) -> dict:
    propiedades: dict[str, dict] = {}
    requeridos: list[str] = []
    for i in esquema.indicadores:
        if i.tipo != "ia":
            continue
        propiedades[i.id] = {"type": "boolean", "description": i.descripcion_ia or i.label}
        requeridos.append(i.id)
    propiedades["justificacion"] = {
        "type": "string",
        "description": "Explicación breve (máx. 200 caracteres) citando la conversación",
    }
    requeridos.append("justificacion")
    return {"type": "object", "properties": propiedades, "required": requeridos, "additionalProperties": False}


class EsquemaOpenAIClassifier:
    """Igual que `OpenAIClassifier`, pero el prompt y el schema de respuesta se
    arman por campaña a partir de su `EsquemaClasificacion` en vez de estar
    fijos para el bot de venta de cupos Acme."""

    def __init__(self, api_key: str, modelo: str, timeout: float = 60.0):
        from openai import OpenAI

        self.modelo = modelo
        self._client = OpenAI(api_key=api_key, timeout=timeout)
        self.ultimo_uso: dict[str, int] | None = None

    def clasificar(
        self, transcript: ConversationTranscript, compilado: EsquemaCompilado
    ) -> tuple[dict[str, bool], str, dict]:
        esquema = compilado.esquema
        respuesta = self._client.chat.completions.create(
            model=self.modelo,
            messages=[
                {"role": "system", "content": construir_system_prompt_dinamico(esquema)},
                {"role": "user", "content": f"Analiza esta conversación:\n\n{formatear_transcript(transcript)}"},
            ],
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "senales_conversacion",
                    "strict": True,
                    "schema": construir_response_schema_dinamico(esquema),
                },
            },
        )
        self.ultimo_uso = _extraer_uso(respuesta)

        contenido = respuesta.choices[0].message.content
        datos = json.loads(contenido)

        ids_ia = [i.id for i in esquema.indicadores if i.tipo == "ia"]
        senales = {i: bool(datos.get(i, False)) for i in ids_ia}
        return senales, datos.get("justificacion", ""), datos
