import type { ReactNode } from 'react'

interface Props {
  checked: boolean
  onChange: (checked: boolean) => void
  children: ReactNode
  size?: 'sm' | 'md'
  className?: string
}

/** Botón con interruptor deslizante a la izquierda ("Contiene Array", "Incluir No aplica"). */
export default function Switch({ checked, onChange, children, size = 'md', className }: Props) {
  const sm = size === 'sm'
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`flex items-center gap-2 border border-line bg-bg text-ink-2 hover:border-ink-3 transition-colors whitespace-nowrap ${
        sm ? 'h-8 px-2.5 rounded-lg text-xs' : 'h-10 px-3 rounded-[10px] text-[13px]'
      } ${className ?? ''}`}
    >
      <span
        className={`relative shrink-0 rounded-full transition-colors duration-150 ${checked ? 'bg-accent' : 'bg-line'} ${
          sm ? 'w-[26px] h-[15px]' : 'w-7 h-4'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 rounded-full bg-white shadow-[0_1px_2px_rgba(0,0,0,.2)] transition-transform duration-[180ms] ease-[cubic-bezier(.2,.8,.2,1)] ${
            sm ? 'w-[11px] h-[11px]' : 'w-3 h-3'
          }`}
          style={{ transform: checked ? `translateX(${sm ? 11 : 12}px)` : 'none' }}
        />
      </span>
      {children}
    </button>
  )
}
