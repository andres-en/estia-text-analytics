import { Calendar, FilterX, Search } from 'lucide-react'
import { useCategorias } from '../context/CategoriasContext'

export interface FilterState {
  q: string
  categorias: string[]
  desde: string
  hasta: string
  iniciadaPor: '' | 'CUSTOMER' | 'BOT'
  contieneArray: boolean
}

interface Props {
  value: FilterState
  onChange: (patch: Partial<FilterState>) => void
}

export default function FilterBar({ value, onChange }: Props) {
  const { categorias, meta } = useCategorias()
  const toggleCategoria = (cat: string) => {
    const has = value.categorias.includes(cat)
    onChange({
      categorias: has ? value.categorias.filter((c) => c !== cat) : [...value.categorias, cat],
    })
  }

  const hasFilters =
    value.q ||
    value.categorias.length > 0 ||
    value.desde ||
    value.hasta ||
    value.iniciadaPor ||
    value.contieneArray

  return (
    <div className="surface p-4 mb-4 flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Search (phone or SESSION_ID)</label>
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            <input
              type="text"
              value={value.q}
              onChange={(e) => onChange({ q: e.target.value })}
              placeholder="573..."
              className="border border-gray-200 rounded-lg pl-8 pr-2 py-1.5 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-black/5"
            />
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">From</label>
          <div className="relative">
            <Calendar size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            <input
              type="date"
              value={value.desde}
              onChange={(e) => onChange({ desde: e.target.value })}
              className="border border-gray-200 rounded-lg pl-8 pr-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/5"
            />
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">To</label>
          <div className="relative">
            <Calendar size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            <input
              type="date"
              value={value.hasta}
              onChange={(e) => onChange({ hasta: e.target.value })}
              className="border border-gray-200 rounded-lg pl-8 pr-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/5"
            />
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Category</label>
          <div className="flex flex-wrap gap-2">
            {categorias.map((cat) => {
              const active = value.categorias.includes(cat.id)
              const { color } = meta(cat.id)
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => toggleCategoria(cat.id)}
                  className="text-xs rounded-full px-3 py-1.5 border transition-colors"
                  style={
                    active
                      ? { backgroundColor: `${color}1a`, color, borderColor: 'transparent' }
                      : { borderColor: '#e5e7eb', color: '#6b7280' }
                  }
                >
                  {cat.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4 pt-3 border-t border-gray-100">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-500">Started by</span>
          <select
            value={value.iniciadaPor}
            onChange={(e) => onChange({ iniciadaPor: e.target.value as FilterState['iniciadaPor'] })}
            className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/5"
          >
            <option value="">All</option>
            <option value="CUSTOMER">Client</option>
            <option value="BOT">Bot</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={value.contieneArray}
            onChange={(e) => onChange({ contieneArray: e.target.checked })}
            className="rounded border-gray-300"
          />
          Contiene "Array"
        </label>
        {hasFilters && (
          <button
            type="button"
            onClick={() =>
              onChange({ q: '', categorias: [], desde: '', hasta: '', iniciadaPor: '', contieneArray: false })
            }
            className="btn-secondary text-xs px-3 py-1.5 ml-auto"
          >
            <FilterX size={14} />
            Clear filters
          </button>
        )}
      </div>
    </div>
  )
}
