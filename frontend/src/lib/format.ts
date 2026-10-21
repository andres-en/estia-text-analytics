// Formatos en español de Colombia (es-CO): "9.741", "18/10/2026", "10:23 p. m.".
//
// Las fechas se arman a mano con padStart a propósito: pedirle a Intl día+mes
// en 2 dígitos (`{day:'2-digit', month:'2-digit'}`) no rellena el cero en
// Chromium con locale es-CO — da "5/8" en vez de "05/08".

const LOCALE = 'es-CO'

export const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

const pad = (n: number) => String(n).padStart(2, '0')

/** Una fecha "AAAA-MM-DD" (sin hora) interpretada en hora local, no en UTC. */
export function parseLocalDate(isoDate: string): Date {
  return new Date(`${isoDate.slice(0, 10)}T00:00:00`)
}

/** "AAAA-MM-DD" de una fecha local (lo que esperan los filtros `desde`/`hasta`). */
export function toIsoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function formatNumber(n: number): string {
  return Math.round(n).toLocaleString(LOCALE)
}

export function formatPercent(fraction: number, decimals = 1): string {
  return `${(fraction * 100).toFixed(decimals)}%`
}

/** "18/10/2026" */
export function formatDate(iso: string | Date): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`
}

/** "10:23 p. m." */
export function formatTime(iso: string | Date): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso
  return d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit' })
}

/** "18/10/2026, 10:23 p. m." */
export function formatDateTime(iso: string | Date): string {
  return `${formatDate(iso)}, ${formatTime(iso)}`
}

/** "18 oct" */
export function formatDayMonth(d: Date): string {
  return `${d.getDate()} ${MESES_CORTOS[d.getMonth()]}`
}

/** "26 ago 2026" */
export function formatMediumDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getDate()} ${MESES_CORTOS[d.getMonth()]} ${d.getFullYear()}`
}

/** "21 de octubre de 2026" */
export function formatLongDate(d: Date): string {
  return d.toLocaleDateString(LOCALE, { day: 'numeric', month: 'long', year: 'numeric' })
}

/** Iniciales para avatares: "Miguel Estepa" → "ME", "dora" → "D". */
export function initials(name: string | null | undefined, max = 2): string {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  return words
    .slice(0, max)
    .map((w) => w[0]!.toUpperCase())
    .join('')
}

/** Teléfono colombiano con indicativo: "573015632061" → "+57 301 563 2061". */
export function formatPhone(phone: string | null): string {
  if (!phone) return '—'
  const m = /^57(\d{3})(\d{3})(\d{4})$/.exec(phone)
  return m ? `+57 ${m[1]} ${m[2]} ${m[3]}` : phone
}
