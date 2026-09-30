import { useEffect, useState } from 'react'
import { LayoutDashboard, Tag } from 'lucide-react'
import { fetchDashboard, type DashboardData } from '../api/client'
import StatCard from '../components/StatCard'
import CategoryDistributionChart from '../components/CategoryDistributionChart'
import DailyTrendChart from '../components/DailyTrendChart'
import MethodBreakdown from '../components/MethodBreakdown'
import PageHeader from '../components/PageHeader'
import { computeTrend } from '../lib/trend'
import { useCategorias } from '../context/CategoriasContext'

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

const RANGE_PRESETS: { label: string; desde: string; hasta: string }[] = [
  { label: 'All time', desde: '', hasta: '' },
  { label: 'Last 7 days', desde: isoDaysAgo(7), hasta: '' },
  { label: 'Last 30 days', desde: isoDaysAgo(30), hasta: '' },
]

export default function DashboardPage() {
  const { categorias, subcategorias } = useCategorias()
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  useEffect(() => {
    fetchDashboard({ desde: desde || undefined, hasta: hasta || undefined })
      .then((res) => {
        setData(res)
        setLastUpdated(new Date())
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the dashboard'))
  }, [desde, hasta])

  // Categorías marcadas para no graficarse (ej. "Sin respuesta" en Acme, que
  // es la gran mayoría y aplasta al resto) — siguen existiendo en la tabla.
  const ocultas = new Set(categorias.filter((c) => c.ocultar_en_dashboard).map((c) => c.id))
  const conteosVisibles = Object.fromEntries(
    Object.entries(data?.category_counts ?? {}).filter(([id]) => !ocultas.has(id)),
  )
  const hasRangeFilter = desde || hasta
  const activePreset = RANGE_PRESETS.find((p) => p.desde === desde && p.hasta === hasta)

  return (
    <div className="space-y-6">
      <PageHeader icon={LayoutDashboard} title="Dashboard" />

      {lastUpdated && (
        <p className="text-xs text-gray-400 text-right -mt-4">
          Last updated:{' '}
          {lastUpdated.toLocaleString('en-US', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </p>
      )}

      <div className="surface p-4 flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">From</label>
          <input
            type="date"
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
            className="border border-gray-300 rounded-lg px-2 py-1 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">To</label>
          <input
            type="date"
            value={hasta}
            onChange={(e) => setHasta(e.target.value)}
            className="border border-gray-300 rounded-lg px-2 py-1 text-sm"
          />
        </div>
        <div className="flex gap-2">
          {RANGE_PRESETS.map((preset) => {
            const active = preset === activePreset || (!activePreset && preset.label === 'All time' && !hasRangeFilter)
            return (
              <button
                key={preset.label}
                type="button"
                onClick={() => {
                  setDesde(preset.desde)
                  setHasta(preset.hasta)
                }}
                className={`text-xs rounded-full px-3 py-1.5 border transition-colors ${
                  active
                    ? 'bg-[var(--wa-green-dark)] border-[var(--wa-green-dark)] text-white font-medium'
                    : 'border-gray-300 text-gray-500 hover:border-gray-400'
                }`}
              >
                {preset.label}
              </button>
            )
          })}
        </div>
        {hasRangeFilter && (
          <button
            type="button"
            onClick={() => {
              setDesde('')
              setHasta('')
            }}
            className="text-xs text-[var(--wa-green-dark)] underline ml-auto"
          >
            Clear filter
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {!data && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {categorias
              .filter((cat) => cat.id !== 'SIN_ANALIZAR' && !ocultas.has(cat.id))
              .map((cat) => (
                <StatCard
                  key={cat.id}
                  label={cat.label}
                  value={data.category_counts[cat.id] ?? 0}
                  to={`/?categoria=${encodeURIComponent(cat.id)}`}
                  icon={Tag}
                  accentColor={cat.color}
                  trend={computeTrend(
                    data.category_counts_trend.current[cat.id] ?? 0,
                    data.category_counts_trend.previous[cat.id] ?? 0,
                  )}
                />
              ))}
          </div>
          {!hasRangeFilter && (
            <p className="text-xs text-gray-400 -mt-3">
              The change compares the last 30 days against the previous 30 (there is no older data yet).
            </p>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="surface p-4">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-semibold text-[var(--wa-green-dark)]">Distribution by category</h2>
                <span className="text-xs text-gray-400">
                  Total: {Object.values(conteosVisibles).reduce((a, b) => a + b, 0).toLocaleString('en-US')}{' '}
                  conversaciones
                </span>
              </div>
              <CategoryDistributionChart counts={conteosVisibles} />
              {categorias
                .filter((c) => ocultas.has(c.id) && (data.category_counts[c.id] ?? 0) > 0)
                .map((c) => (
                  <p key={c.id} className="text-xs text-gray-400 mt-2">
                    {c.label} ({(data.category_counts[c.id] ?? 0).toLocaleString('en-US')}) is not included in the chart.
                  </p>
                ))}
            </div>

            {subcategorias.items.length > 0 && (
              <div className="surface p-4">
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-sm font-semibold text-[var(--wa-green-dark)]">{subcategorias.etiqueta}</h2>
                  <span className="text-xs text-gray-400">
                    Total: {Object.values(data.subcategory_counts ?? {}).reduce((a, b) => a + b, 0).toLocaleString('en-US')}{' '}
                    conversaciones
                  </span>
                </div>
                <CategoryDistributionChart counts={data.subcategory_counts ?? {}} catalogo={subcategorias.items} />
              </div>
            )}

            <div className="surface p-4">
              <h2 className="text-sm font-semibold text-[var(--wa-green-dark)] mb-3">Classification method</h2>
              <MethodBreakdown counts={data.method_counts} />
            </div>

            <div className="surface p-4 lg:col-span-2">
              <h2 className="text-sm font-semibold text-[var(--wa-green-dark)] mb-2">Daily trend</h2>
              <DailyTrendChart trend={data.daily_trend.filter((t) => !ocultas.has(t.categoria))} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
