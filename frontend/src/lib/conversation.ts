export function metodoLabel(metodo: string | null): string {
  if (metodo === 'RULE') return 'Clasificado por reglas'
  if (metodo === 'AI') return 'Clasificado por IA'
  return 'Pendiente de clasificación'
}

/** Nombre a mostrar de un contacto: su nombre de WhatsApp, o el teléfono si no tiene. */
export function displayName(t: { customer_name: string | null; customer_phone: string | null }): string {
  return t.customer_name?.trim() || t.customer_phone || 'Sin nombre'
}
