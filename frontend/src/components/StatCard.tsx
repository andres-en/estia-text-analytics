import { Link } from 'react-router-dom'
import { ArrowUpRight, Minus, Sparkles, Tag, TrendingDown, TrendingUp } from 'lucide-react'
import type { Trend } from '../lib/trend'
import { formatNumber, formatPercent } from '../lib/format'
import { smoothPath, type Point } from '../lib/chart'
import { categorySoftBg } from '../lib/categoryColors'

interface Props {
  label: string
  value: number
  /** Fracción del total de conversaciones (0–1): alimenta el "% del total" y la barra inferior. */
  share: number
  color: string
  to: string
  trend: Trend | null
  /** Conteos diarios del período, para la mini tendencia; `null` la oculta. */
  spark: number[] | null
}

const TREND_STYLE: Record<Trend['direction'], { cls: string; icon: typeof TrendingUp }> = {
  up: { cls: 'bg-ok-bg text-ok-fg', icon: TrendingUp },
  down: { cls: 'bg-bad-bg text-bad-fg', icon: TrendingDown },
  flat: { cls: 'bg-mute-bg text-mute-fg', icon: Minus },
  new: { cls: 'bg-accent-soft text-accent-ink', icon: Sparkles },
}

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const max = Math.max(...values, 1)
  const pts: Point[] = values.map((v, i) => [(i / Math.max(values.length - 1, 1)) * 100, 34 - (v / max) * 30])
  const line = smoothPath(pts, 34)
  return (
    <svg viewBox="0 0 100 36" preserveAspectRatio="none" className="w-[84px] h-9 shrink-0 overflow-visible" aria-hidden>
      <path d={`${line} L100,36 L0,36 Z`} fill={color} fillOpacity={0.1} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth={1.75}
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}

/** Tarjeta de categoría del dashboard: ícono, total, variación, % del total, mini tendencia y barra. */
export default function StatCard({ label, value, share, color, to, trend, spark }: Props) {
  const t = trend ? TREND_STYLE[trend.direction] : null
  return (
    <Link
      to={to}
      className="group relative flex flex-col gap-3.5 p-[18px] bg-surface border border-line-soft rounded-2xl shadow-card overflow-hidden text-inherit no-underline transition-[transform,box-shadow] duration-[180ms] ease-[cubic-bezier(.2,.8,.2,1)] hover:-translate-y-0.5 hover:shadow-pop"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className="w-[34px] h-[34px] rounded-[10px] shrink-0 flex items-center justify-center"
            style={{ backgroundColor: categorySoftBg(color), color }}
          >
            <Tag size={17} strokeWidth={2} />
          </span>
          <span className="text-[13px] font-semibold text-ink-2 leading-[1.3]">{label}</span>
        </div>
        <ArrowUpRight size={16} className="text-ink-3 shrink-0 transition-colors group-hover:text-ink" />
      </div>

      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-[30px] font-bold tracking-[-.03em] leading-none text-ink tabular-nums">{formatNumber(value)}</div>
          <div className="flex items-center gap-2 mt-2.5 flex-wrap">
            {trend && t && (
              <span className={`inline-flex items-center gap-[3px] h-[22px] px-2 rounded-full text-[11.5px] font-semibold ${t.cls}`}>
                <t.icon size={12} strokeWidth={2.5} />
                {trend.label}
              </span>
            )}
            <span className="text-[11.5px] text-ink-3">{formatPercent(share)} del total</span>
          </div>
        </div>
        {spark && spark.length > 1 && <Sparkline values={spark} color={color} />}
      </div>

      <div className="h-1 rounded-full bg-surface-2 overflow-hidden">
        <div
          className="h-full rounded-full transition-[width] duration-[400ms] ease-[cubic-bezier(.2,.8,.2,1)]"
          style={{ width: `${(share * 100).toFixed(2)}%`, backgroundColor: color }}
        />
      </div>
    </Link>
  )
}
