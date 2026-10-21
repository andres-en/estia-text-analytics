import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'motion/react'
import { materialize, springDrawer, springSettle } from '../lib/motionPresets'

interface Props {
  open: boolean
  onClose: () => void
  children: ReactNode
  className?: string
}

/**
 * Diálogo centrado sobre un velo oscuro con desenfoque; Escape o clic afuera lo cierra.
 * Se monta en <body> con un portal: cualquier ancestro con transform (las
 * animaciones de entrada de página y pestaña) recortaría el `position: fixed`.
 */
export default function Modal({ open, onClose, children, className }: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={springSettle}
          className="fixed inset-0 z-50 bg-[rgba(15,23,42,.45)] backdrop-blur-[2px] flex items-center justify-center p-4"
          onClick={onClose}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            initial={materialize.initial}
            animate={materialize.animate}
            exit={materialize.exit}
            transition={springDrawer}
            onClick={(e) => e.stopPropagation()}
            className={`bg-surface rounded-2xl shadow-pop p-[22px] max-w-full max-h-[85vh] overflow-y-auto ${className ?? 'w-[440px]'}`}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
