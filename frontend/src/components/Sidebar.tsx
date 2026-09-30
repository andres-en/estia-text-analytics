import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Settings,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { springSettle } from '../lib/motionPresets'

const COLLAPSE_KEY = 'sidebar-collapsed'
const WIDTH_EXPANDED = 240
const WIDTH_COLLAPSED = 72

function readStoredCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === '1'
  } catch {
    return false
  }
}

function navLinkClass(collapsed: boolean) {
  return ({ isActive }: { isActive: boolean }) =>
    `relative flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
      collapsed ? 'justify-center px-0' : ''
    } ${isActive ? 'text-[var(--ink-1)] font-semibold' : 'text-gray-500 hover:text-gray-800 hover:bg-black/[0.03]'}`
}

function SidebarHighlight() {
  return (
    <motion.span
      layoutId="sidebar-active-highlight"
      className="absolute inset-0 bg-black/[0.04] rounded-lg -z-10"
      transition={springSettle}
    />
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

  const initial = user?.nombre_usuario?.[0]?.toUpperCase() ?? '?'
  const linkClass = navLinkClass(collapsed)

  return (
    <motion.aside
      animate={{ width: collapsed ? WIDTH_COLLAPSED : WIDTH_EXPANDED }}
      transition={springSettle}
      className="relative shrink-0 h-screen sticky top-0 flex flex-col bg-white border-r border-black/5 px-3 py-4"
    >
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        title={collapsed ? 'Expand menu' : 'Collapse menu'}
        className="absolute -right-3 top-6 w-6 h-6 rounded-full border border-gray-200 bg-white shadow-sm flex items-center justify-center text-gray-400 hover:text-gray-700 hover:border-gray-300 z-10"
      >
        {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
      </button>

      <div className={`flex items-center gap-2.5 mb-6 ${collapsed ? 'justify-center px-0' : 'px-2'}`}>
        <img src="/logo-estia-icon.png" alt="ESTIA" className="w-9 h-9 object-contain shrink-0" />
        {!collapsed && (
          <div className="leading-tight whitespace-nowrap">
            <div className="text-sm font-bold tracking-wide text-[var(--ink-1)]">ESTIA</div>
            <div className="text-[10px] text-gray-400 -mt-0.5">Conversation Intelligence</div>
          </div>
        )}
      </div>

      <nav className="flex flex-col gap-1">
        <NavLink to="/dashboard" className={linkClass} title={collapsed ? 'Dashboard' : undefined}>
          {({ isActive }) => (
            <>
              {isActive && <SidebarHighlight />}
              <LayoutDashboard size={17} strokeWidth={2} className="shrink-0" />
              {!collapsed && <span className="whitespace-nowrap">Dashboard</span>}
            </>
          )}
        </NavLink>
        <NavLink to="/" end className={linkClass} title={collapsed ? 'Conversations' : undefined}>
          {({ isActive }) => (
            <>
              {isActive && <SidebarHighlight />}
              <MessageSquare size={17} strokeWidth={2} className="shrink-0" />
              {!collapsed && <span className="whitespace-nowrap">Conversations</span>}
            </>
          )}
        </NavLink>
        {user?.es_super_admin && (
          <NavLink to="/configuracion" className={linkClass} title={collapsed ? 'Settings' : undefined}>
            {({ isActive }) => (
              <>
                {isActive && <SidebarHighlight />}
                <Settings size={17} strokeWidth={2} className="shrink-0" />
                {!collapsed && <span className="whitespace-nowrap">Settings</span>}
              </>
            )}
          </NavLink>
        )}
      </nav>

      <div className="mt-auto relative">
        {menuOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
            <div
              className={`absolute bottom-full mb-2 surface p-1.5 z-50 ${
                collapsed ? 'left-0 w-48' : 'left-0 right-0'
              }`}
            >
              <button
                type="button"
                onClick={handleLogout}
                className="w-full flex items-center gap-2 text-sm text-left px-2.5 py-2 rounded-lg text-gray-600 hover:bg-black/[0.04] hover:text-[var(--ink-1)] whitespace-nowrap"
              >
                <LogOut size={15} />
                Sign out
              </button>
            </div>
          </>
        )}
        <button
          type="button"
          onClick={() => setMenuOpen((o) => !o)}
          title={collapsed ? user?.nombre_usuario : undefined}
          className={`w-full flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-black/[0.03] transition-colors ${
            collapsed ? 'justify-center px-0' : ''
          }`}
        >
          <div className="w-8 h-8 rounded-full bg-[var(--wa-green)]/15 text-[var(--wa-green)] flex items-center justify-center text-xs font-semibold shrink-0">
            {initial}
          </div>
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1 text-left leading-tight">
                <div className="text-sm font-medium text-[var(--ink-1)] truncate">{user?.nombre_usuario}</div>
                {user?.cliente_activo && (
                  <div className="text-xs text-gray-400 truncate">{user.cliente_activo.nombre_cliente}</div>
                )}
              </div>
              <ChevronDown size={14} className="text-gray-400 shrink-0" />
            </>
          )}
        </button>
      </div>
    </motion.aside>
  )
}
