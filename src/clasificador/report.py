from __future__ import annotations

import dataclasses

from .conversation_builder import RowProcessingError


@dataclasses.dataclass
class ImportReport:
    file_name: str
    status: str
    rows_received: int
    rows_processed: int
    rows_error: int
    conversations_created: int
    conversations_updated: int
    messages_created: int
    messages_skipped_duplicate: int
    customer_messages: int
    bot_messages: int
    system_messages: int
    row_errors: list[RowProcessingError]
    warnings: list[str]


_MAX_LISTED = 20


def format_report(report: ImportReport) -> str:
    lines = [
        f"Importación: {report.file_name}",
        f"Estado: {report.status}",
        "",
        f"Filas recibidas:              {report.rows_received}",
        f"Filas procesadas:             {report.rows_processed}",
        f"Filas con error:              {report.rows_error}",
        "",
        f"Conversaciones nuevas:        {report.conversations_created}",
        f"Conversaciones actualizadas:  {report.conversations_updated}",
        "",
        f"Mensajes nuevos:              {report.messages_created}",
        f"Mensajes duplicados (omitidos): {report.messages_skipped_duplicate}",
        f"Mensajes cliente:             {report.customer_messages}",
        f"Mensajes bot:                 {report.bot_messages}",
        f"Eventos de sistema:           {report.system_messages}",
    ]

    if report.warnings:
        lines.append("")
        lines.append(f"Advertencias de calidad de datos ({len(report.warnings)}):")
        for w in report.warnings[:_MAX_LISTED]:
            lines.append(f"  - {w}")
        if len(report.warnings) > _MAX_LISTED:
            lines.append(f"  ... y {len(report.warnings) - _MAX_LISTED} más")

    if report.row_errors:
        lines.append("")
        lines.append(f"Errores por fila ({len(report.row_errors)}):")
        for e in report.row_errors[:_MAX_LISTED]:
            lines.append(f"  - fila {e.source_row}: [{e.error_type}] {e.error_message}")
        if len(report.row_errors) > _MAX_LISTED:
            lines.append(f"  ... y {len(report.row_errors) - _MAX_LISTED} más")

    return "\n".join(lines)
