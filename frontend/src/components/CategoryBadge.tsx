import { useCategorias } from '../context/CategoriasContext'
import { categoryInk, categorySoftBg } from '../lib/categoryColors'

export default function CategoryBadge({ categoria, size = 'md' }: { categoria: string | null; size?: 'sm' | 'md' | 'lg' }) {
  const { meta } = useCategorias()
  const { label, color } = meta(categoria)
  const cls =
    size === 'sm'
      ? 'h-[22px] px-[9px] text-[11.5px] gap-[5px]'
      : size === 'lg'
        ? 'h-[26px] px-[11px] text-[12.5px] gap-1.5'
        : 'h-6 px-2.5 text-xs gap-1.5'
  return (
    <span
      title={label}
      className={`inline-flex items-center max-w-full rounded-full font-semibold whitespace-nowrap ${cls}`}
      style={{ backgroundColor: categorySoftBg(color), color: categoryInk(color) }}
    >
      <span className={`rounded-full bg-current shrink-0 ${size === 'sm' ? 'w-[5px] h-[5px]' : 'w-1.5 h-1.5'}`} />
      <span className="truncate">{label}</span>
    </span>
  )
}
