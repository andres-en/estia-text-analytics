import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import { Check, Copy, ListChecks, Maximize2, MessageCircle, X } from 'lucide-react'
import { fetchConversationDetail, type ConversationTranscript } from '../api/client'
import CategoryBadge from './CategoryBadge'
import ChatTranscript from './ChatTranscript'
import SegmentedControl from './SegmentedControl'
import { formatDate, formatDateTime, formatPhone, formatTime, initials } from '../lib/format'
import { displayName, metodoLabel } from '../lib/conversation'
import { slideFromRight, springDrawer } from '../lib/motionPresets'

type Tab = 'conversacion' | 'clasificacion' | 'informacion'

const TABS: { value: Tab; label: string }[] = [
  { value: 'conversacion', label: 'Conversación' },
  { value: 'clasificacion', label: 'Clasificación' },
  { value: 'informacion', label: 'Información' },
]

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      title="Copiar teléfono"
      onClick={() => {
        navigator.clipboard
          ?.writeText(text)
          .then(() => {
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1200)
          })
          .catch(() => {})
      }}
      className="p-0.5 rounded text-ink-3 hover:text-accent hover:bg-accent-soft flex"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  )
}

function InfoCell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="bg-bg px-3 py-2.5 min-w-0">
      <div className="text-[11px] text-ink-3 mb-1">{label}</div>
      {children}
    </div>
  )
}

export default function ConversationSidePanel({
  sessionId,
  onClose,
  overlay = false,
}: {
  sessionId: string
  onClose: () => void
  /** En pantallas angostas el panel flota sobre la tabla como un cajón en vez de empujarla. */
  overlay?: boolean
}) {
  const [transcript, setTranscript] = useState<ConversationTranscript | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('conversacion')

  useEffect(() => {
    let cancelled = false
    setTranscript(null)
    setError(null)
    setTab('conversacion')
    fetchConversationDetail(sessionId)
      .then((t) => {
        if (!cancelled) setTranscript(t)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'No se pudo cargar la conversación')
      })
    return () => {
      cancelled = true
    }
  }, [sessionId])

  const name = transcript ? displayName(transcript) : '…'
  const indicadoresActivos = transcript ? transcript.indicadores.filter((i) => i.valor) : []
  const iniciadaPor = transcript?.iniciada_por === 'BOT' ? 'Bot' : 'Cliente'

  return (
    <motion.aside
      initial={slideFromRight.initial}
      animate={slideFromRight.animate}
      exit={slideFromRight.exit}
      transition={springDrawer}
      className={`w-[440px] max-w-[calc(100%-24px)] shrink-0 flex flex-col bg-surface border border-line-soft rounded-2xl overflow-hidden ${
        overlay ? 'absolute top-0 right-0 bottom-0 z-10 shadow-[var(--shadow-lg),0_0_0_1px_var(--border-soft)]' : 'relative shadow-card'
      }`}
    >
      <div className="px-[18px] pt-[18px] pb-3.5 flex flex-col gap-3.5 border-b border-line-soft">
        <div className="flex items-start gap-3">
          <div className="relative shrink-0">
            <div className="w-12 h-12 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center text-[17px] font-bold">
              {transcript ? initials(name, 1) : ''}
            </div>
            <span className="absolute -right-0.5 -bottom-0.5 w-[18px] h-[18px] rounded-full bg-[#25d366] border-2 border-surface flex items-center justify-center">
              <MessageCircle size={9} strokeWidth={3} className="text-white" />
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-base font-bold text-ink tracking-[-.01em] truncate">{name}</div>
            <div className="flex items-center gap-1.5 mt-[3px] text-[13px] text-ink-2 tabular-nums">
              {formatPhone(transcript?.customer_phone ?? null)}
              {transcript?.customer_phone && <CopyButton text={transcript.customer_phone} />}
            </div>
          </div>
          <div className="flex gap-1">
            <Link
              to={`/conversations/${encodeURIComponent(sessionId)}`}
              title="Abrir en página completa"
              className="btn-icon"
            >
              <Maximize2 size={15} />
            </Link>
            <button type="button" onClick={onClose} title="Cerrar" className="btn-icon">
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-px bg-line-soft border border-line-soft rounded-xl overflow-hidden">
          <InfoCell label="Categoría">
            {transcript ? <CategoryBadge categoria={transcript.categoria} size="sm" /> : <span className="text-xs text-ink-3">—</span>}
          </InfoCell>
          <InfoCell label="Inicio">
            <div className="text-[12.5px] font-semibold text-ink whitespace-nowrap">
              {transcript ? formatDate(transcript.started_at) : '—'}
            </div>
            <div className="text-[11.5px] text-ink-2">{transcript ? formatTime(transcript.started_at) : ''}</div>
          </InfoCell>
          <InfoCell label="Mensajes">
            <div className="text-[12.5px] font-semibold text-ink">{transcript?.messages.length ?? '—'}</div>
            <div className="text-[11.5px] text-ink-2">{transcript ? `Inició: ${iniciadaPor}` : ''}</div>
          </InfoCell>
        </div>

        <SegmentedControl options={TABS} value={tab} onChange={setTab} />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto bg-surface">
        {error && <p className="text-[13px] text-bad-fg p-[18px]">{error}</p>}
        {!error && !transcript && <p className="text-[13px] text-ink-3 p-[18px]">Cargando…</p>}

        {transcript && tab === 'conversacion' && <ChatTranscript messages={transcript.messages} customerName={name} />}

        {transcript && tab === 'clasificacion' && (
          <div className="p-[18px] flex flex-col gap-4 animate-estia-fade">
            <div className="flex flex-col gap-2.5 p-4 border border-line-soft rounded-xl bg-bg">
              <div className="flex items-center gap-2 flex-wrap">
                <CategoryBadge categoria={transcript.categoria} size="lg" />
                {transcript.subcategoria_label && (
                  <span className="inline-block px-2.5 py-1 rounded-lg bg-surface border border-line-soft text-ink-2 text-xs font-medium">
                    {transcript.subcategoria_label}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5 text-xs text-ink-2">
                <ListChecks size={14} className="text-accent" />
                {metodoLabel(transcript.metodo)}
              </div>
            </div>
            {transcript.justificacion && (
              <div>
                <div className="eyebrow mb-2">Justificación</div>
                <p className="m-0 text-[13.5px] leading-[1.65] text-ink-2 [text-wrap:pretty]">{transcript.justificacion}</p>
              </div>
            )}
            <div>
              <div className="eyebrow mb-2">Señales de clasificación</div>
              <div className="flex flex-wrap gap-1.5">
                {indicadoresActivos.length === 0 && <span className="text-xs text-ink-3">Sin señales</span>}
                {indicadoresActivos.map((i) => (
                  <span
                    key={i.id}
                    className="inline-flex items-center gap-1.5 px-[11px] py-[5px] rounded-full bg-surface-2 text-ink-2 text-xs font-medium"
                  >
                    <Check size={12} strokeWidth={2.5} className="text-accent" />
                    {i.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {transcript && tab === 'informacion' && (
          <div className="p-[18px] flex flex-col gap-0.5 animate-estia-fade">
            {[
              { k: 'SESSION_ID', v: transcript.session_id, mono: true },
              { k: 'Teléfono', v: transcript.customer_phone ?? '—' },
              { k: 'Nombre', v: transcript.customer_name ?? '—' },
              { k: 'Inicio', v: formatDateTime(transcript.started_at) },
              { k: 'Fin', v: formatDateTime(transcript.ended_at) },
              { k: 'Segmentos', v: String(transcript.conn_id_count) },
            ].map((row) => (
              <div key={row.k} className="grid grid-cols-[120px_minmax(0,1fr)] gap-3 py-3 border-b border-line-soft items-baseline">
                <div className="text-xs text-ink-3">{row.k}</div>
                <div className={`text-[13px] text-ink font-medium break-all ${row.mono ? 'font-mono' : ''}`}>{row.v}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.aside>
  )
}
