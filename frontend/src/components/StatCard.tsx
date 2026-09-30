import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import { Minus, TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react'
import type { Trend } from '../lib/trend'
import { springPress } from '../lib/motionPresets'

interface Props {
  label: string
  value: number
  hint?: string
  to?: string
  icon: LucideIcon
  accentColor: string
  trend?: Trend | null
  /** Si el indicador sube, ¿es una buena o mala señal? Define el color del badge. */
  goodDirection?: 'up' | 'down'
}

export default function StatCard({
  label,
  value,
  hint,
  to,
  icon: Icon,
  accentColor,
  trend,
  goodDirection = 'up',
}: Props) {
  const trendColor =
    !trend || trend.direction === 'flat'
      ? 'text-gray-400'
      : trend.direction === 'new'
        ? 'text-gray-500'
        : trend.direction === goodDirection
          ? 'text-emerald-600'
          : 'text-red-600'

  const TrendIcon = !trend || trend.direction === 'flat' ? Minus : trend.direction === 'down' ? TrendingDown : TrendingUp

  const content = (
    <>
      <div
        className="w-11 h-11 rounded-full flex items-center justify-center mb-3"
        style={{ backgroundColor: `${accentColor}1a`, color: accentColor }}
      >
        <Icon size={22} strokeWidth={2} />
      </div>
      <div className="text-3xl font-semibold text-gray-800 tabular-nums">{value.toLocaleString('en-US')}</div>
      <div className="text-sm font-medium text-gray-700 mt-1">{label}</div>
      {hint && <div className="text-xs text-gray-400 mt-0.5">{hint}</div>}
      {trend && (
        <div className={`flex items-center gap-1 text-xs mt-3 ${trendColor}`}>
          <TrendIcon size={13} strokeWidth={2.5} />
          <span>{trend.label}</span>
        </div>
      )}
    </>
  )

  const cardClass = 'surface p-4 border-l-4'

  if (to) {
    return (
      <Link to={to} className="block" style={{ borderLeftColor: accentColor }}>
        <motion.div
          className={cardClass}
          style={{ borderLeftColor: accentColor }}
          whileHover={{ scale: 1.015 }}
          whileTap={{ scale: 0.98 }}
          transition={springPress}
        >
          {content}
        </motion.div>
      </Link>
    )
  }

  return (
    <div className={cardClass} style={{ borderLeftColor: accentColor }}>
      {content}
    </div>
  )
}
