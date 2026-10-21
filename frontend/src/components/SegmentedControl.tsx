import type { CSSProperties } from 'react'

interface Option<T extends string> {
  value: T
  label: string
}

interface Props<T extends string> {
  options: Option<T>[]
  /** Si no coincide con ninguna opción (ej. rango personalizado), no se resalta ninguna. */
  value: T | null
  onChange: (value: T) => void
  size?: 'md' | 'lg'
  className?: string
  style?: CSSProperties
}

/**
 * Selector de pestañas con un fondo blanco que se desliza a la opción activa
 * (rango del dashboard, pestañas del panel de conversación y de Configuración).
 * Todas las opciones miden lo mismo, así el indicador se mueve con un simple
 * translateX en vez de medir el DOM.
 */
export default function SegmentedControl<T extends string>({ options, value, onChange, size = 'md', className, style }: Props<T>) {
  const index = options.findIndex((o) => o.value === value)
  const n = options.length
  const lg = size === 'lg'

  return (
    <div
      role="tablist"
      className={`relative grid p-1 bg-surface-2 box-border ${lg ? 'rounded-xl' : 'rounded-[10px]'} ${className ?? ''}`}
      style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))`, ...style }}
    >
      {index >= 0 && (
        <span
          aria-hidden
          className={`absolute top-1 bottom-1 left-1 bg-surface shadow-[0_1px_2px_rgba(15,23,42,.08),0_1px_1px_rgba(15,23,42,.04)] transition-transform duration-[280ms] ease-[cubic-bezier(.2,.8,.2,1)] ${
            lg ? 'rounded-[9px]' : 'rounded-[7px]'
          }`}
          style={{ width: `calc((100% - 8px) / ${n})`, transform: `translateX(${index * 100}%)` }}
        />
      )}
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={`relative z-[1] px-2 text-[13px] whitespace-nowrap transition-colors duration-150 hover:text-ink ${
              lg ? 'h-9' : 'h-8'
            } ${active ? 'font-semibold text-ink' : 'font-medium text-ink-3'}`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
