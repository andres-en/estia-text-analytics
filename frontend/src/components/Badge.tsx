import type { ReactNode } from 'react'

export type BadgeTone = 'ok' | 'bad' | 'warn' | 'mute' | 'accent'

const TONE: Record<BadgeTone, string> = {
  ok: 'bg-ok-bg text-ok-fg',
  bad: 'bg-bad-bg text-bad-fg',
  warn: 'bg-warn-bg text-warn-fg',
  mute: 'bg-mute-bg text-mute-fg',
  accent: 'bg-accent-soft text-accent-ink',
}

/** Etiqueta redondeada de fondo translúcido con punto de color (estado, rol). */
export default function Badge({ tone, children, dot = true }: { tone: BadgeTone; children: ReactNode; dot?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 h-6 px-2.5 rounded-full text-xs font-semibold whitespace-nowrap ${TONE[tone]}`}
    >
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
      {children}
    </span>
  )
}
