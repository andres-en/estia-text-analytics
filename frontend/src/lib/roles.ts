import type { BadgeTone } from '../components/Badge'

// Nombres internos de rol (tabla `rol`) → etiqueta y tono de badge en la UI.
const ROL_LABEL: Record<string, string> = {
  super_admin: 'SuperAdmin',
  admin: 'Admin',
  user: 'Usuario',
}

const ROL_TONE: Record<string, BadgeTone> = {
  super_admin: 'warn',
  admin: 'accent',
  user: 'ok',
}

export function rolLabel(nombreRol: string): string {
  return ROL_LABEL[nombreRol] ?? nombreRol
}

export function rolTone(nombreRol: string): BadgeTone {
  return ROL_TONE[nombreRol] ?? 'mute'
}
