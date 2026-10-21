import { useEffect, useMemo, useState } from 'react'
import { Download } from 'lucide-react'
import { exportConversations, fetchDashboard, type DashboardData } from '../api/client'
import StatCard from '../components/StatCard'
import CategoryDistributionChart from '../components/CategoryDistributionChart'
import DailyTrendChart, { type TrendSeries } from '../components/DailyTrendChart'
import MethodBreakdown from '../components/MethodBreakdown'
import PageHeader from '../components/PageHeader'
import SegmentedControl from '../components/SegmentedControl'
import DateRangeField from '../components/DateRangeField'
import Switch from '../components/Switch'
import { computeTrend } from '../lib/trend'
import { dayRange } from '../lib/chart'
import { formatDateTime, formatNumber, toIsoDate } from '../lib/format'
import { useCategorias } from '../context/CategoriasContext'

type Preset = 'todo' | '30' | '7'

const PRESETS: { value: Preset; label: string }[] = [
  { value: 'todo', label: 'Todo' },
  { value: '30', label: 'Últimos 30 días' },
  { value: '7', label: 'Últimos 7 días' },
]

// "Últimos N días" incluye hoy, igual que la ventana por defecto del backend
// para la variación (ver `_ventana_actual_y_anterior` en conversation_view.py).
function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return toIsoDate(d)
}

function presetRange(p: Preset): { desde: string; hasta: string } {
  if (p === '30') return { desde: isoDaysAgo(29), hasta: '' }
  if (p === '7') return { desde: isoDaysAgo(6), hasta: '' }
  return { desde: '', hasta: '' }
}

function CardTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div>
      <h2 className="m-0 text-[15px] font-bold text-ink">{title}</h2>
      {subtitle && <div className="text-xs text-ink-3 mt-[3px]">{subtitle}</div>}
    </div>
  )
}

export default function DashboardPage() {
  const { categorias, subcategorias } = useCategorias()
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [preset, setPreset] = useState<Preset | null>('todo')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [incluirOcultas, setIncluirOcultas] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchDashboard({ desde: desde || undefined, hasta: hasta || undefined })
      .then((res) => {
        if (cancelled) return
        setData(res)
        setError(null)
        setLastUpdated(new Date())
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'No se pudo cargar el dashboard')
      })
    return () => {
      cancelled = true
    }
  }, [desde, hasta])

  const elegirPreset = (p: Preset) => {
    const r = presetRange(p)
    setPreset(p)
    setDesde(r.desde)
    setHasta(r.hasta)
  }

  const handleExport = async () => {
    setExporting(true)
    setExportError(null)
    try {
      await exportConversations({ desde: desde || undefined, hasta: hasta || undefined })
    } catch (e) {
      setExportError(e instanceof Error ? e.message : 'No se pudo exportar')
    } finally {
      setExporting(false)
    }
  }

  // Categorías marcadas para no graficarse (ej. "No aplica ninguna de las
  // anteriores", que es la gran mayoría y aplasta al resto) — siguen
  // existiendo en la tabla y en las tarjetas.
  const ocultas = useMemo(() => categorias.filter((c) => c.ocultar_en_dashboard), [categorias])
  const idsOcultas = useMemo(() => new Set(ocultas.map((c) => c.id)), [ocultas])
  const counts = data?.category_counts ?? {}
  const total = Object.values(counts).reduce((a, b) => a + b, 0)
  const conteosDistribucion = Object.fromEntries(
    Object.entries(counts).filter(([id]) => id !== 'SIN_ANALIZAR' && (incluirOcultas || !idsOcultas.has(id))),
  )
  const totalDistribucion = Object.values(conteosDistribucion).reduce((a, b) => a + b, 0)
  const ocultasConDatos = ocultas.filter((c) => (counts[c.id] ?? 0) > 0)

  // Serie diaria continua (días sin conversaciones = 0) para la tendencia y
  // las mini tendencias de las tarjetas.
  const { fechas, porCategoria } = useMemo(() => {
    const trend = data?.daily_trend ?? []
    const conDatos = trend.map((t) => t.fecha).sort()
    const inicio = desde || conDatos[0]
    const fin = hasta || (desde ? toIsoDate(new Date()) : conDatos[conDatos.length - 1])
    const fechas = inicio && fin ? dayRange(inicio, fin) : []
    const indice = new Map(fechas.map((f, i) => [f, i]))
    const porCategoria = new Map<string, number[]>()
    for (const t of trend) {
      const i = indice.get(t.fecha.slice(0, 10))
      if (i === undefined) continue
      if (!porCategoria.has(t.categoria)) porCategoria.set(t.categoria, new Array(fechas.length).fill(0))
      porCategoria.get(t.categoria)![i] += t.cantidad
    }
    return { fechas, porCategoria }
  }, [data, desde, hasta])

  const series: TrendSeries[] = categorias
    .filter((c) => !idsOcultas.has(c.id) && porCategoria.has(c.id))
    .map((c) => ({ id: c.id, label: c.label, color: c.color, values: porCategoria.get(c.id)! }))

  const tarjetas = categorias.filter((c) => c.id !== 'SIN_ANALIZAR')

  return (
    <div className="flex flex-col gap-5 px-7 pt-6 pb-8 box-border max-w-[1600px]">
      <PageHeader
        title="Dashboard"
        subtitle={
          lastUpdated && (
            <span className="flex items-center gap-2">
              <span className="w-[7px] h-[7px] rounded-full bg-[#10b981] shadow-[0_0_0_3px_rgba(16,185,129,.18)]" />
              Actualizado el {formatDateTime(lastUpdated)}
            </span>
          )
        }
        actions={
          <button type="button" onClick={handleExport} disabled={exporting} className="btn-secondary">
            <Download size={16} />
            {exporting ? 'Exportando…' : 'Exportar a Excel'}
          </button>
        }
      />
      {exportError && <p className="text-[13px] text-bad-fg -mt-2">{exportError}</p>}

      <section className="surface p-2.5 flex items-center justify-between gap-3 flex-wrap">
        <SegmentedControl options={PRESETS} value={preset} onChange={elegirPreset} className="w-[360px] max-w-full" />
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="text-xs text-ink-3">Rango personalizado</span>
          <DateRangeField
            desde={desde}
            hasta={hasta}
            onChange={(patch) => {
              setPreset(null)
              if (patch.desde !== undefined) setDesde(patch.desde)
              if (patch.hasta !== undefined) setHasta(patch.hasta)
            }}
          />
        </div>
      </section>

      {error && <p className="text-[13px] text-bad-fg">{error}</p>}
      {!data && !error && <p className="text-[13px] text-ink-3">Cargando…</p>}

      {data && (
        <>
          <section className="flex flex-col gap-3">
            <div className="flex items-baseline justify-between gap-3 flex-wrap">
              <h2 className="m-0 text-[15px] font-bold text-ink">
                Categorías <span className="font-medium text-ink-3 ml-1.5">{formatNumber(total)} conversaciones</span>
              </h2>
              <span className="text-xs text-ink-3">
                {desde
                  ? 'Variación: período seleccionado vs. el anterior de igual duración'
                  : 'Variación: últimos 30 días vs. 30 anteriores'}
              </span>
            </div>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3.5">
              {tarjetas.map((cat) => (
                <StatCard
                  key={cat.id}
                  label={cat.label}
                  value={counts[cat.id] ?? 0}
                  share={total > 0 ? (counts[cat.id] ?? 0) / total : 0}
                  color={cat.color}
                  to={`/?categoria=${encodeURIComponent(cat.id)}`}
                  trend={computeTrend(
                    data.category_counts_trend.current[cat.id] ?? 0,
                    data.category_counts_trend.previous[cat.id] ?? 0,
                  )}
                  spark={porCategoria.get(cat.id) ?? null}
                />
              ))}
            </div>
          </section>

          <div className="grid grid-cols-[repeat(auto-fit,minmax(420px,1fr))] gap-4">
            <section className="surface p-5 flex flex-col gap-4">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <CardTitle
                  title="Distribución por categoría"
                  subtitle={`Total: ${formatNumber(totalDistribucion)} conversaciones`}
                />
                {ocultasConDatos.length > 0 && (
                  <Switch checked={incluirOcultas} onChange={setIncluirOcultas} size="sm">
                    {ocultasConDatos.length === 1 ? `Incluir “${ocultasConDatos[0]!.label}”` : 'Incluir categorías ocultas'}
                  </Switch>
                )}
              </div>
              <CategoryDistributionChart counts={conteosDistribucion} total={total} />
              {!incluirOcultas &&
                ocultasConDatos.map((c) => (
                  <div key={c.id} className="text-xs text-ink-3 pt-3 border-t border-line-soft">
                    “{c.label}” ({formatNumber(counts[c.id] ?? 0)}) se oculta para no aplanar la escala.
                  </div>
                ))}
            </section>

            {subcategorias.items.length > 0 && (
              <section className="surface p-5 flex flex-col gap-4">
                <CardTitle
                  title={subcategorias.etiqueta}
                  subtitle={`Total: ${formatNumber(
                    Object.values(data.subcategory_counts ?? {}).reduce((a, b) => a + b, 0),
                  )} conversaciones`}
                />
                <CategoryDistributionChart
                  counts={data.subcategory_counts ?? {}}
                  total={Object.values(data.subcategory_counts ?? {}).reduce((a, b) => a + b, 0)}
                  catalogo={subcategorias.items}
                />
              </section>
            )}

            <section className="surface p-5 flex flex-col gap-[18px]">
              <CardTitle title="Método de clasificación" subtitle="Cómo se decidió cada categoría" />
              <MethodBreakdown counts={data.method_counts} />
            </section>
          </div>

          <section className="surface p-5 flex flex-col gap-4">
            <DailyTrendChart
              dates={fechas}
              series={series}
              heading={
                <CardTitle
                  title="Tendencia diaria"
                  subtitle="Conversaciones por día y categoría · pasa el cursor para ver el detalle"
                />
              }
            />
            {ocultasConDatos.length > 0 && (
              <div className="text-xs text-ink-3 pt-3 border-t border-line-soft">
                No incluye {ocultasConDatos.map((c) => `“${c.label}”`).join(', ')} — su volumen aplanaría el resto.
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}
