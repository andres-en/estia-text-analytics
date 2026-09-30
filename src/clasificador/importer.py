from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from .conversation_builder import build_conversations
from .db.repository import (
    compute_file_hash,
    finish_import,
    insert_staging_messages,
    save_conversation_with_messages,
    start_import,
)
from .excel_reader import ExcelValidationError, read_excel_rows
from .report import ImportReport

logger = logging.getLogger(__name__)


def run_import(file_path: str | Path, session_factory: sessionmaker, campana_id: int | None = None) -> ImportReport:
    """Procesa un archivo CDR de WhatsApp de punta a punta: lee, valida, guarda en
    staging, normaliza, clasifica, arma conversaciones y las guarda de forma
    idempotente. Ver sección 19 del documento de especificación para las etapas.
    """
    file_path = Path(file_path)
    file_hash = compute_file_hash(file_path.read_bytes())

    with session_factory() as session:
        try:
            excel_result = read_excel_rows(file_path)
        except ExcelValidationError as exc:
            logger.error("Archivo inválido %s: %s", file_path, exc)
            imp = start_import(session, file_path.name, file_hash, rows_received=0, campana_id=campana_id)
            finish_import(
                session,
                imp,
                status="ERROR",
                rows_processed=0,
                rows_error=0,
                conversations_created=0,
                conversations_updated=0,
                messages_created=0,
                messages_skipped_duplicate=0,
                error_summary=[{"error_type": "VALIDATION_ERROR", "error_message": str(exc)}],
                warning_summary=None,
            )
            session.commit()
            return ImportReport(
                file_name=file_path.name,
                status="ERROR",
                rows_received=0,
                rows_processed=0,
                rows_error=0,
                conversations_created=0,
                conversations_updated=0,
                messages_created=0,
                messages_skipped_duplicate=0,
                customer_messages=0,
                bot_messages=0,
                system_messages=0,
                row_errors=[],
                warnings=[str(exc)],
            )

        rows = excel_result.rows
        imp = start_import(session, file_path.name, file_hash, rows_received=len(rows), campana_id=campana_id)
        insert_staging_messages(session, imp.id, rows)

        conversations, row_errors = build_conversations(rows)

        conversations_created = 0
        conversations_updated = 0
        messages_created = 0
        messages_skipped_duplicate = 0
        customer_messages = 0
        bot_messages = 0
        system_messages = 0
        warnings: list[str] = []

        for draft in conversations:
            for msg in draft.messages:
                if msg.sender == "CUSTOMER":
                    customer_messages += 1
                elif msg.sender == "BOT":
                    bot_messages += 1
                else:
                    system_messages += 1
            warnings.extend(draft.warnings)

            save_result = save_conversation_with_messages(session, draft, imp.id)
            if save_result.conversation_created:
                conversations_created += 1
            else:
                conversations_updated += 1
            messages_created += save_result.messages_created
            messages_skipped_duplicate += save_result.messages_skipped_duplicate

        rows_error = len(row_errors)
        rows_processed = len(rows) - rows_error
        status = "COMPLETED_WITH_WARNINGS" if (rows_error or warnings) else "COMPLETED"

        finish_import(
            session,
            imp,
            status=status,
            rows_processed=rows_processed,
            rows_error=rows_error,
            conversations_created=conversations_created,
            conversations_updated=conversations_updated,
            messages_created=messages_created,
            messages_skipped_duplicate=messages_skipped_duplicate,
            error_summary=[
                {
                    "source_row": e.source_row,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "raw_value": e.raw_value,
                }
                for e in row_errors
            ]
            or None,
            warning_summary=[{"message": w} for w in warnings] or None,
        )
        session.commit()

        return ImportReport(
            file_name=file_path.name,
            status=status,
            rows_received=len(rows),
            rows_processed=rows_processed,
            rows_error=rows_error,
            conversations_created=conversations_created,
            conversations_updated=conversations_updated,
            messages_created=messages_created,
            messages_skipped_duplicate=messages_skipped_duplicate,
            customer_messages=customer_messages,
            bot_messages=bot_messages,
            system_messages=system_messages,
            row_errors=row_errors,
            warnings=warnings,
        )
