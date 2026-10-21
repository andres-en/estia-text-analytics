import { Bot, CheckCheck } from 'lucide-react'
import type { TranscriptMessage } from '../api/client'
import { formatDayMonth, formatTime } from '../lib/format'

/**
 * Flujo de la conversación: el cliente a la izquierda en gris claro, el bot a
 * la derecha en el azul de la marca, eventos del sistema como separadores.
 * El nombre del emisor solo aparece cuando cambia de turno, y cada cambio de
 * día abre con una etiqueta de fecha.
 */
export default function ChatTranscript({ messages, customerName }: { messages: TranscriptMessage[]; customerName: string }) {
  const firstName = customerName.split(/\s+/)[0] || customerName

  return (
    <div className="px-[18px] pt-4 pb-6 flex flex-col gap-1">
      {messages.map((m, i) => {
        const prev = messages[i - 1]
        const date = new Date(m.timestamp)
        const newDay = !prev || new Date(prev.timestamp).toDateString() !== date.toDateString()
        const turnChange = !prev || prev.sender !== m.sender || newDay
        const time = formatTime(date)
        const marginTop = i === 0 || newDay ? 0 : turnChange ? 14 : 2

        return (
          <div key={m.sequence_number} className="flex flex-col">
            {newDay && (
              <div
                className={`self-center text-[11px] font-medium text-ink-3 bg-bg border border-line-soft rounded-full px-3 py-[3px] mb-2.5 ${
                  i === 0 ? '' : 'mt-4'
                }`}
              >
                {formatDayMonth(date)} {date.getFullYear()}
              </div>
            )}

            {m.sender === 'SYSTEM' ? (
              <div className="flex items-center gap-2.5 mt-3.5 mb-1 text-[11px] text-ink-3">
                <span className="flex-1 h-px bg-line-soft" />
                <span className="text-center">
                  {m.message} · {time}
                </span>
                <span className="flex-1 h-px bg-line-soft" />
              </div>
            ) : m.sender === 'BOT' ? (
              <div className="flex flex-col items-end animate-estia-fade" style={{ marginTop }}>
                {turnChange && (
                  <div className="flex items-center gap-[5px] text-[11px] font-semibold text-accent-ink mr-1 mb-1">
                    <Bot size={12} />
                    Asistente
                  </div>
                )}
                <div className="max-w-[82%] bg-accent text-white rounded-[18px_18px_6px_18px] px-3.5 py-2.5 text-[13.5px] leading-[1.6] whitespace-pre-wrap break-words shadow-[0_4px_12px_-6px_rgba(29,111,242,.5)]">
                  {m.message}
                </div>
                <div className="flex items-center gap-1 text-[10.5px] text-ink-3 mt-[3px] mr-1.5">
                  {time}
                  <CheckCheck size={13} className="text-accent" />
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-start animate-estia-fade" style={{ marginTop }}>
                {turnChange && <div className="text-[11px] font-semibold text-ink-2 ml-1 mb-1">{firstName}</div>}
                <div className="max-w-[82%] bg-[var(--bubble-in)] text-ink rounded-[18px_18px_18px_6px] px-3.5 py-2.5 text-[13.5px] leading-[1.6] whitespace-pre-wrap break-words">
                  {m.message}
                </div>
                <div className="text-[10.5px] text-ink-3 mt-[3px] ml-1.5">{time}</div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
