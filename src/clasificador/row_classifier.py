from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .normalizer import is_dash

SessionPattern = Literal["REAL", "BROADCAST_LONG_NUMERIC", "BROADCAST_DOTTED"]

# Validados contra los 4028 registros del archivo de muestra real: estos tres
# patrones cubren el 100% de los SESSION_ID observados (ver hallazgo 1 del plan).
_REAL_RE = re.compile(r"^\d{10,15}\.[\w-]+\.\d+$")
_BROADCAST_LONG_NUMERIC_RE = re.compile(r"^\d{25,40}$")
_BROADCAST_DOTTED_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


def classify_session_id(session_id: str) -> tuple[SessionPattern, bool]:
    """Clasifica el SESSION_ID. Devuelve (patrón, coincidencia_segura).

    Si ningún patrón conocido coincide (archivo futuro con un formato nuevo),
    se asume REAL de forma conservadora (para no tratar por error una
    conversación genuina como mensaje proactivo) y se marca coincidencia_segura=False
    para que el llamador registre una advertencia de calidad de datos.
    """
    sid = str(session_id).strip()
    if _REAL_RE.match(sid):
        return "REAL", True
    if _BROADCAST_LONG_NUMERIC_RE.match(sid):
        return "BROADCAST_LONG_NUMERIC", True
    if _BROADCAST_DOTTED_RE.match(sid):
        return "BROADCAST_DOTTED", True
    return "REAL", False


@dataclass(frozen=True)
class RowClassification:
    session_pattern: SessionPattern
    is_broadcast: bool
    warning: str | None


def classify_row(session_id: str, conn_id) -> RowClassification:
    """Clasifica una fila y hace una verificación cruzada con CONN_ID (hallazgo 1).

    Señal primaria: el patrón del SESSION_ID.
    Señal secundaria (de corroboración, no autoritativa): CONN_ID == "-" para
    mensajes proactivos, CONN_ID real para conversaciones reales. Si no coinciden,
    se registra una advertencia mencionando la fila, pero no se descarta el registro.
    """
    pattern, matched_known_pattern = classify_session_id(session_id)
    is_broadcast = pattern in ("BROADCAST_LONG_NUMERIC", "BROADCAST_DOTTED")
    conn_id_is_dash = is_dash(conn_id)

    warnings: list[str] = []
    if not matched_known_pattern:
        warnings.append(f"SESSION_ID '{session_id}' does not match any known pattern; assumed REAL.")
    if is_broadcast and not conn_id_is_dash:
        warnings.append(
            f"SESSION_ID '{session_id}' has pattern {pattern} (proactive expected) but CONN_ID='{conn_id}' is not '-'."
        )
    if pattern == "REAL" and matched_known_pattern and conn_id_is_dash:
        warnings.append(f"SESSION_ID '{session_id}' has pattern REAL (conversation expected) but CONN_ID is '-'.")

    return RowClassification(
        session_pattern=pattern,
        is_broadcast=is_broadcast,
        warning="; ".join(warnings) if warnings else None,
    )
