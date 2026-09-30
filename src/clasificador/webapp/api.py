from __future__ import annotations

import datetime as dt
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, send_file
from werkzeug.utils import secure_filename

from .. import conversation_view as cv
from ..db import repository as client_repo
from ..importer import run_import
from ..reports import build_conversations_xlsx
from .tenancy import get_client_session_factory, require_cliente_activo

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _session_factory():
    return get_client_session_factory(g.cliente_activo_db_name)


def _analysis_runner():
    """Un `AnalysisRunner` por cliente activo, creado on-demand y cacheado —
    igual que los engines, para no compartir el estado 'está corriendo' de un
    cliente con otro."""
    runners = current_app.config["ANALYSIS_RUNNERS"]
    db_name = g.cliente_activo_db_name
    runner = runners.get(db_name)
    if runner is None:
        from .analysis_runner import AnalysisRunner

        runner = AnalysisRunner(_session_factory(), current_app.config["SETTINGS"])
        runners[db_name] = runner
    return runner


def _iso(value):
    return value.isoformat() if isinstance(value, (dt.datetime, dt.date)) else value


def _summary_json(c: cv.ConversationSummary) -> dict:
    return {
        "session_id": c.session_id,
        "customer_phone": c.customer_phone,
        "customer_name": c.customer_name,
        "started_at": _iso(c.started_at),
        "ended_at": _iso(c.ended_at),
        "message_count": c.message_count,
        "session_pattern": c.session_pattern,
        "iniciada_por": c.iniciada_por,
        "contiene_array": c.contiene_array,
        "categoria": c.categoria,
        "categoria_label": c.categoria_label,
        "subcategoria": c.subcategoria,
        "subcategoria_label": c.subcategoria_label,
    }


def _message_json(m: cv.TranscriptMessage) -> dict:
    return {
        "sequence_number": m.sequence_number,
        "timestamp": _iso(m.timestamp),
        "sender": m.sender,
        "sender_label": m.sender_label,
        "message_type": m.message_type,
        "message": m.message,
    }


def _transcript_json(t: cv.ConversationTranscript) -> dict:
    return {
        "session_id": t.session_id,
        "customer_phone": t.customer_phone,
        "customer_name": t.customer_name,
        "started_at": _iso(t.started_at),
        "ended_at": _iso(t.ended_at),
        "conn_id_count": t.conn_id_count,
        "messages": [_message_json(m) for m in t.messages],
        "iniciada_por": t.iniciada_por,
        "contiene_array": t.contiene_array,
        "categoria": t.categoria,
        "categoria_label": t.categoria_label,
        "subcategoria": t.subcategoria,
        "subcategoria_label": t.subcategoria_label,
        "metodo": t.metodo,
        "justificacion": t.justificacion,
        "indicadores": list(t.indicadores),
    }


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    return dt.date.fromisoformat(value)


def _parse_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.lower() in ("1", "true", "si", "sí")


@api_bp.route("/campaigns")
@require_cliente_activo
def campaigns():
    with _session_factory()() as session:
        campanas = client_repo.list_campanas(session)
    return jsonify(
        [{"id_campana": c.id_campana, "nombre_campana": c.nombre_campana, "estado": c.estado} for c in campanas]
    )


def _conversation_filters_from_request() -> dict:
    """Filtros compartidos por /conversations y /conversations/export."""
    return dict(
        query=request.args.get("q") or None,
        categorias=request.args.getlist("categoria") or None,
        date_from=_parse_date(request.args.get("desde")),
        date_to=_parse_date(request.args.get("hasta")),
        flag=request.args.get("flag") or None,
        iniciada_por=request.args.get("iniciada_por") or None,
        contiene_array=_parse_bool(request.args.get("contiene_array")),
    )


@api_bp.route("/conversations")
@require_cliente_activo
def conversations():
    filters = _conversation_filters_from_request()
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = min(max(request.args.get("page_size", cv.DEFAULT_PAGE_SIZE, type=int), 1), 200)

    with _session_factory()() as session:
        items, total = cv.list_conversations(session, page=page, page_size=page_size, **filters)

    return jsonify(
        {
            "items": [_summary_json(c) for c in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@api_bp.route("/conversations/export")
@require_cliente_activo
def export_conversations():
    """Reporte en Excel de las conversaciones que cumplen los filtros activos
    (los mismos que la tabla) — sin paginar, todas de una vez."""
    filters = _conversation_filters_from_request()

    with _session_factory()() as session:
        export = cv.export_conversations(session, **filters)

    buffer = build_conversations_xlsx(export)
    filename = f"conversaciones_{g.cliente_activo_nombre}_{dt.date.today():%Y%m%d}.xlsx".replace(" ", "_")
    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@api_bp.route("/conversations/<session_id>")
@require_cliente_activo
def conversation_detail(session_id: str):
    with _session_factory()() as session:
        transcript = cv.get_transcript(session, session_id)
    if transcript is None:
        return jsonify({"error": f"No conversation found with SESSION_ID '{session_id}'"}), 404
    return jsonify(_transcript_json(transcript))


@api_bp.route("/upload", methods=["POST"])
@require_cliente_activo
def upload():
    file = request.files.get("file")
    if file is None or file.filename == "":
        return jsonify({"error": "No file was selected."}), 400
    if not file.filename.lower().endswith(".xlsx"):
        return jsonify({"error": f"Expected an .xlsx file, got: {file.filename}"}), 400

    campana_id = request.form.get("campana_id", type=int)
    if not campana_id:
        return jsonify({"error": "Please select a campaign."}), 400
    with _session_factory()() as session:
        if client_repo.get_campana(session, campana_id) is None:
            return jsonify({"error": "Invalid campaign."}), 400

    upload_dir: Path = current_app.config["UPLOAD_DIR"]
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_path = upload_dir / f"{timestamp}_{secure_filename(file.filename)}"
    file.save(saved_path)

    report = run_import(saved_path, _session_factory(), campana_id=campana_id)

    # Dispara la fase 2 (clasificación) en segundo plano tras cada carga, para que
    # el usuario no tenga que correrla a mano por consola. No bloquea esta respuesta:
    # si ya hay una corrida en curso (ej. de una carga anterior), no lanza otra.
    analysis_started = _analysis_runner().start()

    return jsonify(
        {
            "file_name": report.file_name,
            "status": report.status,
            "rows_received": report.rows_received,
            "rows_processed": report.rows_processed,
            "rows_error": report.rows_error,
            "conversations_created": report.conversations_created,
            "conversations_updated": report.conversations_updated,
            "messages_created": report.messages_created,
            "messages_skipped_duplicate": report.messages_skipped_duplicate,
            "customer_messages": report.customer_messages,
            "bot_messages": report.bot_messages,
            "system_messages": report.system_messages,
            "warnings": report.warnings,
            "row_errors": [
                {
                    "source_row": e.source_row,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                }
                for e in report.row_errors
            ],
            "analysis_started": analysis_started,
        }
    )


@api_bp.route("/analyze/status")
@require_cliente_activo
def analyze_status():
    return jsonify(_analysis_runner().status())


@api_bp.route("/categorias")
@require_cliente_activo
def categorias():
    """Catálogo de categorías del cliente activo (unión de las de todas sus
    campañas, cada una con su propio esquema o el de Acme por defecto) — lo
    usa el frontend para resolver colores/etiquetas sin tenerlos hardcodeados."""
    with _session_factory()() as session:
        return jsonify(cv.categorias_disponibles(session))


@api_bp.route("/subcategorias")
@require_cliente_activo
def subcategorias():
    """Catálogo de subcategorías (segundo nivel, ej. motivo del interés) del
    cliente activo: `{"etiqueta": ..., "items": [{id,label,color,orden}]}`."""
    with _session_factory()() as session:
        return jsonify(cv.subcategorias_disponibles(session))


@api_bp.route("/dashboard")
@require_cliente_activo
def dashboard():
    desde = _parse_date(request.args.get("desde"))
    hasta = _parse_date(request.args.get("hasta"))
    with _session_factory()() as session:
        payload = {
            "category_counts": cv.category_counts(session, date_from=desde, date_to=hasta),
            "subcategory_counts": cv.subcategory_counts(session, date_from=desde, date_to=hasta),
            "category_counts_trend": cv.category_counts_trend(session, date_from=desde, date_to=hasta),
            "method_counts": cv.method_counts(session),
            "business_indicators": cv.business_indicators(session, date_from=desde, date_to=hasta),
            "business_indicators_trend": cv.business_indicators_trend(session, date_from=desde, date_to=hasta),
            "daily_trend": cv.daily_category_trend(session, date_from=desde, date_to=hasta),
        }
    return jsonify(payload)
