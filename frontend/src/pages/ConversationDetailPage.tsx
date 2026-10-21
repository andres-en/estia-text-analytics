import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, ListChecks } from 'lucide-react'
import { fetchConversationDetail, type ConversationTranscript } from '../api/client'
import CategoryBadge from '../components/CategoryBadge'
import ChatTranscript from '../components/ChatTranscript'
import { formatDateTime, formatPhone, initials } from '../lib/format'
import { displayName, metodoLabel } from '../lib/conversation'

export default function ConversationDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [transcript, setTranscript] = useState<ConversationTranscript | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) return
    setTranscript(null)
    setError(null)
    fetchConversationDetail(sessionId)
      .then(setTranscript)
      .catch((e) => setError(e instanceof Error ? e.message : 'No se pudo cargar la conversación'))
  }, [sessionId])

  const name = transcript ? displayName(transcript) : ''

  return (
    <div className="px-7 py-6 box-border">
      <Link to="/" className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-2 hover:text-ink mb-4">
        <ArrowLeft size={15} />
        Volver a conversaciones
      </Link>

      {error && <p className="text-[13px] text-bad-fg">{error}</p>}
      {!error && !transcript && <p className="text-[13px] text-ink-3">Cargando…</p>}

      {transcript && (
        <div className="max-w-2xl mx-auto surface overflow-hidden">
          <div className="px-5 py-4 border-b border-line-soft flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center text-[17px] font-bold shrink-0">
              {initials(name, 1)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-base font-bold text-ink truncate">{name}</div>
              <div className="text-xs text-ink-2">
                {formatPhone(transcript.customer_phone)} · {formatDateTime(transcript.started_at)} →{' '}
                {formatDateTime(transcript.ended_at)} · {transcript.conn_id_count} segmento(s)
              </div>
            </div>
          </div>

          {transcript.categoria && (
            <div className="px-5 py-3 border-b border-line-soft flex items-center gap-3 flex-wrap bg-bg">
              <CategoryBadge categoria={transcript.categoria} />
              <span className="flex items-center gap-1.5 text-xs text-ink-2">
                <ListChecks size={14} className="text-accent" />
                {metodoLabel(transcript.metodo)}
              </span>
              {transcript.justificacion && (
                <p className="basis-full m-0 text-[13px] leading-[1.6] text-ink-2">{transcript.justificacion}</p>
              )}
            </div>
          )}

          <ChatTranscript messages={transcript.messages} customerName={name} />
        </div>
      )}
    </div>
  )
}
