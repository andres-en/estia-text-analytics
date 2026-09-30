import type { Transition } from 'motion/react'

/** Crítico (sin rebote): para UI que aparece por sí sola, no por un gesto. */
export const springSettle: Transition = { type: 'spring', bounce: 0, duration: 0.4 }

/** Un poco de rebote: solo para paneles/hojas que el usuario podría arrastrar o lanzar. */
export const springDrawer: Transition = { type: 'spring', bounce: 0.15, duration: 0.35 }

/** Feedback de presión, casi instantáneo. */
export const springPress: Transition = { type: 'spring', bounce: 0, duration: 0.2 }

export const fadeIn = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
}

export const materialize = {
  initial: { opacity: 0, scale: 0.96 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.97 },
}

/** El panel entra y sale por el mismo camino (derecha), como pide la consistencia espacial. */
export const slideFromRight = {
  initial: { opacity: 0, x: 24 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 24 },
}
