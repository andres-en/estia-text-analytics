import { useEffect, useRef } from 'react'
import { ChevronDown, RotateCcw, Search, User } from 'lucide-react'
import { useCategorias } from '../context/CategoriasContext'
import DateRangeField from './DateRangeField'
import Switch from './Switch'
import { categoryInk, categorySoftBg } from '../lib/categoryColors'

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

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

export default function FilterBar({ value, onChange }: Props) {
  const { categorias, meta } = useCategorias()
  const searchRef = useRef<HTMLInputElement>(null)

  // ⌘K / Ctrl+K enfoca la búsqueda desde cualquier parte de la página.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

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
    <section className="surface p-3.5 flex flex-col gap-3">
      <div className="flex flex-wrap gap-2 items-center">
        <label className="field flex-[2_1_260px]">
          <Search size={16} className="text-ink-3 shrink-0" />
          <input
            ref={searchRef}
            type="text"
            value={value.q}
            onChange={(e) => onChange({ q: e.target.value })}
            placeholder="Buscar por teléfono o SESSION_ID…"
          />
          <kbd className="font-mono text-[11px] text-ink-3 border border-line rounded-md px-1.5 py-px bg-surface">
            {isMac ? '⌘K' : 'Ctrl K'}
          </kbd>
        </label>
        <DateRangeField
          desde={value.desde}
          hasta={value.hasta}
          onChange={(patch) => onChange(patch)}
          className="flex-[1_0_auto]"
        />
        <label className="field relative flex-[0_1_190px] pr-2.5">
          <User size={15} className="text-ink-3 shrink-0" />
          <span className="text-xs text-ink-3 whitespace-nowrap">Iniciada por</span>
          <select
            value={value.iniciadaPor}
            onChange={(e) => onChange({ iniciadaPor: e.target.value as FilterState['iniciadaPor'] })}
            className="font-medium pr-4"
          >
            <option value="">Todas</option>
            <option value="CUSTOMER">Cliente</option>
            <option value="BOT">Bot</option>
          </select>
          <ChevronDown size={14} className="absolute right-2.5 text-ink-3 pointer-events-none" />
        </label>
        <Switch checked={value.contieneArray} onChange={(contieneArray) => onChange({ contieneArray })}>
          Contiene “Array”
        </Switch>
      </div>

      <div className="flex items-center gap-2 flex-wrap pt-3 border-t border-line-soft">
        <span className="text-xs font-medium text-ink-3 mr-1">Categoría</span>
        {categorias.map((cat) => {
          const active = value.categorias.includes(cat.id)
          const { color } = meta(cat.id)
          return (
            <button
              key={cat.id}
              type="button"
              aria-pressed={active}
              onClick={() => toggleCategoria(cat.id)}
              className="flex items-center gap-1.5 h-[30px] px-3 rounded-full border text-xs font-medium hover:border-ink-3 transition-colors"
              style={
                active
                  ? { backgroundColor: categorySoftBg(color), color: categoryInk(color), borderColor: 'transparent' }
                  : { backgroundColor: 'var(--surface)', color: 'var(--ink-2)', borderColor: 'var(--border)' }
              }
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
              {cat.label}
            </button>
          )
        })}
        {hasFilters && (
          <button
            type="button"
            onClick={() =>
              onChange({ q: '', categorias: [], desde: '', hasta: '', iniciadaPor: '', contieneArray: false })
            }
            className="ml-auto flex items-center gap-1.5 h-[30px] px-2.5 rounded-lg text-xs font-medium text-ink-2 hover:bg-surface-2 hover:text-ink"
          >
            <RotateCcw size={13} />
            Limpiar filtros
          </button>
        )}
      </div>
    </section>
  )
}
