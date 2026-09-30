import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import { Bell, ChevronDown, LogOut } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchClientes, type ClienteRef } from '../api/client'
import { materialize, springPress } from '../lib/motionPresets'

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

  return (
    <div className="relative">
      <select
        className="appearance-none text-sm bg-white border border-gray-200 rounded-full pl-3.5 pr-8 py-1.5 text-gray-700 cursor-pointer hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-black/5 transition-colors"
        value={user?.cliente_activo?.id_cliente ?? ''}
        onChange={async (e) => {
          await cambiarClienteActivo(e.target.value ? Number(e.target.value) : null)
          // Recarga completa: todas las páginas (conversaciones, dashboard) ya
          // resolvieron sus datos contra la base del cliente anterior.
          window.location.reload()
        }}
      >
        <option value="" disabled>
          Select a client
        </option>
        {opciones.map((c) => (
          <option key={c.id_cliente} value={c.id_cliente}>
            {c.nombre_cliente}
          </option>
        ))}
      </select>
      <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
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
        title="Notifications"
        className="btn-secondary w-9 h-9 p-0"
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
              className="surface absolute right-0 mt-2 w-56 p-3 text-xs text-gray-500 z-50"
            >
              No new notifications.
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function AccountCluster() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const puedeElegirCliente = Boolean(user && user.clientes.length !== 1)

  return (
    <div className="flex items-center gap-2 shrink-0">
      {puedeElegirCliente && <ClienteActivoSwitcher />}
      <NotificationsButton />
      <button type="button" onClick={handleLogout} title="Sign out" className="btn-primary w-9 h-9 p-0">
        <LogOut size={16} />
      </button>
    </div>
  )
}
