from __future__ import annotations

import dataclasses
import datetime as dt
import threading

from ..analysis.analyzer import AnalysisReport, run_analysis
from ..config import Settings


@dataclasses.dataclass
class AnalysisStatus:
    state: str = "idle"  # idle | running | done | error
    total: int = 0
    evaluadas: int = 0
    resueltas_por_regla: int = 0
    resueltas_por_ia: int = 0
    pendientes_de_ia: int = 0
    errores: int = 0
    usa_ia: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


class AnalysisRunner:
    """Corre la fase 2 (clasificación) en un hilo de fondo y expone su progreso.

    Pensado para dispararse solo tras cada carga (`/api/upload`), sin bloquear
    el servidor mientras corre (ver `webapp/__main__.py`: Flask con
    `threaded=True`). Solo admite una corrida a la vez — si ya hay una en
    curso, `start()` no lanza otra, para no pisarse las mismas conversaciones
    pendientes.
    """

    def __init__(self, session_factory, settings: Settings) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._lock = threading.Lock()
        self._status = AnalysisStatus()

    def status(self) -> dict:
        with self._lock:
            return self._status.as_dict()

    def start(self) -> bool:
        """Lanza una corrida en background. Devuelve False si ya había una corriendo."""
        with self._lock:
            if self._status.state == "running":
                return False
            self._status = AnalysisStatus(state="running", started_at=dt.datetime.now().isoformat())

        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return True

    def _run(self) -> None:
        usa_ia = bool(self._settings.openai_api_key)
        ai_client = None
        ai_client_esquema = None
        if usa_ia:
            from ..analysis.ai_client import EsquemaOpenAIClassifier, OpenAIClassifier

            ai_client = OpenAIClassifier(api_key=self._settings.openai_api_key, modelo=self._settings.openai_model)
            # Campañas con `EsquemaClasificacion` propio (ver analysis/schema.py)
            # necesitan este clasificador aparte — sin él, su zona gris se
            # queda pendiente para siempre (`ai_client` solo sirve al motor
            # fijo de Acme).
            ai_client_esquema = EsquemaOpenAIClassifier(
                api_key=self._settings.openai_api_key, modelo=self._settings.openai_model
            )

        with self._lock:
            self._status.usa_ia = usa_ia

        def on_progress(report: AnalysisReport, total: int) -> None:
            with self._lock:
                self._status.total = total
                self._status.evaluadas = report.total_evaluadas
                self._status.resueltas_por_regla = report.resueltas_por_regla
                self._status.resueltas_por_ia = report.resueltas_por_ia
                self._status.pendientes_de_ia = report.pendientes_de_ia
                self._status.errores = len(report.errores)

        try:
            run_analysis(
                self._session_factory,
                ai_client=ai_client,
                ai_client_esquema=ai_client_esquema,
                on_progress=on_progress,
            )
            with self._lock:
                self._status.state = "done"
                self._status.finished_at = dt.datetime.now().isoformat()
        except Exception as exc:  # un fallo del hilo no debe tumbar el servidor
            with self._lock:
                self._status.state = "error"
                self._status.error_message = f"{type(exc).__name__}: {exc}"
                self._status.finished_at = dt.datetime.now().isoformat()
