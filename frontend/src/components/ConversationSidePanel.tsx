import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { X, Calendar, MessageCircle } from 'lucide-react'
import { fetchConversationDetail, type ConversationTranscript } from '../api/client'
import CategoryBadge from './CategoryBadge'
import AnimatedTabUnderline from './AnimatedTabUnderline'
import { formatDateAndTime, formatDateTime } from '../lib/format'
import { slideFromRight, springDrawer } from '../lib/motionPresets'

type Tab = 'conversacion' | 'clasificacion' | 'informacion'

const TABS: { id: Tab; label: string }[] = [
  { id: 'conversacion', label: 'Conversation' },
  { id: 'clasificacion', label: 'Classification' },
  { id: 'informacion', label: 'Details' },
]

export default function ConversationSidePanel({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
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
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load the conversation')
      })
    return () => {
      cancelled = true
    }
  }, [sessionId])

  const displayName = transcript?.customer_name ?? transcript?.customer_phone ?? 'Client'
  const indicadoresActivos = transcript ? transcript.indicadores.filter((i) => i.valor) : []

  return (
    <motion.aside
      initial={slideFromRight.initial}
      animate={slideFromRight.animate}
      exit={slideFromRight.exit}
      transition={springDrawer}
      className="surface overflow-hidden w-full lg:w-[420px] xl:w-[460px] flex-shrink-0 flex flex-col max-h-[calc(100vh-140px)] sticky top-6"
    >
      <div className="px-4 py-3 border-b border-gray-100 flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-[var(--wa-green-light)] text-white flex items-center justify-center font-bold flex-shrink-0">
          {displayName[0]?.toUpperCase() ?? '?'}
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-sm text-gray-800 truncate">{displayName}</div>
          <div className="text-xs text-gray-500 truncate">{transcript?.customer_phone ?? '-'}</div>
        </div>
        {transcript?.categoria !== undefined && transcript && (
          <div className="flex-shrink-0">
            <CategoryBadge categoria={transcript.categoria} />
          </div>
        )}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="text-gray-400 hover:text-gray-600 flex-shrink-0"
        >
          <X size={18} />
        </button>
      </div>

      {transcript && (
        <div className="px-4 py-2 border-b border-gray-100 flex items-center gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <Calendar size={13} />
            {formatDateTime(transcript.started_at)}
          </span>
          <span className="flex items-center gap-1">
            <MessageCircle size={13} />
            {transcript.messages.length} mensajes
          </span>
        </div>
      )}

      <div className="px-4 border-b border-gray-100 flex gap-4 text-sm">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`relative py-2 -mb-px transition-colors ${
              tab === t.id ? 'text-[var(--wa-green-dark)] font-semibold' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
            {tab === t.id && (
              <AnimatedTabUnderline
                layoutId="side-panel-tab-underline"
                className="absolute left-0 right-0 -bottom-[1px] h-[2px] bg-[var(--wa-green-dark)] rounded-full"
              />
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {error && <p className="text-sm text-red-600 p-4">{error}</p>}
        {!error && !transcript && <p className="text-sm text-gray-400 p-4">Loading...</p>}

        {transcript && tab === 'conversacion' && (
          <div className="bg-[var(--wa-chat-bg)] p-3 flex flex-col gap-1.5 min-h-full">
            {transcript.messages.map((m) => {
              if (m.sender === 'SYSTEM') {
                return (
                  <div
                    key={m.sequence_number}
                    className="self-center bg-[#fef6d8] text-[#7a6a2f] text-xs px-3 py-1 rounded-lg my-1.5"
                  >
                    {m.message} · {formatDateAndTime(m.timestamp)}
                  </div>
                )
              }
              const outgoing = m.sender === 'BOT'
              return (
                <div key={m.sequence_number} className={`flex ${outgoing ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] min-w-[104px] rounded-lg px-2.5 pt-1.5 pb-5 relative text-sm shadow-sm whitespace-pre-wrap break-words ${
                      outgoing ? 'bg-[var(--wa-bubble-out)] rounded-tr-sm' : 'bg-[var(--wa-bubble-in)] rounded-tl-sm'
                    }`}
                  >
                    {m.message}
                    <span className="absolute bottom-1 right-2.5 text-[10px] text-gray-400 whitespace-nowrap">
                      {formatDateAndTime(m.timestamp)}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {transcript && tab === 'clasificacion' && (
          <div className="p-4 text-sm space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <CategoryBadge categoria={transcript.categoria} />
              {transcript.subcategoria_label && (
                <span className="text-xs rounded-full bg-gray-100 text-gray-700 px-2 py-0.5">
                  {transcript.subcategoria_label}
                </span>
              )}
              {transcript.metodo && (
                <span className="text-xs text-gray-400">
                  {transcript.metodo === 'RULE' ? 'classified by rules' : 'classified by AI'}
                </span>
              )}
            </div>
            {transcript.justificacion && (
              <div className="text-xs text-gray-600 italic bg-gray-50 rounded-lg p-3">{transcript.justificacion}</div>
            )}
            <div>
              <div className="text-xs font-semibold text-gray-500 mb-2">Classification signals</div>
              <div className="flex flex-wrap gap-2">
                {indicadoresActivos.length === 0 && <span className="text-gray-400 text-xs">No signals</span>}
                {indicadoresActivos.map((i) => (
                  <span key={i.id} className="text-xs bg-gray-100 border border-gray-200 rounded-full px-2 py-0.5 text-gray-600">
                    {i.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {transcript && tab === 'informacion' && (
          <div className="p-4 text-sm space-y-3">
            <div>
              <div className="text-xs text-gray-500">SESSION_ID</div>
              <div className="font-mono text-xs text-gray-700 break-all">{transcript.session_id}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Phone</div>
              <div className="text-gray-700">{transcript.customer_phone ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Name</div>
              <div className="text-gray-700">{transcript.customer_name ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Start</div>
              <div className="text-gray-700">{formatDateTime(transcript.started_at)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">End</div>
              <div className="text-gray-700">{formatDateTime(transcript.ended_at)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Segments</div>
              <div className="text-gray-700">{transcript.conn_id_count}</div>
            </div>
          </div>
        )}
      </div>
    </motion.aside>
  )
}
