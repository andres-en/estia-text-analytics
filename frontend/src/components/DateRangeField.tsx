import { Calendar } from 'lucide-react'

interface Props {
  desde: string
  hasta: string
  onChange: (patch: { desde?: string; hasta?: string }) => void
  className?: string
}

// Ancho fijo para que el input nativo (texto + ícono de calendario) nunca se
// monte sobre la etiqueta vecina cuando el campo se encoge.
const inputClass = 'w-[124px] shrink-0 border-0 outline-0 bg-transparent text-[13px] text-ink'

/** "Desde | Hasta" en un solo campo píldora, con inputs de fecha nativos sin borde. */
export default function DateRangeField({ desde, hasta, onChange, className }: Props) {
  return (
    <div
      className={`flex items-center h-10 rounded-[10px] border border-line bg-bg box-border overflow-hidden focus-within:border-accent transition-colors ${
        className ?? ''
      }`}
    >
      <label className="flex-1 flex items-center gap-2 px-3 h-full">
        <Calendar size={15} className="text-ink-3 shrink-0" strokeWidth={2} />
        <span className="text-xs text-ink-3">Desde</span>
        <input
          type="date"
          value={desde}
          max={hasta || undefined}
          onChange={(e) => onChange({ desde: e.target.value })}
          className={inputClass}
        />
      </label>
      <span className="w-px h-5 bg-line shrink-0" />
      <label className="flex-1 flex items-center gap-2 px-3 h-full">
        <span className="text-xs text-ink-3">Hasta</span>
        <input
          type="date"
          value={hasta}
          min={desde || undefined}
          onChange={(e) => onChange({ hasta: e.target.value })}
          className={inputClass}
        />
      </label>
    </div>
  )
}
