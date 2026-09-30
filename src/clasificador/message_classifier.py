from __future__ import annotations

from .pipeline_types import MessageDraft, PreparedRow

END_EXIT_CHAT = "end_exit_chat"


def classify_session_rows(rows: list[PreparedRow]) -> list[MessageDraft]:
    """Convierte las filas (ya ordenadas por fecha/source_row) de UNA conversación
    en la lista de mensajes CUSTOMER/BOT/SYSTEM que deben quedar en `messages`.

    Reglas (sección 12 del documento + hallazgo 3 del plan):
    - Fila con patrón proactivo (BROADCAST_*): CUSTOMER_QUERY -> BOT/PROACTIVE.
    - Fila REAL: CUSTOMER_QUERY -> CUSTOMER/TEXT, salvo que sea un duplicado
      adyacente exacto (mismo DATE + CONN_ID + CUSTOMER_QUERY que la fila
      inmediatamente anterior) del CDR, en cuyo caso se omite para no duplicar
      el mensaje del cliente.
    - ROUTING_ANSWER == "end_exit_chat" -> SYSTEM/SYSTEM_EVENT.
    - Cualquier otro ROUTING_ANSWER -> BOT/TEXT.
    """
    drafts: list[MessageDraft] = []
    prev_row: PreparedRow | None = None

    for row in rows:
        is_broadcast = row.session_pattern != "REAL"

        if row.customer_query is not None:
            if is_broadcast:
                drafts.append(
                    MessageDraft(row.source_row, row.conn_id, row.date, "BOT", "PROACTIVE", row.customer_query)
                )
            else:
                is_adjacent_duplicate = (
                    prev_row is not None
                    and prev_row.date == row.date
                    and prev_row.conn_id == row.conn_id
                    and prev_row.customer_query == row.customer_query
                )
                if not is_adjacent_duplicate:
                    drafts.append(
                        MessageDraft(row.source_row, row.conn_id, row.date, "CUSTOMER", "TEXT", row.customer_query)
                    )

        if row.routing_answer is not None:
            if row.routing_answer == END_EXIT_CHAT:
                drafts.append(
                    MessageDraft(row.source_row, row.conn_id, row.date, "SYSTEM", "SYSTEM_EVENT", END_EXIT_CHAT)
                )
            else:
                drafts.append(MessageDraft(row.source_row, row.conn_id, row.date, "BOT", "TEXT", row.routing_answer))

        prev_row = row

    return drafts
