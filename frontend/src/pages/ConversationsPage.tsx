import { useEffect, useMemo, useState } from 'react'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { useSearchParams } from 'react-router-dom'
import { AnimatePresence } from 'motion/react'
import { AlertTriangle, Bot, ChevronDown, Download, MessagesSquare, User } from 'lucide-react'
import { exportConversations, fetchConversations, type ConversationSummary } from '../api/client'
import FilterBar, { type FilterState } from '../components/FilterBar'
import UploadPanel from '../components/UploadPanel'
import CategoryBadge from '../components/CategoryBadge'
import ConversationSidePanel from '../components/ConversationSidePanel'
import PageHeader from '../components/PageHeader'
import Pagination from '../components/Pagination'
import { formatDateTime } from '../lib/format'
import { useCategorias } from '../context/CategoriasContext'
import { FLAG_LABELS } from '../lib/flags'

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200]
const DEFAULT_PAGE_SIZE = 50

const columnHelper = createColumnHelper<ConversationSummary>()

const columns = [
  columnHelper.accessor('session_id', {
    header: 'SESSION_ID',
    cell: (info) => <span className="font-mono text-xs text-[var(--wa-green-dark)]">{info.getValue()}</span>,
  }),
  columnHelper.accessor('customer_phone', { header: 'Phone', cell: (info) => info.getValue() ?? '-' }),
  columnHelper.accessor('customer_name', { header: 'Name', cell: (info) => info.getValue() ?? '-' }),
  columnHelper.accessor('started_at', { header: 'Start', cell: (info) => formatDateTime(info.getValue()) }),
  columnHelper.accessor('message_count', { header: 'Messages' }),
  columnHelper.accessor('iniciada_por', {
    header: 'Origin',
    cell: (info) => {
      const v = info.getValue()
      const esBot = v === 'BOT'
      const contieneArray = info.row.original.contiene_array
      return (
        <span className="inline-flex items-center gap-1.5 text-xs">
          <span className={`inline-flex items-center gap-1 ${esBot ? 'text-gray-500' : 'text-[var(--wa-green-dark)]'}`}>
            {esBot ? <Bot size={14} /> : <User size={14} />}
            {esBot ? 'Bot' : 'Client'}
          </span>
          {contieneArray && (
            <span title='A message contains the text "Array"' className="inline-flex text-amber-600">
              <AlertTriangle size={13} />
            </span>
          )}
        </span>
      )
    },
  }),
  columnHelper.accessor('categoria', {
    header: 'Category',
    cell: (info) => <CategoryBadge categoria={info.getValue()} />,
  }),
]

// Solo se agrega cuando el cliente tiene subcategorías (ej. "Motivo del interés" en Acme).
const subcategoriaColumn = (header: string) =>
  columnHelper.accessor('subcategoria_label', {
    header,
    cell: (info) =>
      info.getValue() ? (
        <span className="text-xs rounded-full bg-gray-100 text-gray-700 px-2 py-0.5">{info.getValue()}</span>
      ) : (
        <span className="text-gray-300">—</span>
      ),
  })

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

  // Deep link desde las StatCards del dashboard (`/?categoria=X`): se consume
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
      setExportError(e instanceof Error ? e.message : 'Export failed')
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
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load the conversations')
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

  const { subcategorias } = useCategorias()
  const tableColumns = useMemo(
    () => (subcategorias.items.length > 0 ? [...columns, subcategoriaColumn(subcategorias.etiqueta)] : columns),
    [subcategorias],
  )

  const table = useReactTable({
    data: items,
    columns: tableColumns,
    getRowId: (row) => row.session_id,
    getCoreRowModel: getCoreRowModel(),
  })

  const totalPages = Math.max(Math.ceil(total / pageSize), 1)
  const columnCount = tableColumns.length

  return (
    <div>
      <PageHeader
        icon={MessagesSquare}
        title="Conversations"
        subtitle="Browse and review every classified conversation."
      />
      <div className="flex items-start justify-end gap-2 mb-4">
        <button
          type="button"
          onClick={handleExport}
          disabled={exporting}
          className="btn-secondary text-sm px-4 py-2 disabled:opacity-50 flex-shrink-0"
        >
          <Download size={16} />
          {exporting ? 'Exporting...' : 'Export to Excel'}
        </button>
        <UploadPanel onUploaded={() => setReloadToken((t) => t + 1)} />
      </div>
      {exportError && <p className="text-sm text-red-600 mb-4">{exportError}</p>}
      {flag && (
        <div className="bg-[var(--wa-green-dark)]/10 border border-[var(--wa-green-dark)]/30 rounded-lg px-4 py-2 mb-4 flex items-center gap-2 text-sm">
          <span className="text-gray-600">
            Filtered by indicator: <strong>{FLAG_LABELS[flag] ?? flag}</strong>
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
            className="text-[var(--wa-green-dark)] underline ml-auto"
          >
            Remove filter
          </button>
        </div>
      )}
      <FilterBar value={filters} onChange={(patch) => setFilters((f) => ({ ...f, ...patch }))} />

      <div className="flex flex-col lg:flex-row gap-4 items-start">
        <div className="surface overflow-hidden flex-1 min-w-0 w-full">
          {error && <p className="text-sm text-red-600 p-3">{error}</p>}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] text-sm">
              <thead className="text-gray-400 text-xs uppercase tracking-wide">
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>
                    {hg.headers.map((header) => (
                      <th key={header.id} className="text-left px-3 py-2.5 font-semibold border-b border-gray-100">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedSessionId(row.original.session_id)}
                    className={`border-t border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors duration-150 ${
                      selectedSessionId === row.original.session_id ? 'bg-[var(--wa-green-dark)]/5' : ''
                    }`}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-2">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
                {!loading && items.length === 0 && (
                  <tr>
                    <td colSpan={columnCount} className="text-center text-gray-400 py-8">
                      No conversations found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between px-3 py-3 border-t border-gray-100 text-sm">
            <span className="text-gray-500">
              Showing {items.length === 0 ? 0 : (page - 1) * pageSize + 1} to{' '}
              {Math.min(page * pageSize, total)} of {total.toLocaleString('en-US')} conversations
              {loading && ' · loading...'}
            </span>
            <div className="flex items-center gap-3">
              <Pagination page={page} totalPages={totalPages} onChange={setPage} />
              <div className="relative">
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  className="appearance-none text-sm bg-white border border-gray-200 rounded-full pl-3 pr-8 py-1.5 text-gray-700 cursor-pointer hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-black/5"
                >
                  {PAGE_SIZE_OPTIONS.map((size) => (
                    <option key={size} value={size}>
                      {size} per page
                    </option>
                  ))}
                </select>
                <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
              </div>
            </div>
          </div>
        </div>

        <AnimatePresence>
          {selectedSessionId && (
            <ConversationSidePanel
              key={selectedSessionId}
              sessionId={selectedSessionId}
              onClose={() => setSelectedSessionId(null)}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
