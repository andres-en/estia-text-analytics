import { parseLocalDate, toIsoDate } from './format'

export type Point = [number, number]

/**
 * Curva suave (Catmull-Rom → Bézier cúbica) que pasa por todos los puntos.
 * `floorY` evita que los puntos de control bajen del eje cuando la serie
 * toca cero, que de otra forma "hunden" la curva por debajo del gráfico.
 */
export function smoothPath(pts: Point[], floorY = Infinity): string {
  if (pts.length === 0) return ''
  if (pts.length === 1) return `M${pts[0]![0]},${pts[0]![1]}`
  let d = `M${pts[0]![0].toFixed(1)},${pts[0]![1].toFixed(1)}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i]!
    const p1 = pts[i]!
    const p2 = pts[i + 1]!
    const p3 = pts[i + 2] ?? p2
    const c1x = p1[0] + (p2[0] - p0[0]) / 6
    const c1y = Math.min(p1[1] + (p2[1] - p0[1]) / 6, floorY)
    const c2x = p2[0] - (p3[0] - p1[0]) / 6
    const c2y = Math.min(p2[1] - (p3[1] - p1[1]) / 6, floorY)
    d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`
  }
  return d
}

/** Paso "redondo" (1, 2, 2.5, 5 × 10ⁿ) ≥ `raw`, para marcas de eje legibles. */
export function niceStep(raw: number): number {
  if (raw <= 0) return 1
  const mag = 10 ** Math.floor(Math.log10(raw))
  for (const m of [1, 2, 2.5, 5, 10]) {
    if (m * mag >= raw) return Math.max(1, m * mag)
  }
  return 10 * mag
}

/** Días consecutivos (AAAA-MM-DD) entre dos fechas, ambas inclusive. */
export function dayRange(from: string, to: string): string[] {
  const out: string[] = []
  const d = parseLocalDate(from)
  const end = parseLocalDate(to)
  // Tope defensivo: un rango de varios años no debería colgar el navegador.
  while (d <= end && out.length < 3700) {
    out.push(toIsoDate(d))
    d.setDate(d.getDate() + 1)
  }
  return out
}
