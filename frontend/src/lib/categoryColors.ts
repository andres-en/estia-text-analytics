// Los colores de categoría vienen de cada campaña (hex arbitrario), así que el
// fondo suave y el texto de alto contraste se derivan con color-mix en vez de
// una tabla fija de tonos.
export function categorySoftBg(color: string, pct = 14): string {
  return `color-mix(in srgb, ${color} ${pct}%, transparent)`
}

export function categoryInk(color: string): string {
  return `color-mix(in srgb, ${color} 72%, var(--ink))`
}
