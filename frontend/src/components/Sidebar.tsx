import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronLeft, ChevronsUpDown, LayoutDashboard, LogOut, MessageSquare, SlidersHorizontal, type LucideIcon } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { materialize, springPress, springSettle } from '../lib/motionPresets'
import { initials } from '../lib/format'
import { rolLabel } from '../lib/roles'

const COLLAPSE_KEY = 'sidebar-collapsed'
const WIDTH_EXPANDED = 248
const WIDTH_COLLAPSED = 72

function readStoredCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === '1'
  } catch {
    return false
  }
}

function NavItem({ to, end, icon: Icon, label, collapsed }: { to: string; end?: boolean; icon: LucideIcon; label: string; collapsed: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        `flex items-center gap-2.5 px-2.5 py-[9px] rounded-[10px] whitespace-nowrap overflow-hidden transition-colors ${
          isActive ? 'bg-accent-soft text-accent-ink font-semibold' : 'text-ink-2 font-medium hover:bg-surface-2 hover:text-ink'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon size={18} strokeWidth={1.8} className={`shrink-0 ${isActive ? 'text-accent' : ''}`} />
          {!collapsed && <span>{label}</span>}
        </>
      )}
    </NavLink>
  )
}

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(readStoredCollapsed)

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0')
    } catch {
      // almacenamiento no disponible (modo privado, etc.) — no es crítico
    }
  }, [collapsed])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const subtitulo = [user?.cliente_activo?.nombre_cliente, user ? rolLabel(user.rol) : null].filter(Boolean).join(' · ')

  return (
    <motion.aside
      animate={{ width: collapsed ? WIDTH_COLLAPSED : WIDTH_EXPANDED }}
      initial={false}
      transition={springSettle}
      className="relative shrink-0 h-screen flex flex-col bg-surface border-r border-line-soft pt-5 px-3 pb-3.5 box-border z-30"
    >
      <button
        type="button"
        onClick={() => {
          setCollapsed((c) => !c)
          setMenuOpen(false)
        }}
        title={collapsed ? 'Expandir menú' : 'Contraer menú'}
        className="absolute -right-3 top-7 w-6 h-6 rounded-full border border-line bg-surface text-ink-3 hover:text-ink hover:border-ink-3 flex items-center justify-center shadow-[0_1px_3px_rgba(15,23,42,.08)] z-10"
      >
        <ChevronLeft size={13} strokeWidth={2.2} className={`transition-transform duration-200 ${collapsed ? 'rotate-180' : ''}`} />
      </button>

      <div className="flex items-center gap-2.5 px-1.5 mb-7 overflow-hidden">
        <img src="/logo-estia-icon.png" alt="ESTIA" className="w-8 h-8 object-contain shrink-0" />
        {!collapsed && (
          <div className="leading-[1.15] whitespace-nowrap">
            <div className="text-[15px] font-bold tracking-[.06em] text-ink">ESTIA</div>
            <div className="text-[11px] text-ink-3 mt-0.5">Conversation Intelligence</div>
          </div>
        )}
      </div>

      {!collapsed && (
        <div className="text-[11px] font-medium tracking-[.08em] uppercase text-ink-3 px-2.5 mb-2">Menú</div>
      )}
      <nav className="flex flex-col gap-0.5">
        <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" collapsed={collapsed} />
        <NavItem to="/" end icon={MessageSquare} label="Conversaciones" collapsed={collapsed} />
        {user?.es_super_admin && (
          <NavItem to="/configuracion" icon={SlidersHorizontal} label="Configuración" collapsed={collapsed} />
        )}
      </nav>

      <div className="mt-auto relative">
        <AnimatePresence>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <motion.div
                initial={materialize.initial}
                animate={materialize.animate}
                exit={materialize.exit}
                transition={springPress}
                className="absolute bottom-[calc(100%+8px)] left-0 right-0 min-w-[200px] bg-surface border border-line-soft rounded-xl shadow-pop p-1.5 z-50"
              >
                <div className="px-2.5 pt-2 pb-2.5 border-b border-line-soft mb-1">
                  <div className="text-xs text-ink-3">Sesión iniciada como</div>
                  <div className="text-[13px] font-medium text-ink truncate">{user?.email}</div>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-[13px] text-left text-ink-2 hover:bg-surface-2 hover:text-ink"
                >
                  <LogOut size={15} />
                  Cerrar sesión
                </button>
              </motion.div>
            </>
          )}
        </AnimatePresence>
        <button
          type="button"
          onClick={() => setMenuOpen((o) => !o)}
          title={collapsed ? user?.nombre_usuario : undefined}
          className="w-full flex items-center gap-2.5 p-2 rounded-xl border border-line-soft bg-bg hover:border-line hover:bg-surface-2 text-left overflow-hidden transition-colors"
        >
          <div className="relative shrink-0">
            <div className="w-[34px] h-[34px] rounded-full bg-[linear-gradient(135deg,#2f8cf5,#1a3fa8)] text-white flex items-center justify-center text-xs font-semibold tracking-[.02em]">
              {initials(user?.nombre_usuario)}
            </div>
            <span className="absolute -right-px -bottom-px w-2.5 h-2.5 rounded-full bg-[#10b981] border-2 border-bg" />
          </div>
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0 leading-[1.25]">
                <div className="text-[13px] font-medium text-ink truncate">{user?.nombre_usuario}</div>
                <div className="text-[11px] font-light text-ink-3 tracking-[.06em] truncate">{subtitulo}</div>
              </div>
              <ChevronsUpDown size={14} className="text-ink-3 shrink-0" />
            </>
          )}
        </button>
      </div>
    </motion.aside>
  )
}
