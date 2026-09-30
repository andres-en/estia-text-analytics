import { useEffect, useRef, useState, type DragEvent } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, FileSpreadsheet, Megaphone, Upload, X } from 'lucide-react'
import {
  fetchAnalysisStatus,
  fetchCampaigns,
  uploadFile,
  type AnalysisStatus,
  type Campaign,
  type ImportReport,
} from '../api/client'
import { materialize, springDrawer, springSettle } from '../lib/motionPresets'

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
      setError('The file must be an .xlsx')
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
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const analyzing = analysis?.state === 'running'
  const progressPct = analysis && analysis.total > 0 ? Math.round((analysis.evaluadas / analysis.total) * 100) : 0

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="btn-primary text-sm px-4 py-2 flex-shrink-0"
      >
        <Upload size={16} />
        Upload file
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={springSettle}
            className="fixed inset-0 bg-black/40 backdrop-blur-[2px] flex items-center justify-center z-50 p-4"
            onClick={() => setOpen(false)}
          >
            <motion.div
              initial={materialize.initial}
              animate={materialize.animate}
              exit={materialize.exit}
              transition={springDrawer}
              className="surface p-5 w-full max-w-lg max-h-[85vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-[var(--wa-green-dark)]">Upload file</h2>
              <button type="button" onClick={() => setOpen(false)} aria-label="Close" className="text-gray-400 hover:text-gray-600">
                <X size={18} />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  Excel file
                </label>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault()
                    setDragActive(true)
                  }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={handleDrop}
                  className={`cursor-pointer border-2 border-dashed rounded-lg px-3 py-2.5 flex items-center gap-2 text-sm transition-colors ${
                    dragActive
                      ? 'border-[var(--wa-green)] bg-[var(--wa-green)]/5'
                      : 'border-gray-300 hover:border-gray-400 bg-gray-50/50'
                  }`}
                >
                  <FileSpreadsheet size={18} className="text-gray-400 flex-shrink-0" />
                  <span className={`truncate ${file ? 'text-gray-700' : 'text-gray-400'}`}>
                    {file ? file.name : 'Select an .xlsx file'}
                  </span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx"
                    onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
                    className="hidden"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  Campaign
                </label>
                <div className="relative">
                  <Megaphone size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                  <select
                    value={campanaId}
                    onChange={(e) => setCampanaId(e.target.value)}
                    className="w-full appearance-none border border-gray-300 rounded-lg pl-9 pr-8 py-2.5 text-sm text-gray-700 cursor-pointer hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-[var(--wa-green)]/30 transition-colors"
                  >
                    <option value="">Select a campaign...</option>
                    {campaigns.map((c) => (
                      <option key={c.id_campana} value={c.id_campana}>
                        {c.nombre_campana}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                </div>
              </div>
            </div>

            <button
              onClick={handleUpload}
              disabled={!file || !campanaId || loading}
              className="btn-primary mt-3 w-full text-sm px-4 py-2"
            >
              {loading ? 'Loading...' : 'Upload file'}
            </button>

            {error && <p className="text-sm text-red-600 mt-2">{error}</p>}

            {report && (
              <div className="mt-3 text-sm border-t border-gray-200 pt-3">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold mb-2 ${
                    report.status === 'COMPLETED' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                  }`}
                >
                  {report.status}
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-gray-700">
                  <div>
                    Rows received: <b>{report.rows_received}</b>
                  </div>
                  <div>
                    New conversations: <b>{report.conversations_created}</b>
                  </div>
                  <div>
                    New messages: <b>{report.messages_created}</b>
                  </div>
                  <div>
                    Errors: <b>{report.rows_error}</b>
                  </div>
                </div>
                {report.warnings.length > 0 && (
                  <details className="mt-2 text-xs text-gray-500">
                    <summary className="cursor-pointer">{report.warnings.length} data-quality warning(s)</summary>
                    <ul className="list-disc pl-4 mt-1">
                      {report.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            )}

            {analysis && (analyzing || analysis.state === 'error') && (
              <div className="mt-3 text-sm border-t border-gray-200 pt-3">
                {analyzing && (
                  <>
                    <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                      <span>
                        Classifying conversations...{' '}
                        {analysis.total > 0 ? `${analysis.evaluadas}/${analysis.total}` : ''}
                      </span>
                      <span>{analysis.total > 0 ? `${progressPct}%` : ''}</span>
                    </div>
                    <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-[var(--wa-green)]"
                        animate={{ width: `${analysis.total > 0 ? progressPct : 5}%` }}
                        transition={springSettle}
                      />
                    </div>
                    {analysis.resueltas_por_ia > 0 && (
                      <p className="text-xs text-gray-400 mt-1">
                        {analysis.resueltas_por_regla} by rules · {analysis.resueltas_por_ia} by AI
                      </p>
                    )}
                  </>
                )}
                {analysis.state === 'error' && (
                  <p className="text-sm text-red-600">Classification failed: {analysis.error_message}</p>
                )}
              </div>
            )}

            {analysis && analysis.state === 'done' && (
              <p className="text-xs text-emerald-600 mt-3 border-t border-gray-200 pt-3">
                Automatic classification finished: {analysis.evaluadas} conversations analyzed
                {analysis.resueltas_por_ia > 0 ? ` (${analysis.resueltas_por_ia} by AI)` : ''}.
              </p>
            )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
