import type { LucideIcon } from 'lucide-react'
import AccountCluster from './AccountCluster'

interface Props {
  icon: LucideIcon
  title: string
  subtitle?: string
}

export default function PageHeader({ icon: Icon, title, subtitle }: Props) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div className="flex items-start gap-3">
        <Icon className="text-gray-400 mt-0.5" size={26} strokeWidth={1.75} />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--ink-1)]">{title}</h1>
          {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      <AccountCluster />
    </div>
  )
}
