"""Purga filas viejas de staging_messages (copia cruda de auditoría de cada carga).

`staging_messages` no se deduplica nunca (a diferencia de `conversations`/
`messages`) y crece sin límite con cada importación. Los datos de negocio ya
viven, estructurados, en `conversations`/`messages` — este script no los toca.

Uso:
    python scripts/purge_staging_messages.py --dry-run       # cuenta, no borra
    python scripts/purge_staging_messages.py                 # borra lo más viejo de 180 días
    python scripts/purge_staging_messages.py --dias 90        # ventana de retención distinta
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from clasificador.db import repository  # noqa: E402
from clasificador.db.engine import create_db_engine, make_session_factory  # noqa: E402

RETENCION_DEFAULT_DIAS = 180  # 6 meses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", dest="db_url", required=True, help="URL de la base del cliente")
    parser.add_argument("--dias", type=int, default=RETENCION_DEFAULT_DIAS, help="Ventana de retención en días")
    parser.add_argument("--dry-run", action="store_true", help="Solo cuenta las filas que se borrarían")
    args = parser.parse_args(argv)

    engine = create_db_engine(args.db_url)
    session_factory = make_session_factory(engine)

    limite = dt.datetime.now() - dt.timedelta(days=args.dias)

    with session_factory() as session:
        if args.dry_run:
            n = repository.contar_staging_antiguo(session, limite)
            print(f"Se borrarían {n} filas de staging_messages anteriores a {limite:%Y-%m-%d} (--dias {args.dias}).")
            return 0

        n = repository.purgar_staging_antiguo(session, limite)
        session.commit()
        print(f"Borradas {n} filas de staging_messages anteriores a {limite:%Y-%m-%d} (--dias {args.dias}).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
