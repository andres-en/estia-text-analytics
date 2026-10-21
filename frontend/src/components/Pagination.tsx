import { ChevronLeft, ChevronRight } from 'lucide-react'

function pageList(current: number, total: number): (number | 'ellipsis')[] {
  if (total <= 1) return [1]
  const delta = 1
  const left = Math.max(2, current - delta)
  const right = Math.min(total - 1, current + delta)
  const list: (number | 'ellipsis')[] = [1]
  if (left > 2) list.push('ellipsis')
  for (let i = left; i <= right; i++) list.push(i)
  if (right < total - 1) list.push('ellipsis')
  list.push(total)
  return list
}

const arrowClass =
  'w-[30px] h-[30px] rounded-lg border border-line bg-surface text-ink-2 flex items-center justify-center hover:border-ink-3 disabled:text-ink-3 disabled:opacity-60 disabled:hover:border-line'

export default function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number
  totalPages: number
  onChange: (page: number) => void
}) {
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => onChange(Math.max(page - 1, 1))}
        disabled={page <= 1}
        aria-label="Página anterior"
        className={arrowClass}
      >
        <ChevronLeft size={14} />
      </button>
      {pageList(page, totalPages).map((p, i) =>
        p === 'ellipsis' ? (
          <span key={`ellipsis-${i}`} className="px-1 text-ink-3">
            …
          </span>
        ) : (
          <button
            key={p}
            type="button"
            onClick={() => onChange(p)}
            aria-current={p === page ? 'page' : undefined}
            className={`min-w-[30px] h-[30px] px-1 rounded-lg text-xs transition-colors ${
              p === page ? 'bg-accent-soft text-accent-ink font-semibold' : 'text-ink-2 hover:bg-surface-2'
            }`}
          >
            {p}
          </button>
        ),
      )}
      <button
        type="button"
        onClick={() => onChange(Math.min(page + 1, totalPages))}
        disabled={page >= totalPages}
        aria-label="Página siguiente"
        className={arrowClass}
      >
        <ChevronRight size={14} />
      </button>
    </div>
  )
}
