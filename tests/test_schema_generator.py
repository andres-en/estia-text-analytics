from __future__ import annotations

import json

import pytest

from clasificador.analysis.schema_generator import (
    GeneradorEsquemaError,
    generar_esquema,
    parsear_respuesta_generador,
)

RESPUESTA_IA = {
    "categorias": [
        {"id": "MATRICULADO", "label": "Se matriculó", "color": "#1baf7a"},
        {"id": "PREGUNTO", "label": "Preguntó y no matriculó", "color": "#2a78d6"},
        {"id": "SIN_RESPUESTA", "label": "Sin respuesta", "color": "#898781"},
        {"id": "IGNORO", "label": "No mostró interés", "color": "#e34948"},
    ],
    "indicadores": [
        {
            "id": "confirmo_pago",
            "label": "Confirmó el pago",
            "tipo": "regla",
            "condiciones": [{"tipo": "regex_bot", "patron": "tu matr.cula qued. confirmada"}],
            "descripcion_ia": "",
        },
        {
            "id": "pregunto_precio",
            "label": "Preguntó el precio",
            "tipo": "ia",
            "condiciones": [],
            "descripcion_ia": "El cliente preguntó cuánto cuesta el curso",
        },
    ],
    "arbol_decision": [
        {"condicion": [{"indicador_id": "confirmo_pago", "valor": True}], "categoria": "MATRICULADO"},
        {"condicion": [{"indicador_id": "pregunto_precio", "valor": True}], "categoria": "PREGUNTO"},
        {"condicion": [], "categoria": "IGNORO"},
    ],
    "categoria_sin_respuesta": "SIN_RESPUESTA",
    "contexto_negocio": "Venta de un curso online de programación.",
}


def test_parsear_respuesta_generador_produce_esquema_valido():
    esquema = parsear_respuesta_generador(RESPUESTA_IA)
    assert esquema.validar() is None
    assert [c.id for c in esquema.categorias] == ["MATRICULADO", "PREGUNTO", "SIN_RESPUESTA", "IGNORO"]
    assert esquema.arbol_decision[0].condicion == {"confirmo_pago": True}
    assert esquema.categoria_sin_respuesta == "SIN_RESPUESTA"


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeUsage:
    def __init__(self, prompt_tokens=111, completion_tokens=22):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeCompletion:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage()


class _FakeCompletions:
    def __init__(self, content: str):
        self._content = content
        self.ultima_llamada: dict | None = None

    def create(self, **kwargs):
        self.ultima_llamada = kwargs
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content: str):
        self.completions = _FakeCompletions(content)


class _FakeOpenAI:
    def __init__(self, content: str):
        self.chat = _FakeChat(content)

    def __call__(self, api_key, timeout):  # se instancia como OpenAI(api_key=..., timeout=...)
        return self


def test_generar_esquema_con_ia_mockeada(monkeypatch):
    fake = _FakeOpenAI(json.dumps(RESPUESTA_IA))
    monkeypatch.setattr("openai.OpenAI", fake)

    esquema, uso = generar_esquema(
        "Vendo un curso online, quiero saber quién se matriculó", api_key="x", modelo="gpt-4o-mini"
    )

    assert esquema.validar() is None
    assert esquema.categorias[0].id == "MATRICULADO"
    assert fake.chat.completions.ultima_llamada["response_format"]["json_schema"]["strict"] is True
    assert uso == {"tokens_prompt": 111, "tokens_completion": 22}


def test_generar_esquema_lanza_error_si_la_ia_devuelve_algo_invalido(monkeypatch):
    respuesta_rota = {**RESPUESTA_IA, "arbol_decision": [{"condicion": [], "categoria": "NO_EXISTE"}]}
    fake = _FakeOpenAI(json.dumps(respuesta_rota))
    monkeypatch.setattr("openai.OpenAI", fake)

    with pytest.raises(GeneradorEsquemaError):
        generar_esquema("prompt cualquiera", api_key="x", modelo="gpt-4o-mini")
