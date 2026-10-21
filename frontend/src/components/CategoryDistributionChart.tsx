import { useCategorias } from '../context/CategoriasContext'
import { formatNumber, formatPercent } from '../lib/format'

interface CatalogoItem {
  id: string
  label: string
  color: string
  orden: number
}

// Barras horizontales en HTML (no SVG) para que las etiquetas largas se corten
// con elipsis en vez de encimarse. `catalogo` opcional: por defecto resuelve
// etiquetas/colores contra las categorías del cliente; se pasa para graficar
// otro nivel (ej. subcategorías). `total` es el denominador del porcentaje —
// puede incluir categorías que no se grafican.
export default function CategoryDistributionChart({
  counts,
  total,
  catalogo,
}: {
  counts: Record<string, number>
  total: number
  catalogo?: CatalogoItem[]
}) {
  const { categorias, meta: metaCategoria } = useCategorias()
  const fuente = catalogo ?? categorias
  const meta = (id: string) => fuente.find((c) => c.id === id) ?? metaCategoria(id)
  const orden = new Map(fuente.map((c) => [c.id, c.orden]))
  const data = Object.entries(counts)
    .filter(([, n]) => n > 0)
    .sort(([a], [b]) => (orden.get(a) ?? 999) - (orden.get(b) ?? 999))
  const max = Math.max(...data.map(([, n]) => n), 1)

  if (data.length === 0) {
    return <p className="text-[13px] text-ink-3 py-8 text-center">Todavía no hay conversaciones clasificadas.</p>
  }

  return (
    <div className="flex flex-col gap-3">
      {data.map(([id, n]) => {
        const { label, color } = meta(id)
        return (
          <div key={id} className="grid grid-cols-[150px_minmax(0,1fr)_96px] items-center gap-3">
            <span className="flex items-center gap-2 text-[12.5px] font-medium text-ink-2 min-w-0">
              <span className="w-2 h-2 rounded-[3px] shrink-0" style={{ backgroundColor: color }} />
              <span className="truncate" title={label}>
                {label}
              </span>
            </span>
            <div className="h-2.5 rounded-full bg-surface-2 overflow-hidden">
              <div
                className="h-full min-w-1 rounded-full transition-[width] duration-500 ease-[cubic-bezier(.2,.8,.2,1)]"
                style={{ width: `${((n / max) * 100).toFixed(2)}%`, backgroundColor: color }}
              />
            </div>
            <span className="text-[12.5px] text-right tabular-nums whitespace-nowrap">
              <strong className="font-semibold text-ink">{formatNumber(n)}</strong>{' '}
              <span className="text-ink-3">{total > 0 ? formatPercent(n / total) : ''}</span>
            </span>
          </div>
        )
      })}
    </div>
  )
}
