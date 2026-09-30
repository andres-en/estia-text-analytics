export interface Trend {
  direction: 'up' | 'down' | 'flat' | 'new'
  label: string
}

// Compara el período actual contra el período anterior (misma duración).
// Ver business_indicators_trend en conversation_view.py para cómo se define cada período.
export function computeTrend(current: number, previous: number): Trend | null {
  if (previous === 0) {
    return current > 0 ? { direction: 'new', label: 'New' } : null
  }
  const pct = ((current - previous) / previous) * 100
  if (Math.abs(pct) < 0.5) {
    return { direction: 'flat', label: 'No change' }
  }
  const sign = pct > 0 ? '+' : ''
  return {
    direction: pct > 0 ? 'up' : 'down',
    label: `${sign}${pct.toFixed(1)}% vs. previous period`,
  }
}
