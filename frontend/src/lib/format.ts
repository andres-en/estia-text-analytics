export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

// Fecha corta + hora, para el timestamp de cada mensaje dentro de una conversación
// (formatDateTime es más largo — año incluido — pensado para encabezados, no para
// repetirse en cada burbuja). Relleno manual con padStart a propósito: pedirle a
// Intl día+mes en 2 dígitos SIN año (`{day:'2-digit', month:'2-digit'}`) no rellena
// el cero en Chromium con locale es-CO — da "5/8" en vez de "05/08".
export function formatDateAndTime(iso: string): string {
  const d = new Date(iso)
  const day = String(d.getDate()).padStart(2, '0')
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  return `${day}/${month} ${time}`
}

export function formatDateRange(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { day: '2-digit', month: '2-digit' })
}
