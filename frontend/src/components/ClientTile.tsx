// Paleta de "azulejos" para distinguir clientes de un vistazo (selector del
// encabezado, tabla de Clientes). El color sale del nombre, así un cliente
// conserva el suyo en todas las pantallas.
const TILES: [string, string][] = [
  ['#fde68a', '#92400e'],
  ['#d1fae5', '#065f46'],
  ['#ede9fe', '#6d28d9'],
  ['#e0f2fe', '#075985'],
  ['#ffe4e6', '#9f1239'],
]

function tileFor(name: string): [string, string] {
  let h = 0
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return TILES[h % TILES.length]!
}

export default function ClientTile({ name, size = 'sm' }: { name: string; size?: 'sm' | 'md' }) {
  const [bg, fg] = tileFor(name)
  const md = size === 'md'
  return (
    <span
      className={`shrink-0 flex items-center justify-center font-bold ${
        md ? 'w-9 h-9 rounded-[10px] text-[13px]' : 'w-5 h-5 rounded-md text-[10px]'
      }`}
      style={{ backgroundColor: bg, color: fg }}
    >
      {name.trim()[0]?.toUpperCase() ?? '?'}
    </span>
  )
}
