"""Valida la clasificación de la IA contra tu criterio, mediante etiquetado a ciegas.

Flujo:
    1) Exportar la muestra (SIN la respuesta de la IA, para no condicionar tu criterio):
       python scripts/validar_ia.py --exportar validacion.xlsx

    2) Abrir el Excel y llenar la columna TU_CATEGORIA con el desplegable.

    3) Comparar tu criterio contra el de la IA:
       python scripts/validar_ia.py --comparar validacion.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import openpyxl  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402
from sqlalchemy import select  # noqa: E402

from clasificador.conversation_view import get_transcript  # noqa: E402
from clasificador.db.engine import create_db_engine, make_session_factory  # noqa: E402
from clasificador.db.models import Conversation, ConversationAnalysis  # noqa: E402

CATEGORIAS = ["INTERESADO", "RESOLVIO_DUDAS", "NO_INTERESADO", "SIN_CLASIFICAR"]


def _conversaciones_analizadas_por_ia(session):
    """Las que resuelve la IA: son las candidatas a exportar para validación."""
    return session.execute(
        select(ConversationAnalysis, Conversation.session_id)
        .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
        .where(ConversationAnalysis.metodo == "AI")
        .order_by(Conversation.started_at)
    ).all()


def _todas_las_analizadas(session):
    """Todas, sin importar el método.

    Al comparar hay que usar esta: tras un ajuste de criterios, una conversación
    que antes resolvía la IA puede pasar a resolverse por regla, y aun así sigue
    siendo válida para contrastar contra la etiqueta manual.
    """
    return session.execute(
        select(ConversationAnalysis, Conversation.session_id).join(
            Conversation, Conversation.id == ConversationAnalysis.conversation_id
        )
    ).all()


def exportar(session_factory, destino: Path) -> int:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Validacion"

    encabezados = ["SESSION_ID", "TELEFONO", "CONVERSACION", "TU_CATEGORIA", "NOTAS"]
    ws.append(encabezados)
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", start_color="075E54")
        celda.alignment = Alignment(vertical="center")

    with session_factory() as session:
        filas = _conversaciones_analizadas_por_ia(session)
        for _, sid in filas:
            t = get_transcript(session, sid)
            lineas = []
            for m in t.messages:
                if m.sender == "SYSTEM":
                    lineas.append(f"[cierre: {m.message}]")
                else:
                    etiqueta = "CLIENTE" if m.sender == "CUSTOMER" else "Bot"
                    lineas.append(f"{etiqueta}: {m.message}")
            ws.append([sid, t.customer_phone or "", "\n".join(lineas), "", ""])

    ws.column_dimensions["A"].width = 50
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 110
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 30
    ws.freeze_panes = "A2"

    for fila in ws.iter_rows(min_row=2, min_col=3, max_col=3):
        for celda in fila:
            celda.alignment = Alignment(wrap_text=True, vertical="top")

    dv = DataValidation(
        type="list",
        formula1='"' + ",".join(CATEGORIAS) + '"',
        allow_blank=True,
        showDropDown=False,
    )
    ws.add_data_validation(dv)
    dv.add(f"D2:D{ws.max_row}")

    wb.save(destino)
    total = ws.max_row - 1
    print(f"Exportadas {total} conversaciones a {destino}")
    print("\nLlena la columna TU_CATEGORIA (tiene desplegable) y luego ejecuta:")
    print(f"  python scripts/validar_ia.py --comparar {destino}")
    return 0


def comparar(session_factory, origen: Path) -> int:
    wb = openpyxl.load_workbook(origen)
    ws = wb.active

    etiquetas_manuales: dict[str, str] = {}
    for fila in ws.iter_rows(min_row=2, values_only=True):
        sid, _telefono, _conv, categoria, *_ = fila
        if sid and categoria:
            etiquetas_manuales[str(sid)] = str(categoria).strip().upper()

    if not etiquetas_manuales:
        print("No se encontró ninguna etiqueta en la columna TU_CATEGORIA.")
        return 1

    with session_factory() as session:
        filas = _todas_las_analizadas(session)
        por_sid = {sid: analisis for analisis, sid in filas}

        coincidencias = 0
        desacuerdos = []
        for sid, manual in etiquetas_manuales.items():
            analisis = por_sid.get(sid)
            if analisis is None:
                continue
            if analisis.categoria_final == manual:
                coincidencias += 1
            else:
                razon = analisis.justificacion or f"(regla: {analisis.regla_aplicada})"
                desacuerdos.append((sid, manual, analisis.categoria_final, razon))

        total = coincidencias + len(desacuerdos)
        print(f"\nConversaciones etiquetadas: {total}")
        print(f"Coincidencias: {coincidencias}  ({coincidencias / total * 100:.1f}%)")
        print(f"Desacuerdos  : {len(desacuerdos)}  ({len(desacuerdos) / total * 100:.1f}%)")

        if desacuerdos:
            print("\n--- Desacuerdos ---")
            for sid, manual, ia, justificacion in desacuerdos:
                print(f"\n  {sid}")
                print(f"    tu criterio : {manual}")
                print(f"    la IA dijo  : {ia}")
                print(f"    razón de IA : {justificacion}")
            print(
                "\nRevisa si el desacuerdo viene de un criterio ambiguo (habría que precisar "
                "docs/classification-criteria.md) o de un error del modelo (habría que ajustar el prompt)."
            )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", dest="db_url", required=True, help="URL de la base del cliente")
    parser.add_argument("--exportar", type=Path, default=None, help="Genera el Excel para etiquetar")
    parser.add_argument("--comparar", type=Path, default=None, help="Compara el Excel etiquetado contra la IA")
    args = parser.parse_args()

    if not args.exportar and not args.comparar:
        parser.error("Indica --exportar o --comparar")

    session_factory = make_session_factory(create_db_engine(args.db_url))

    if args.exportar:
        return exportar(session_factory, args.exportar)
    return comparar(session_factory, args.comparar)


if __name__ == "__main__":
    sys.exit(main())
