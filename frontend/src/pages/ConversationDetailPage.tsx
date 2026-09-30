import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchConversationDetail, type ConversationTranscript } from '../api/client'
import CategoryBadge from '../components/CategoryBadge'
import { formatDateAndTime, formatDateTime } from '../lib/format'

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
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the conversation'))
  }, [sessionId])

  return (
    <div>
      <Link to="/" className="text-sm text-[var(--wa-green-dark)] underline mb-4 inline-block">
        ← Back to search
      </Link>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {!error && !transcript && <p className="text-sm text-gray-400">Loading...</p>}

      {transcript && (
        <div className="max-w-xl mx-auto rounded-xl overflow-hidden shadow-lg">
          <div className="bg-[var(--wa-green-dark)] text-white px-4 py-3 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[var(--wa-green-light)] flex items-center justify-center font-bold flex-shrink-0">
              {(transcript.customer_name ?? '?')[0]?.toUpperCase()}
            </div>
            <div>
              <div className="font-semibold text-sm">
                {transcript.customer_name ?? transcript.customer_phone ?? 'Client'}
              </div>
              <div className="text-xs opacity-80">
                {transcript.customer_phone ?? '-'} · {formatDateTime(transcript.started_at)} →{' '}
                {formatDateTime(transcript.ended_at)} · {transcript.conn_id_count} segment(s)
              </div>
            </div>
          </div>

          {transcript.categoria && (
            <div className="bg-white px-4 py-3 border-t border-gray-100 flex items-center gap-3 flex-wrap">
              <CategoryBadge categoria={transcript.categoria} />
              <span className="text-xs text-gray-400">
                {transcript.metodo === 'RULE' ? 'classified by rules' : 'classified by AI'}
              </span>
              {transcript.justificacion && (
                <div className="basis-full text-xs text-gray-500 italic">{transcript.justificacion}</div>
              )}
            </div>
          )}

          <div className="bg-[var(--wa-chat-bg)] p-4 flex flex-col gap-1.5 max-h-[640px] overflow-y-auto">
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
                    className={`max-w-[78%] min-w-[104px] rounded-lg px-2.5 pt-1.5 pb-5 relative text-sm shadow-sm whitespace-pre-wrap break-words ${
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
        </div>
      )}
    </div>
  )
}
