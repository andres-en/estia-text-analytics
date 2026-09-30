from __future__ import annotations

import io

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .conversation_view import SENDER_LABEL, ConversationExportRow, ExportResult

METODO_LABEL = {"RULE": "Rule", "AI": "AI"}

# Orden preferido para los 6 ids que usaba el motor fijo de Acme — así una
# campaña que todavía no tiene esquema propio (o datos históricos previos a
# `EsquemaClasificacion`) mantiene el mismo orden de columnas de siempre. Ids
# nuevos que no estén en esta lista se agregan después, en el orden en que
# aparecen en los datos.
ORDEN_INDICADORES_LEGADO = [
    "interes_declarado",
    "interes_confirmado",
    "busco_informacion",
    "rechazo_explicito",
    "bot_no_resolvio",
    "es_autorespondedor",
]

COLUMNAS_BASE: list[tuple[str, int]] = [
    ("SESSION_ID", 46),
    ("Phone", 16),
    ("Name", 22),
    ("Campaign", 20),
    ("Start", 18),
    ("End", 18),
    ("Messages", 10),
    ("Started by", 12),
    ("Category", 16),
    ("Method", 9),
]

COLUMNAS_FINALES: list[tuple[str, int]] = [
    ('Contains "Array"', 15),
    ("AI rationale", 60),
]


def _si_no(valor: bool | None) -> str:
    """Sí/No, o vacío para conversaciones sin analizar (valor no evaluado)."""
    if valor is None:
        return ""
    return "Yes" if valor else "No"


def _ids_indicadores_presentes(rows: list[ConversationExportRow]) -> list[str]:
    """Unión de ids de indicador presentes en `senales`, en un orden estable:
    primero los 6 legados (si aparecen), luego cualquier otro en el orden en
    que se encuentran — para que una campaña con esquema propio (ver
    `analysis/schema.py`) muestre sus propias columnas."""
    vistos: set[str] = set()
    orden_aparicion: list[str] = []
    for r in rows:
        for indicador_id in r.senales or {}:
            if indicador_id not in vistos:
                vistos.add(indicador_id)
                orden_aparicion.append(indicador_id)

    return [i for i in ORDEN_INDICADORES_LEGADO if i in vistos] + [
        i for i in orden_aparicion if i not in ORDEN_INDICADORES_LEGADO
    ]


def build_conversations_xlsx(export: ExportResult) -> io.BytesIO:
    """Arma el reporte de conversaciones en memoria, listo para descargar.

    Las columnas de indicador (antes una lista fija de 6: Interés declarado,
    Interés confirmado, etc.) ahora se arman dinámicamente a partir de
    `senales` — cada campaña puede tener sus propios indicadores (ver
    `analysis/schema.py`), así que la columna se genera sola en vez de quedar
    en blanco para una campaña con un esquema distinto al de Acme.
    """
    rows = export.rows
    ids_indicadores = _ids_indicadores_presentes(rows)
    columnas_indicadores = [
        (export.indicador_labels.get(i, i.replace("_", " ").capitalize()), 16) for i in ids_indicadores
    ]
    # Columna de subcategoría (ej. "Motivo del interés") justo después del
    # método, solo si alguna conversación exportada la tiene.
    columnas_sub = [(export.subcategoria_etiqueta, 26)] if export.subcategoria_etiqueta else []
    columnas = COLUMNAS_BASE + columnas_sub + columnas_indicadores + COLUMNAS_FINALES

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Conversations"

    ws.append([nombre for nombre, _ in columnas])
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", start_color="075E54")
        celda.alignment = Alignment(vertical="center")

    for r in rows:
        senales = r.senales or {}
        fila = [
            r.session_id,
            r.customer_phone or "",
            r.customer_name or "",
            r.campana_nombre or "",
            r.started_at,
            r.ended_at,
            r.message_count,
            SENDER_LABEL.get(r.iniciada_por, r.iniciada_por),
            r.categoria_label,
            METODO_LABEL.get(r.metodo or "", ""),
        ]
        if columnas_sub:
            fila.append(r.subcategoria_label or "")
        fila += [_si_no(senales.get(i)) if r.senales is not None else "" for i in ids_indicadores]
        fila += [_si_no(r.contiene_array), r.justificacion or ""]
        ws.append(fila)

    for i, (_, ancho) in enumerate(columnas, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho

    fecha_formato = "DD/MM/YYYY HH:MM"
    for fila in ws.iter_rows(min_row=2, min_col=5, max_col=6):
        for celda in fila:
            celda.number_format = fecha_formato

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columnas))}{ws.max_row}"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
