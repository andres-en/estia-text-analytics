"""Utilidad de consulta rápida para ver el resultado de una importación.

Uso:
    # Lista las conversaciones más recientes
    python scripts/show_conversations.py --list

    # Lista filtrando por teléfono o SESSION_ID (coincidencia parcial)
    python scripts/show_conversations.py --list --query 573001000001

    # Imprime el transcript completo de una conversación
    python scripts/show_conversations.py --session-id "573001000002.botco-4402-acme_venta.1001"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from clasificador.conversation_view import get_transcript, list_conversations  # noqa: E402
from clasificador.db.engine import create_db_engine, make_session_factory  # noqa: E402


def print_list(session, query: str | None, limit: int) -> None:
    conversations, total = list_conversations(session, query=query, page_size=limit)
    if not conversations:
        print("No se encontraron conversaciones.")
        return

    print(f"{'SESSION_ID':<55} {'Teléfono':<15} {'Inicio':<20} {'Msjs':<5} {'Categoría'}")
    print("-" * 115)
    for c in conversations:
        print(
            f"{c.session_id:<55} {(c.customer_phone or '-'):<15} "
            f"{c.started_at.strftime('%Y-%m-%d %H:%M:%S'):<20} {c.message_count:<5} "
            f"{c.categoria_label or 'sin analizar'}"
        )
    if total > len(conversations):
        print(f"\n(mostrando {len(conversations)} de {total} conversaciones que coinciden)")


def print_transcript(session, session_id: str) -> None:
    transcript = get_transcript(session, session_id)
    if transcript is None:
        print(f"No existe una conversación con SESSION_ID='{session_id}'")
        return

    print(f"SESSION_ID: {transcript.session_id}")
    print(f"Teléfono: {transcript.customer_phone}   Nombre: {transcript.customer_name}")
    print(
        f"Inicio: {transcript.started_at}   Fin: {transcript.ended_at}   Segmentos (CONN_ID): {transcript.conn_id_count}"
    )
    print("-" * 80)
    for m in transcript.messages:
        print(f"[{m.timestamp.strftime('%H:%M:%S')}] {m.sender_label}: {m.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", dest="db_url", required=True, help="URL de la base del cliente")
    parser.add_argument("--list", action="store_true", help="Lista las conversaciones más recientes")
    parser.add_argument("--query", default=None, help="Filtra la lista por teléfono o SESSION_ID")
    parser.add_argument("--limit", type=int, default=20, help="Máximo de conversaciones a listar (default 20)")
    parser.add_argument(
        "--session-id", dest="session_id", default=None, help="Imprime el transcript de esta conversación"
    )
    args = parser.parse_args()

    engine = create_db_engine(args.db_url)
    session_factory = make_session_factory(engine)

    with session_factory() as session:
        if args.session_id:
            print_transcript(session, args.session_id)
        else:
            print_list(session, args.query, args.limit)

    return 0


if __name__ == "__main__":
    sys.exit(main())
