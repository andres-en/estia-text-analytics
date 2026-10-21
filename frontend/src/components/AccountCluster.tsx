import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Bell, ChevronDown } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchClientes, type ClienteRef } from '../api/client'
import { materialize, springPress } from '../lib/motionPresets'
import ClientTile from './ClientTile'

// Píldora con el cliente activo. Un <select> nativo transparente encima hace
// el trabajo (teclado, accesibilidad, lista del sistema) mientras la píldora
// conserva el diseño; si el usuario tiene un solo cliente, es solo informativa.
function ClienteActivoSwitcher() {
  const { user, cambiarClienteActivo } = useAuth()
  const [opciones, setOpciones] = useState<ClienteRef[]>([])

  useEffect(() => {
    if (user?.es_super_admin) {
      // El super admin puede activar cualquier cliente del sistema, no solo
      // los suyos (no tiene ninguno fijo).
      fetchClientes().then(setOpciones).catch(() => setOpciones([]))
    } else {
      setOpciones(user?.clientes ?? [])
    }
  }, [user])

  const puedeElegir = Boolean(user && (user.es_super_admin || user.clientes.length !== 1))
  const nombre = user?.cliente_activo?.nombre_cliente

  return (
    <div className="relative flex items-center gap-2 h-[38px] pl-2.5 pr-3 rounded-[10px] border border-line bg-surface text-ink text-[13px] font-semibold hover:border-ink-3 focus-within:border-accent transition-colors">
      {nombre ? <ClientTile name={nombre} /> : null}
      <span className={nombre ? '' : 'text-ink-3 font-medium'}>{nombre ?? 'Selecciona un cliente'}</span>
      {puedeElegir && (
        <>
          <ChevronDown size={14} className="text-ink-3" />
          <select
            aria-label="Cliente activo"
            className="absolute inset-0 w-full opacity-0 cursor-pointer"
            value={user?.cliente_activo?.id_cliente ?? ''}
            onChange={async (e) => {
              await cambiarClienteActivo(e.target.value ? Number(e.target.value) : null)
              // Recarga completa: todas las páginas (conversaciones, dashboard) ya
              // resolvieron sus datos contra la base del cliente anterior.
              window.location.reload()
            }}
          >
            <option value="" disabled>
              Selecciona un cliente
            </option>
            {opciones.map((c) => (
              <option key={c.id_cliente} value={c.id_cliente}>
                {c.nombre_cliente}
              </option>
            ))}
          </select>
        </>
      )}
    </div>
  )
}

function NotificationsButton() {
  const [open, setOpen] = useState(false)

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="Notificaciones"
        className="w-[38px] h-[38px] rounded-[10px] border border-line bg-surface text-ink-2 hover:text-ink hover:border-ink-3 flex items-center justify-center transition-colors"
      >
        <Bell size={16} />
      </button>
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={materialize.initial}
              animate={materialize.animate}
              exit={materialize.exit}
              transition={springPress}
              className="absolute right-0 mt-2 w-60 p-3 text-xs text-ink-3 z-50 bg-surface border border-line-soft rounded-xl shadow-pop"
            >
              No hay notificaciones nuevas.
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function AccountCluster() {
  return (
    <div className="flex items-center gap-2 shrink-0">
      <ClienteActivoSwitcher />
      <NotificationsButton />
    </div>
  )
}
