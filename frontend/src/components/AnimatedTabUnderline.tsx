import { motion } from 'motion/react'
import { springSettle } from '../lib/motionPresets'

/**
 * Subrayado que se desliza a la pestaña activa en vez de saltar. Cada grupo de
 * pestañas necesita su propio `layoutId` para no animarse contra otro grupo.
 */
export default function AnimatedTabUnderline({ layoutId, className }: { layoutId: string; className?: string }) {
  return (
    <motion.span
      layoutId={layoutId}
      className={className ?? 'absolute left-0 right-0 -bottom-[1px] h-[2px] bg-[var(--wa-green)] rounded-full'}
      transition={springSettle}
    />
  )
}
