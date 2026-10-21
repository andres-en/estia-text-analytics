import { useRef, useState, type MouseEvent, type ReactNode } from 'react'
import { formatDayMonth, formatNumber, parseLocalDate } from '../lib/format'
import { niceStep, smoothPath, type Point } from '../lib/chart'

export interface TrendSeries {
  id: string
  label: string
  color: string
  /** Un valor por cada fecha de `dates`, en el mismo orden. */
  values: number[]
}

// Coordenadas internas del SVG; se estira al ancho real con preserveAspectRatio="none"
// y `vector-effect: non-scaling-stroke` mantiene el grosor de línea.
const W = 1000
const H = 280
const PLOT_H = 270

/**
 * Áreas suaves por categoría con guía vertical + tooltip al pasar el cursor y
 * chips de leyenda que encienden/apagan cada serie. Dibujado a mano (no
 * Recharts) para controlar el tooltip y las marcas como en el diseño.
 */
export default function DailyTrendChart({
  dates,
  series,
  heading,
}: {
  dates: string[]
  series: TrendSeries[]
  /** Título de la tarjeta; la leyenda se alinea a su derecha. */
  heading: ReactNode
}) {
  const chartRef = useRef<HTMLDivElement>(null)
  const [hidden, setHidden] = useState<string[]>([])
  const [hover, setHover] = useState<number | null>(null)

  const n = dates.length
  if (n === 0 || series.length === 0) {
    return (
      <>
        {heading}
        <p className="text-[13px] text-ink-3 py-8 text-center">Todavía no hay conversaciones clasificadas en este período.</p>
      </>
    )
  }

  const visibles = series.filter((s) => !hidden.includes(s.id))
  const step = niceStep(Math.max(4, ...visibles.flatMap((s) => s.values)) / 4)
  const ymax = step * 4
  const X = (i: number) => (n === 1 ? W / 2 : (i / (n - 1)) * W)
  const Y = (v: number) => H - (v / ymax) * PLOT_H
  const pct = (i: number) => `${((X(i) / W) * 100).toFixed(2)}%`

  const paths = visibles.map((s) => {
    const pts: Point[] = s.values.map((v, i) => [X(i), Y(v)])
    const line = smoothPath(pts, H)
    return { ...s, line, area: `${line} L${X(n - 1)},${H} L${X(0)},${H} Z` }
  })

  const yTicks = [0, 1, 2, 3, 4].map((k) => {
    const v = ymax - k * step
    return { v, top: `${((Y(v) / H) * 100).toFixed(2)}%` }
  })

  // ~7 etiquetas en el eje X sin importar cuántos días haya.
  const xStep = Math.max(1, Math.ceil(n / 7))
  const xTicks = dates
    .map((d, i) => ({ i, d }))
    .filter(({ i }) => i % xStep === 0)
    .map(({ i, d }) => ({ left: pct(i), label: formatDayMonth(parseLocalDate(d)) }))

  const h = hover != null && hover < n ? hover : null
  const hoverRows =
    h != null
      ? visibles
          .map((s) => ({ id: s.id, label: s.label, color: s.color, v: s.values[h] ?? 0 }))
          .sort((a, b) => b.v - a.v)
      : []
  const hoverDate = h != null ? parseLocalDate(dates[h]!) : null

  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    const el = chartRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const i = Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width) * (n - 1))))
    if (i !== hover) setHover(i)
  }

  const toggle = (id: string) => setHidden((hs) => (hs.includes(id) ? hs.filter((x) => x !== id) : [...hs, id]))

  return (
    <>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        {heading}
        <div className="flex flex-wrap gap-1.5">
        {series.map((s) => {
          const off = hidden.includes(s.id)
          return (
            <button
              key={s.id}
              type="button"
              aria-pressed={!off}
              onClick={() => toggle(s.id)}
              className={`flex items-center gap-1.5 h-7 px-2.5 rounded-full border border-line bg-surface text-xs font-medium text-ink-2 hover:border-ink-3 transition-opacity ${
                off ? 'opacity-40' : ''
              }`}
            >
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
              {s.label}
            </button>
          )
        })}
        </div>
      </div>

      <div className="grid grid-cols-[32px_minmax(0,1fr)] gap-2">
        <div className="relative h-[280px]">
          {yTicks.map((y) => (
            <span
              key={y.v}
              className="absolute right-0 -translate-y-1/2 text-[11px] text-ink-3 tabular-nums"
              style={{ top: y.top }}
            >
              {formatNumber(y.v)}
            </span>
          ))}
        </div>
        <div>
          <div
            ref={chartRef}
            onMouseMove={onMove}
            onMouseLeave={() => setHover(null)}
            className="relative h-[280px] cursor-crosshair"
          >
            {yTicks.map((y) => (
              <div key={y.v} className="absolute inset-x-0 border-t border-dashed border-line" style={{ top: y.top }} />
            ))}
            <svg
              viewBox={`0 0 ${W} ${H}`}
              preserveAspectRatio="none"
              className="absolute inset-0 w-full h-full overflow-visible"
              aria-hidden
            >
              {paths.map((p) => (
                <g key={p.id}>
                  <path d={p.area} fill={p.color} fillOpacity={0.07} />
                  <path
                    d={p.line}
                    fill="none"
                    stroke={p.color}
                    strokeWidth={2}
                    vectorEffect="non-scaling-stroke"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                  />
                </g>
              ))}
            </svg>

            {h != null && hoverDate && (
              <>
                <div className="absolute inset-y-0 w-px bg-ink-3 opacity-50 pointer-events-none" style={{ left: pct(h) }} />
                {hoverRows.map((r) => (
                  <span
                    key={r.id}
                    className="absolute w-[9px] h-[9px] -mt-[5px] -ml-[5px] rounded-full border-2 border-surface shadow-[0_1px_3px_rgba(0,0,0,.2)] pointer-events-none"
                    style={{ left: pct(h), top: `${((Y(r.v) / H) * 100).toFixed(2)}%`, backgroundColor: r.color }}
                  />
                ))}
                <div
                  className="absolute top-2 min-w-[200px] bg-surface border border-line-soft rounded-xl shadow-pop px-3 py-2.5 pointer-events-none z-[2]"
                  style={{
                    left: pct(h),
                    transform: n > 1 && h / (n - 1) > 0.6 ? 'translateX(calc(-100% - 14px))' : 'translateX(14px)',
                  }}
                >
                  <div className="text-xs font-semibold text-ink mb-2">
                    {formatDayMonth(hoverDate)} {hoverDate.getFullYear()} ·{' '}
                    {formatNumber(hoverRows.reduce((a, r) => a + r.v, 0))} conv.
                  </div>
                  <div className="flex flex-col gap-[5px]">
                    {hoverRows.map((r) => (
                      <div key={r.id} className="flex items-center gap-2 text-xs">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: r.color }} />
                        <span className="flex-1 text-ink-2 whitespace-nowrap">{r.label}</span>
                        <strong className="font-semibold text-ink tabular-nums">{formatNumber(r.v)}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
          <div className="relative h-6 mt-1.5">
            {xTicks.map((x) => (
              <span
                key={x.left}
                className="absolute -translate-x-1/2 text-[11px] text-ink-3 whitespace-nowrap"
                style={{ left: x.left }}
              >
                {x.label}
              </span>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
