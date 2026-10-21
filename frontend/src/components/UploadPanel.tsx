import { useEffect, useRef, useState, type DragEvent } from 'react'
import { motion } from 'motion/react'
import { ChevronDown, FileSpreadsheet, Megaphone, Upload, X } from 'lucide-react'
import {
  fetchAnalysisStatus,
  fetchCampaigns,
  uploadFile,
  type AnalysisStatus,
  type Campaign,
  type ImportReport,
} from '../api/client'
import { springSettle } from '../lib/motionPresets'
import { formatNumber } from '../lib/format'
import Modal from './Modal'
import Badge from './Badge'

const POLL_MS = 1500

export default function UploadPanel({ onUploaded }: { onUploaded: () => void }) {
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [campanaId, setCampanaId] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [report, setReport] = useState<ImportReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisStatus | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const pollRef = useRef<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const selectFile = (f: File | null) => {
    if (f && !f.name.toLowerCase().endsWith('.xlsx')) {
      setError('El archivo debe ser un .xlsx')
      return
    }
    setError(null)
    setFile(f)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragActive(false)
    selectFile(e.dataTransfer.files?.[0] ?? null)
  }

  useEffect(() => {
    fetchCampaigns().then(setCampaigns).catch(() => setCampaigns([]))
  }, [])

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearTimeout(pollRef.current)
    }
  }, [])

  const pollAnalysisStatus = () => {
    fetchAnalysisStatus()
      .then((status) => {
        setAnalysis(status)
        if (status.state === 'running') {
          pollRef.current = window.setTimeout(pollAnalysisStatus, POLL_MS)
        } else {
          // El análisis terminó (o falló): refresca la tabla para mostrar las categorías nuevas.
          onUploaded()
        }
      })
      .catch(() => {
        // Un fallo de red al consultar el estado no debe romper la UI; simplemente se deja de sondear.
      })
  }

  const handleUpload = async () => {
    if (!file || !campanaId) return
    setLoading(true)
    setError(null)
    setAnalysis(null)
    try {
      const r = await uploadFile(file, Number(campanaId))
      setReport(r)
      setFile(null)
      onUploaded()
      pollAnalysisStatus()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  const analyzing = analysis?.state === 'running'
  const progressPct = analysis && analysis.total > 0 ? Math.round((analysis.evaluadas / analysis.total) * 100) : 0

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="btn-primary">
        <Upload size={16} />
        Cargar archivo
      </button>

      <Modal open={open} onClose={() => setOpen(false)} className="w-[520px]">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="m-0 text-base font-bold text-ink">Cargar archivo</h2>
            <p className="mt-1 mb-0 text-[13px] text-ink-2">
              Sube el Excel exportado del bot; las conversaciones nuevas se clasifican automáticamente.
            </p>
          </div>
          <button type="button" onClick={() => setOpen(false)} aria-label="Cerrar" className="btn-icon -mr-1.5 -mt-1">
            <X size={16} />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink-2">Archivo de Excel</span>
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault()
                setDragActive(true)
              }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
              className={`cursor-pointer h-10 border border-dashed rounded-[10px] px-3 flex items-center gap-2 text-[13px] transition-colors ${
                dragActive ? 'border-accent bg-accent-soft' : 'border-line bg-bg hover:border-ink-3'
              }`}
            >
              <FileSpreadsheet size={16} className="text-ink-3 shrink-0" />
              <span className={`truncate ${file ? 'text-ink' : 'text-ink-3'}`}>{file ? file.name : 'Selecciona un .xlsx'}</span>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx"
                onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
                className="hidden"
              />
            </div>
          </div>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink-2">Campaña</span>
            <span className="field relative">
              <Megaphone size={15} className="text-ink-3 shrink-0" />
              <select value={campanaId} onChange={(e) => setCampanaId(e.target.value)} className="pr-5">
                <option value="">Selecciona una campaña…</option>
                {campaigns.map((c) => (
                  <option key={c.id_campana} value={c.id_campana}>
                    {c.nombre_campana}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 text-ink-3 pointer-events-none" />
            </span>
          </label>
        </div>

        <button
          type="button"
          onClick={handleUpload}
          disabled={!file || !campanaId || loading}
          className="btn-primary mt-4 w-full"
        >
          <Upload size={15} />
          {loading ? 'Cargando…' : 'Cargar archivo'}
        </button>

        {error && <p className="text-[13px] text-bad-fg mt-2.5">{error}</p>}

        {report && (
          <div className="mt-4 pt-4 border-t border-line-soft text-[13px]">
            <div className="mb-3">
              <Badge tone={report.status === 'COMPLETED' ? 'ok' : 'warn'}>{report.status}</Badge>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-line-soft border border-line-soft rounded-xl overflow-hidden">
              {[
                ['Filas recibidas', report.rows_received],
                ['Conversaciones nuevas', report.conversations_created],
                ['Mensajes nuevos', report.messages_created],
                ['Errores', report.rows_error],
              ].map(([label, n]) => (
                <div key={label} className="bg-bg px-3 py-2.5">
                  <div className="text-[11px] text-ink-3">{label}</div>
                  <div className="text-[15px] font-bold text-ink tabular-nums">{formatNumber(Number(n))}</div>
                </div>
              ))}
            </div>
            {report.warnings.length > 0 && (
              <details className="mt-3 text-xs text-ink-2">
                <summary className="cursor-pointer">{report.warnings.length} advertencia(s) de calidad de datos</summary>
                <ul className="list-disc pl-4 mt-1.5 space-y-0.5">
                  {report.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}

        {analysis && (analyzing || analysis.state === 'error') && (
          <div className="mt-4 pt-4 border-t border-line-soft text-[13px]">
            {analyzing && (
              <>
                <div className="flex items-center justify-between text-xs text-ink-2 mb-1.5">
                  <span>
                    Clasificando conversaciones… {analysis.total > 0 ? `${analysis.evaluadas}/${analysis.total}` : ''}
                  </span>
                  <span className="tabular-nums">{analysis.total > 0 ? `${progressPct}%` : ''}</span>
                </div>
                <div className="w-full h-1.5 bg-surface-2 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-accent rounded-full"
                    animate={{ width: `${analysis.total > 0 ? progressPct : 5}%` }}
                    transition={springSettle}
                  />
                </div>
                {analysis.resueltas_por_ia > 0 && (
                  <p className="text-xs text-ink-3 mt-1.5 mb-0">
                    {analysis.resueltas_por_regla} por reglas · {analysis.resueltas_por_ia} por IA
                  </p>
                )}
              </>
            )}
            {analysis.state === 'error' && (
              <p className="text-[13px] text-bad-fg m-0">La clasificación falló: {analysis.error_message}</p>
            )}
          </div>
        )}

        {analysis && analysis.state === 'done' && (
          <p className="text-xs text-ok-fg mt-4 pt-4 mb-0 border-t border-line-soft">
            Clasificación automática terminada: {analysis.evaluadas} conversaciones analizadas
            {analysis.resueltas_por_ia > 0 ? ` (${analysis.resueltas_por_ia} por IA)` : ''}.
          </p>
        )}
      </Modal>
    </>
  )
}
