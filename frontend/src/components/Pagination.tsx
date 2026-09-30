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
        aria-label="Previous page"
        className="btn-secondary w-8 h-8 p-0 disabled:opacity-40"
      >
        <ChevronLeft size={15} />
      </button>
      {pageList(page, totalPages).map((p, i) =>
        p === 'ellipsis' ? (
          <span key={`ellipsis-${i}`} className="w-8 h-8 flex items-center justify-center text-gray-400 text-sm">
            …
          </span>
        ) : (
          <button
            key={p}
            type="button"
            onClick={() => onChange(p)}
            aria-current={p === page ? 'page' : undefined}
            className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
              p === page ? 'bg-[var(--ink-1)] text-white' : 'text-gray-500 hover:bg-black/[0.04]'
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
        aria-label="Next page"
        className="btn-secondary w-8 h-8 p-0 disabled:opacity-40"
      >
        <ChevronRight size={15} />
      </button>
    </div>
  )
}
