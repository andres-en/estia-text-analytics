from __future__ import annotations

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ..config import load_settings
from ..db.engine import create_db_engine, make_session_factory
from ..logging_conf import setup_logging
from . import repository
from .analyzer import run_analysis


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="clasificador.analysis",
        description="Clasifica las conversaciones en INTERESADO / RESOLVIO_DUDAS / "
        "NO_INTERESADO / SIN_RESPUESTA. Ver docs/classification-criteria.md",
    )
    p.add_argument("--db-url", dest="db_url", required=True, help="URL de la base del cliente a analizar")
    p.add_argument("--limit", type=int, default=None, help="Procesa como máximo N conversaciones")
    p.add_argument("--force", action="store_true", help="Reprocesa también las ya analizadas")
    p.add_argument("--sin-ia", action="store_true", help="Solo reglas; no llama a la API de OpenAI")
    p.add_argument("--resumen", action="store_true", help="Solo muestra la distribución actual y sale")
    p.add_argument(
        "--recalcular",
        action="store_true",
        help="Reaplica el árbol de decisión del esquema sobre las señales ya guardadas (sin llamar a la IA)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra qué conversaciones irían a la IA y el prompt que se enviaría, sin llamarla",
    )
    return p


def _imprimir_resumen(session_factory) -> None:
    with session_factory() as session:
        por_categoria = repository.resumen_por_categoria(session)
        por_metodo = repository.resumen_por_metodo(session)

    if not por_categoria:
        print("Todavía no hay conversaciones analizadas.")
        return

    total = sum(n for _, n in por_categoria)
    print(f"\nDistribución por categoría ({total} conversaciones analizadas):")
    for cat, n in por_categoria:
        print(f"  {cat:<16} {n:>6}  ({n / total * 100:5.1f}%)")

    print("\nMétodo de clasificación:")
    for metodo, n in por_metodo:
        etiqueta = "reglas" if metodo == "RULE" else "IA"
        print(f"  {etiqueta:<16} {n:>6}  ({n / total * 100:5.1f}%)")


def _dry_run(session_factory, limit: int | None, force: bool) -> int:
    """Muestra la zona gris y el prompt exacto que se enviaría, sin llamar a la API."""
    from ..conversation_view import get_transcript
    from .ai_client import construir_mensajes
    from .rules import clasificar_por_reglas

    with session_factory() as session:
        session_ids = repository.session_ids_pendientes(session, incluir_analizadas=force)

        grises = []
        for sid in session_ids:
            transcript = get_transcript(session, sid)
            if transcript is not None and clasificar_por_reglas(transcript).requiere_ia:
                grises.append(transcript)

        mostrar = grises[:limit] if limit is not None else grises

        print(f"\nZona gris: {len(grises)} conversaciones requerirían IA.")
        if grises:
            mensajes = construir_mensajes(grises[0])
            print("\n--- Prompt de sistema (idéntico para todas) ---")
            print(mensajes[0]["content"])
            print(f"\n--- Ejemplo de entrada ({len(mostrar)} conversaciones a mostrar) ---")
            for t in mostrar:
                print(f"\n=== {t.session_id} ===")
                print(construir_mensajes(t)[1]["content"])

    return 0


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = build_arg_parser().parse_args(argv)

    settings = load_settings()  # CONTROL_DB_URL solo se usa para leer OPENAI_API_KEY/MODEL de .env
    engine = create_db_engine(args.db_url)
    session_factory = make_session_factory(engine)

    if args.resumen:
        _imprimir_resumen(session_factory)
        return 0

    if args.recalcular:
        from .analyzer import recalcular_categorias

        rep = recalcular_categorias(session_factory)
        print(
            f"Recalculo completado: {rep.revisadas} revisadas, {rep.cambiadas} cambiadas, {rep.sin_esquema} sin esquema propio (no tocadas)."
        )
        _imprimir_resumen(session_factory)
        return 0

    if args.dry_run:
        return _dry_run(session_factory, limit=args.limit, force=args.force)

    ai_client = None
    ai_client_esquema = None
    if not args.sin_ia:
        from .ai_client import EsquemaOpenAIClassifier, OpenAIClassifier

        api_key = settings.require_openai_api_key()
        ai_client = OpenAIClassifier(api_key=api_key, modelo=settings.openai_model)
        ai_client_esquema = EsquemaOpenAIClassifier(api_key=api_key, modelo=settings.openai_model)

    report = run_analysis(
        session_factory,
        ai_client=ai_client,
        ai_client_esquema=ai_client_esquema,
        limit=args.limit,
        force=args.force,
    )

    print("\nAnálisis completado")
    print(f"  Conversaciones evaluadas : {report.total_evaluadas}")
    print(f"  Resueltas por reglas     : {report.resueltas_por_regla}")
    print(f"  Resueltas por IA         : {report.resueltas_por_ia}")
    if report.pendientes_de_ia:
        print(f"  Pendientes (zona gris)   : {report.pendientes_de_ia}  <- requieren IA")
    print(f"  Registros nuevos         : {report.nuevas}")
    print(f"  Registros actualizados   : {report.actualizadas}")

    if report.por_categoria:
        print("\n  Categorías asignadas en esta corrida:")
        for cat, n in sorted(report.por_categoria.items(), key=lambda x: -x[1]):
            print(f"    {cat:<16} {n:>6}")

    if report.errores:
        print(f"\n  Errores ({len(report.errores)}):")
        for e in report.errores[:10]:
            print(f"    {e.session_id}: {e.mensaje}")
        if len(report.errores) > 10:
            print(f"    ... y {len(report.errores) - 10} más")

    _imprimir_resumen(session_factory)
    return 0


if __name__ == "__main__":
    sys.exit(main())
