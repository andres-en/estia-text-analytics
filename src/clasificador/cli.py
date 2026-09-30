from __future__ import annotations

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .db.engine import create_all_tables, create_db_engine, make_session_factory
from .importer import run_import
from .logging_conf import setup_logging
from .report import format_report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clasificador",
        description="Importa un archivo CDR de WhatsApp (Excel) y lo estructura en la base de datos de UN cliente.",
    )
    parser.add_argument("file", help="Ruta al archivo .xlsx a procesar")
    parser.add_argument(
        "--db-url",
        dest="db_url",
        required=True,
        help="DSN de la base de datos del cliente. "
        "Ej: mysql+mysqlconnector://usuario:clave@host:3306/cliente_x o sqlite:///./cliente_x.db",
    )
    parser.add_argument(
        "--campana-id",
        dest="campana_id",
        type=int,
        default=None,
        help="ID de la campaña (en la base del cliente) a la que asignar este import.",
    )
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Crea las tablas (imports/staging_messages/conversations/messages) si no existen",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = build_arg_parser().parse_args(argv)

    engine = create_db_engine(args.db_url)
    if args.create_tables:
        create_all_tables(engine)
    session_factory = make_session_factory(engine)

    report = run_import(args.file, session_factory, campana_id=args.campana_id)
    print(format_report(report))

    return 0 if report.status in ("COMPLETED", "COMPLETED_WITH_WARNINGS") else 1


if __name__ == "__main__":
    sys.exit(main())
