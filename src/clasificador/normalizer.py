from __future__ import annotations

import datetime as dt
import math
import re
from typing import Any

import pandas as pd

_NON_DIGIT_RE = re.compile(r"\D+")
_SCI_NOTATION_RE = re.compile(r"^-?\d+(\.\d+)?[eE][+-]?\d+$")

MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 15


def is_dash(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and value.strip() == "-":
        return True
    return False


def normalize_text(value: Any) -> str | None:
    """Convierte el placeholder "-" (y variantes nulas) del Excel en None."""
    if is_dash(value):
        return None
    text = str(value).strip()
    return text if text else None


def normalize_phone(value: Any) -> str | None:
    """Normaliza un teléfono a solo dígitos como texto, ej. '573001000001'.

    Maneja: int/float (incl. artefactos de coma flotante y notación científica
    tipo '5.73001000001E+11'), strings con espacios/guiones/paréntesis/'+'.
    Ver sección 13 del documento de especificación.
    """
    if is_dash(value):
        return None

    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)

    if isinstance(value, float):
        if math.isnan(value):
            return None
        return str(int(round(value)))

    text = str(value).strip()
    if not text:
        return None

    if _SCI_NOTATION_RE.match(text):
        return str(int(round(float(text))))

    digits = _NON_DIGIT_RE.sub("", text)
    return digits or None


def is_valid_phone(digits: str | None) -> bool:
    if not digits:
        return False
    return digits.isdigit() and MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS


def normalize_date(value: Any) -> dt.datetime | None:
    if is_dash(value):
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=False)
    if parsed is None or pd.isna(parsed):
        return None
    return parsed.to_pydatetime()
