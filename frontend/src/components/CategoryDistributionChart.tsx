import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useCategorias } from '../context/CategoriasContext'

interface CatalogoItem {
  id: string
  label: string
  color: string
  orden: number
}

// `catalogo` opcional: por defecto resuelve etiquetas/colores contra las
// categorías del cliente; se pasa para graficar otro nivel (ej. subcategorías).
export default function CategoryDistributionChart({
  counts,
  catalogo,
}: {
  counts: Record<string, number>
  catalogo?: CatalogoItem[]
}) {
  const { categorias, meta: metaCategoria } = useCategorias()
  const total = Object.values(counts).reduce((a, b) => a + b, 0)
  const fuente = catalogo ?? categorias
  const meta = (id: string) => fuente.find((c) => c.id === id) ?? metaCategoria(id)
  const orden = new Map(fuente.map((c) => [c.id, c.orden]))
  const data = Object.entries(counts)
    .filter(([, n]) => n > 0)
    .sort(([a], [b]) => (orden.get(a) ?? 999) - (orden.get(b) ?? 999))
    .map(([categoria, n]) => ({ name: meta(categoria).label, value: n, categoria }))

  if (data.length === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">No classification data yet.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 56 }}>
        <CartesianGrid horizontal={false} stroke="#e1e0d9" />
        <XAxis type="number" tick={{ fontSize: 12, fill: '#898781' }} allowDecimals={false} />
        <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12, fill: '#52514e' }} />
        <Tooltip formatter={(v) => Number(v).toLocaleString('en-US')} />
        <Bar
          dataKey="value"
          radius={[0, 4, 4, 0]}
          barSize={22}
          label={{
            position: 'right',
            fontSize: 12,
            fill: '#52514e',
            formatter: (v: unknown) => {
              const n = Number(v) || 0
              return `${n.toLocaleString('en-US')} (${((n / total) * 100).toFixed(1)}%)`
            },
          }}
        >
          {data.map((d) => (
            <Cell key={d.categoria} fill={meta(d.categoria).color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
