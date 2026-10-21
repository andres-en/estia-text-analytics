import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AnimatePresence } from 'motion/react'
import { AlertTriangle, Bot, ChevronDown, Download, User, X } from 'lucide-react'
import { exportConversations, fetchConversations, type ConversationSummary } from '../api/client'
import FilterBar, { type FilterState } from '../components/FilterBar'
import UploadPanel from '../components/UploadPanel'
import CategoryBadge from '../components/CategoryBadge'
import ConversationSidePanel from '../components/ConversationSidePanel'
import PageHeader from '../components/PageHeader'
import Pagination from '../components/Pagination'
import { formatDate, formatNumber, formatTime, initials } from '../lib/format'
import { displayName } from '../lib/conversation'
import { useCategorias } from '../context/CategoriasContext'
import { FLAG_LABELS } from '../lib/flags'

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200]
const DEFAULT_PAGE_SIZE = 50
// Por debajo de este ancho del área de contenido, el panel de detalle flota
// sobre la tabla (cajón) en vez de encogerla hasta volverla ilegible.
const NARROW_CONTENT_PX = 1000

function Th({ children, align = 'left', first, last }: { children: ReactNode; align?: 'left' | 'right'; first?: boolean; last?: boolean }) {
  return (
    <th
      className={`eyebrow sticky top-0 z-[1] bg-surface pt-3.5 pb-3 border-b border-line-soft ${
        align === 'right' ? 'text-right' : 'text-left'
      } ${first ? 'pl-5 pr-3' : last ? 'pl-3 pr-5' : 'px-3'}`}
    >
      {children}
    </th>
  )
}

export default function ConversationsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const flag = searchParams.get('flag')
  const [filters, setFilters] = useState<FilterState>({
    q: '',
    categorias: [],
    desde: '',
    hasta: '',
    iniciadaPor: '',
    contieneArray: false,
  })

  // Deep link desde las tarjetas del dashboard (`/?categoria=X`): se consume
  // una sola vez al entrar, hacia el filtro de categoría normal (que ya se ve
  // reflejado como activo en FilterBar) — de ahí en más es estado local, no la URL.
  useEffect(() => {
    const categoriaInicial = searchParams.get('categoria')
    if (!categoriaInicial) return
    setFilters((f) => (f.categorias.includes(categoriaInicial) ? f : { ...f, categorias: [...f.categorias, categoriaInicial] }))
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('categoria')
        return next
      },
      { replace: true },
    )
    // Solo al montar: es un deep link de un solo uso, no una fuente de verdad continua.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const [debouncedQ, setDebouncedQ] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [items, setItems] = useState<ConversationSummary[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [narrow, setNarrow] = useState(false)

  useEffect(() => {
    const el = contentRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([entry]) => setNarrow((entry?.contentRect.width ?? Infinity) < NARROW_CONTENT_PX))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const handleExport = async () => {
    setExporting(true)
    setExportError(null)
    try {
      await exportConversations({
        q: debouncedQ || undefined,
        categoria: filters.categorias.length ? filters.categorias : undefined,
        desde: filters.desde || undefined,
        hasta: filters.hasta || undefined,
        flag: flag || undefined,
        iniciada_por: filters.iniciadaPor || undefined,
        contiene_array: filters.contieneArray ? true : undefined,
      })
    } catch (e) {
      setExportError(e instanceof Error ? e.message : 'No se pudo exportar')
    } finally {
      setExporting(false)
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(filters.q), 350)
    return () => clearTimeout(timer)
  }, [filters.q])

  useEffect(() => {
    setPage(1)
  }, [
    debouncedQ,
    filters.categorias,
    filters.desde,
    filters.hasta,
    filters.iniciadaPor,
    filters.contieneArray,
    flag,
    pageSize,
  ])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchConversations({
      q: debouncedQ || undefined,
      categoria: filters.categorias.length ? filters.categorias : undefined,
      desde: filters.desde || undefined,
      hasta: filters.hasta || undefined,
      flag: flag || undefined,
      iniciada_por: filters.iniciadaPor || undefined,
      contiene_array: filters.contieneArray ? true : undefined,
      page,
      page_size: pageSize,
    })
      .then((res) => {
        if (cancelled) return
        setItems(res.items)
        setTotal(res.total)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'No se pudieron cargar las conversaciones')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [
    debouncedQ,
    filters.categorias,
    filters.desde,
    filters.hasta,
    filters.iniciadaPor,
    filters.contieneArray,
    flag,
    page,
    pageSize,
    reloadToken,
  ])

  // La columna de subcategoría solo existe si el cliente las tiene (ej. "Motivo del interés").
  const { subcategorias } = useCategorias()
  const conSubcategoria = subcategorias.items.length > 0

  const totalPages = Math.max(Math.ceil(total / pageSize), 1)
  const desdeFila = items.length === 0 ? 0 : (page - 1) * pageSize + 1
  const hastaFila = Math.min(page * pageSize, total)

  return (
    <div className="h-full min-h-[720px] flex flex-col gap-4 px-7 py-6 box-border">
      <PageHeader
        title="Conversaciones"
        subtitle="Gestiona y revisa todas las conversaciones clasificadas."
        actions={
          <>
            <button type="button" onClick={handleExport} disabled={exporting} className="btn-secondary">
              <Download size={16} />
              {exporting ? 'Exportando…' : 'Exportar a Excel'}
            </button>
            <UploadPanel onUploaded={() => setReloadToken((t) => t + 1)} />
          </>
        }
      />
      {exportError && <p className="text-[13px] text-bad-fg -mt-2">{exportError}</p>}
      {flag && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-accent-soft text-accent-ink text-[13px]">
          <span>
            Filtrado por indicador: <strong className="font-semibold">{FLAG_LABELS[flag] ?? flag}</strong>
          </span>
          <button
            type="button"
            onClick={() =>
              setSearchParams((prev) => {
                const next = new URLSearchParams(prev)
                next.delete('flag')
                return next
              })
            }
            className="ml-auto flex items-center gap-1 text-xs font-medium hover:underline"
          >
            <X size={13} />
            Quitar filtro
          </button>
        </div>
      )}
      <FilterBar value={filters} onChange={(patch) => setFilters((f) => ({ ...f, ...patch }))} />

      <div ref={contentRef} className="relative flex-1 min-h-0 flex gap-4">
        <section className="flex-1 min-w-[520px] flex flex-col surface overflow-hidden">
          {error && <p className="text-[13px] text-bad-fg px-5 py-3 border-b border-line-soft">{error}</p>}
          <div className="flex-1 min-h-0 overflow-auto">
            <table className="w-full min-w-[760px] border-separate border-spacing-0 text-[13px]">
              <thead>
                <tr>
                  <Th first>Contacto</Th>
                  <Th>Inicio</Th>
                  <Th align="right">Mensajes</Th>
                  <Th>Origen</Th>
                  <Th last={!conSubcategoria}>Categoría</Th>
                  {conSubcategoria && <Th last>{subcategorias.etiqueta}</Th>}
                </tr>
              </thead>
              <tbody>
                {items.map((c) => {
                  const selected = selectedSessionId === c.session_id
                  const name = displayName(c)
                  const esBot = c.iniciada_por === 'BOT'
                  const td = 'py-4 border-b border-line-soft'
                  return (
                    <tr
                      key={c.session_id}
                      onClick={() => setSelectedSessionId(c.session_id)}
                      className={`cursor-pointer transition-colors duration-[120ms] ${selected ? 'bg-row-sel' : 'hover:bg-row-hover'}`}
                    >
                      <td className={`${td} pl-5 pr-3`} style={{ boxShadow: selected ? 'inset 3px 0 0 var(--accent)' : 'none' }}>
                        <div className="flex items-center gap-3 min-w-0">
                          <div
                            className={`w-9 h-9 rounded-full shrink-0 flex items-center justify-center text-[13px] font-semibold ${
                              selected ? 'bg-accent text-white' : 'bg-surface-2 text-ink-2'
                            }`}
                          >
                            {initials(name, 1)}
                          </div>
                          <div className="min-w-0 leading-[1.35]">
                            <div className="text-sm font-semibold text-ink truncate max-w-[240px]">{name}</div>
                            <div className="text-xs text-ink-2 tabular-nums">{c.customer_phone ?? '—'}</div>
                            <div title={c.session_id} className="font-mono text-[10.5px] text-ink-3 truncate max-w-[240px] mt-px">
                              {c.session_id}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className={`${td} px-3 whitespace-nowrap leading-[1.35]`}>
                        <div className="font-medium text-ink">{formatDate(c.started_at)}</div>
                        <div className="text-xs text-ink-3">{formatTime(c.started_at)}</div>
                      </td>
                      <td className={`${td} px-3 text-right tabular-nums font-medium text-ink-2`}>{c.message_count}</td>
                      <td className={`${td} px-3 whitespace-nowrap`}>
                        <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
                          {esBot ? <Bot size={14} /> : <User size={14} />}
                          {esBot ? 'Bot' : 'Cliente'}
                          {c.contiene_array && (
                            <span title='Un mensaje contiene el texto "Array"' className="inline-flex text-warn-fg">
                              <AlertTriangle size={13} />
                            </span>
                          )}
                        </span>
                      </td>
                      <td className={`${td} ${conSubcategoria ? 'px-3' : 'pl-3 pr-5'}`}>
                        <CategoryBadge categoria={c.categoria} />
                      </td>
                      {conSubcategoria && (
                        <td className={`${td} pl-3 pr-5`}>
                          {c.subcategoria_label ? (
                            <span className="inline-block px-2.5 py-[3px] rounded-lg bg-surface-2 text-ink-2 text-xs font-medium whitespace-nowrap">
                              {c.subcategoria_label}
                            </span>
                          ) : (
                            <span className="text-ink-3">—</span>
                          )}
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {!loading && items.length === 0 && (
              <div className="px-5 py-12 text-center text-ink-3 text-[13px]">No se encontraron conversaciones con estos filtros.</div>
            )}
            {loading && items.length === 0 && <div className="px-5 py-12 text-center text-ink-3 text-[13px]">Cargando…</div>}
          </div>

          <footer className="flex items-center justify-between gap-3 px-5 py-3 border-t border-line-soft text-xs text-ink-2 flex-wrap">
            <span>
              Mostrando{' '}
              <strong className="text-ink font-semibold">
                {formatNumber(desdeFila)}–{formatNumber(hastaFila)}
              </strong>{' '}
              de <strong className="text-ink font-semibold">{formatNumber(total)}</strong> conversaciones
              {loading && items.length > 0 && <span className="text-ink-3"> · actualizando…</span>}
            </span>
            <div className="flex items-center gap-1">
              <Pagination page={page} totalPages={totalPages} onChange={setPage} />
              <label className="relative ml-2 flex items-center h-[30px] rounded-lg border border-line text-ink-2 hover:border-ink-3 focus-within:border-accent">
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  aria-label="Conversaciones por página"
                  className="appearance-none bg-transparent outline-0 border-0 pl-2.5 pr-7 h-full text-xs cursor-pointer"
                >
                  {PAGE_SIZE_OPTIONS.map((size) => (
                    <option key={size} value={size}>
                      {size} por página
                    </option>
                  ))}
                </select>
                <ChevronDown size={12} className="absolute right-2.5 pointer-events-none" />
              </label>
            </div>
          </footer>
        </section>

        <AnimatePresence>
          {selectedSessionId && (
            <ConversationSidePanel
              key={selectedSessionId}
              sessionId={selectedSessionId}
              overlay={narrow}
              onClose={() => setSelectedSessionId(null)}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
