"""Precios de referencia por modelo de OpenAI, en USD por millón de tokens.

Son los publicados por OpenAI al momento de escribir este archivo — OpenAI los
cambia con cierta frecuencia y sin aviso. Antes de usar el costo estimado para
una decisión de negocio, verificalos contra https://openai.com/api/pricing/ y
actualiza este diccionario si cambiaron.
"""

from __future__ import annotations

PRECIOS_USD_POR_MILLON: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
}


def estimar_costo_usd(modelo: str, tokens_prompt: int, tokens_completion: int) -> float | None:
    """`None` si no hay un precio conocido para `modelo` — a propósito, para no
    mostrar un costo de $0 cuando en realidad es "no lo sabemos"."""
    precio = PRECIOS_USD_POR_MILLON.get(modelo)
    if precio is None:
        return None
    return (float(tokens_prompt) / 1_000_000) * precio["input"] + (float(tokens_completion) / 1_000_000) * precio[
        "output"
    ]
