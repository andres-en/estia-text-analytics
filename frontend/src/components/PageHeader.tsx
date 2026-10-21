import type { ReactNode } from 'react'
import AccountCluster from './AccountCluster'

interface Props {
  title: string
  subtitle?: ReactNode
  /** Botones propios de la página (exportar, cargar archivo…), a la izquierda del cliente activo. */
  actions?: ReactNode
}

export default function PageHeader({ title, subtitle, actions }: Props) {
  return (
    <header className="flex items-center justify-between gap-4 flex-wrap">
      <div className="min-w-0">
        <h1 className="m-0 text-2xl font-bold tracking-[-.02em] text-ink">{title}</h1>
        {subtitle && <div className="mt-1 text-[13px] text-ink-2">{subtitle}</div>}
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        {actions && (
          <>
            {actions}
            <span className="w-px h-6 bg-line mx-1.5" />
          </>
        )}
        <AccountCluster />
      </div>
    </header>
  )
}
