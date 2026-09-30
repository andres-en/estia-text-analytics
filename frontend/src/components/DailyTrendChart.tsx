import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useCategorias } from '../context/CategoriasContext'

interface TrendPoint {
  fecha: string
  categoria: string
  cantidad: number
}

export default function DailyTrendChart({ trend }: { trend: TrendPoint[] }) {
  const { categorias, meta } = useCategorias()
  const fechas = Array.from(new Set(trend.map((t) => t.fecha))).sort()

  if (fechas.length === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">No classification data yet.</p>
  }

  const totalesPorCategoria = new Map<string, number>()
  for (const t of trend) totalesPorCategoria.set(t.categoria, (totalesPorCategoria.get(t.categoria) ?? 0) + t.cantidad)

  const orden = new Map(categorias.map((c) => [c.id, c.orden]))
  const idsOrdenados = Array.from(totalesPorCategoria.keys()).sort(
    (a, b) => (orden.get(a) ?? 999) - (orden.get(b) ?? 999),
  )

  // Si una sola categoría concentra más de la mitad del total, se excluye del
  // gráfico: su volumen aplanaría el resto en la misma escala (ej. "Sin
  // respuesta", que suele ser la mayoría de las conversaciones sin analizar).
  const totalGeneral = Array.from(totalesPorCategoria.values()).reduce((a, b) => a + b, 0)
  const excluida = idsOrdenados.find((id) => (totalesPorCategoria.get(id) ?? 0) > totalGeneral / 2) ?? null
  const idsCategorias = idsOrdenados.filter((id) => id !== excluida)

  const data = fechas.map((fecha) => {
    const row: Record<string, string | number> = { fecha }
    for (const id of idsCategorias) {
      row[id] = trend.find((t) => t.fecha === fecha && t.categoria === id)?.cantidad ?? 0
    }
    return row
  })

  return (
    <>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data}>
          <defs>
            {idsCategorias.map((id) => (
              <linearGradient key={id} id={`fill-${id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={meta(id).color} stopOpacity={0.28} />
                <stop offset="100%" stopColor={meta(id).color} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid vertical={false} stroke="#e1e0d9" />
          <XAxis dataKey="fecha" tick={{ fontSize: 12, fill: '#898781' }} />
          <YAxis tick={{ fontSize: 12, fill: '#898781' }} allowDecimals={false} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} formatter={(value: string) => meta(value).label} />
          {idsCategorias.map((id) => (
            <Area
              key={id}
              type="monotone"
              dataKey={id}
              name={meta(id).label}
              stroke={meta(id).color}
              strokeWidth={2}
              fill={`url(#fill-${id})`}
              dot={{ r: 3, strokeWidth: 0, fill: meta(id).color }}
              activeDot={{ r: 5 }}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
      {excluida && (
        <p className="text-xs text-gray-400 mt-1">Excludes "{meta(excluida).label}" (its volume would flatten the rest).</p>
      )}
    </>
  )
}
