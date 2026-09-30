import { useCategorias } from '../context/CategoriasContext'

export default function CategoryBadge({ categoria }: { categoria: string | null }) {
  const { meta } = useCategorias()
  const { label, color } = meta(categoria)
  return (
    <span
      className="inline-block rounded-full px-3 py-0.5 text-xs font-semibold whitespace-nowrap"
      style={{ backgroundColor: `${color}1a`, color }}
    >
      {label}
    </span>
  )
}
