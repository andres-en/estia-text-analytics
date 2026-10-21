import { Info } from 'lucide-react'
import { formatNumber, formatPercent } from '../lib/format'

const R = 68
const CIRC = 2 * Math.PI * R
// Separación entre los dos arcos; con extremos redondeados se ve como un hueco limpio.
const GAP = 10

function MethodCard({ color, label, value, pct }: { color: string; label: string; value: number; pct: string }) {
  return (
    <div className="flex flex-col gap-1.5 px-3.5 py-3 rounded-xl bg-bg border border-line-soft">
      <div className="flex items-center gap-2">
        <span className="w-[9px] h-[9px] rounded-full" style={{ backgroundColor: color }} />
        <span className="text-[13px] font-medium text-ink-2 flex-1">{label}</span>
        <span className="text-xs text-ink-3">{pct}</span>
      </div>
      <div className="text-[22px] font-bold tracking-[-.02em] text-ink tabular-nums">{formatNumber(value)}</div>
    </div>
  )
}

export default function MethodBreakdown({ counts }: { counts: Record<string, number> }) {
  const rule = counts.RULE ?? 0
  const ai = counts.AI ?? 0
  const total = rule + ai

  if (total === 0) {
    return <p className="text-[13px] text-ink-3 py-8 text-center">Todavía no hay conversaciones clasificadas.</p>
  }

  const ruleFrac = rule / total
  // Si un método no tiene conversaciones, el otro ocupa el anillo completo (sin hueco).
  const both = rule > 0 && ai > 0
  const ruleLen = both ? CIRC * ruleFrac - GAP : rule > 0 ? CIRC : 0
  const aiLen = both ? CIRC * (1 - ruleFrac) - GAP : ai > 0 ? CIRC : 0

  return (
    <>
      <div className="flex items-center gap-7 flex-wrap flex-1">
        <div className="relative w-[168px] h-[168px] shrink-0">
          <svg viewBox="0 0 168 168" className="w-[168px] h-[168px] -rotate-90" aria-hidden>
            <circle cx="84" cy="84" r={R} fill="none" stroke="var(--surface-2)" strokeWidth="16" />
            {ruleLen > 0 && (
              <circle
                cx="84"
                cy="84"
                r={R}
                fill="none"
                stroke="var(--accent)"
                strokeWidth="16"
                strokeLinecap={both ? 'round' : 'butt'}
                strokeDasharray={`${ruleLen.toFixed(1)} ${CIRC.toFixed(1)}`}
                className="transition-[stroke-dasharray] duration-500"
              />
            )}
            {aiLen > 0 && (
              <circle
                cx="84"
                cy="84"
                r={R}
                fill="none"
                stroke="var(--ai)"
                strokeWidth="16"
                strokeLinecap={both ? 'round' : 'butt'}
                strokeDasharray={`${aiLen.toFixed(1)} ${CIRC.toFixed(1)}`}
                strokeDashoffset={both ? (-(ruleLen + GAP)).toFixed(1) : 0}
                className="transition-all duration-500"
              />
            )}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="text-[26px] font-bold tracking-[-.03em] text-ink tabular-nums">{formatNumber(total)}</div>
            <div className="text-[11px] text-ink-3">clasificadas</div>
          </div>
        </div>
        <div className="flex-1 min-w-[200px] flex flex-col gap-3.5">
          <MethodCard color="var(--accent)" label="Reglas deterministas" value={rule} pct={formatPercent(ruleFrac)} />
          <MethodCard color="var(--ai)" label="Inteligencia artificial" value={ai} pct={formatPercent(1 - ruleFrac)} />
        </div>
      </div>
      <div className="flex items-start gap-2.5 px-3.5 py-3 rounded-xl bg-accent-soft text-accent-ink text-[12.5px] leading-normal">
        <Info size={15} className="shrink-0 mt-0.5" />
        <span>La IA interviene únicamente cuando las reglas no pudieron determinar una categoría (zona gris).</span>
      </div>
    </>
  )
}
