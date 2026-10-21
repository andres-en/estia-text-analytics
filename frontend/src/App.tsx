import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import Sidebar from './components/Sidebar'
import RequireAuth from './components/RequireAuth'
import { AuthProvider } from './context/AuthContext'
import { CategoriasProvider } from './context/CategoriasContext'
import LoginPage from './pages/LoginPage'
import ConversationsPage from './pages/ConversationsPage'
import DashboardPage from './pages/DashboardPage'
import ConversationDetailPage from './pages/ConversationDetailPage'
import ConfiguracionPage from './pages/admin/ConfiguracionPage'
import { fadeIn, springSettle } from './lib/motionPresets'

function AppRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        initial={fadeIn.initial}
        animate={fadeIn.animate}
        exit={fadeIn.exit}
        transition={springSettle}
        className="h-full"
      >
        <Routes location={location}>
          <Route path="/" element={<ConversationsPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/conversations/:sessionId" element={<ConversationDetailPage />} />
          <Route
            path="/configuracion"
            element={
              <RequireAuth permiso="administracion.acceso">
                <ConfiguracionPage />
              </RequireAuth>
            }
          />
        </Routes>
      </motion.div>
    </AnimatePresence>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <CategoriasProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/*"
              element={
                <RequireAuth>
                  {/* Cada página decide su propio scroll: Dashboard y Configuración
                      desplazan todo el <main>; Conversaciones llena la ventana y
                      desplaza solo la tabla y el panel. */}
                  <div className="flex h-screen overflow-hidden bg-bg text-ink">
                    <Sidebar />
                    <main className="flex-1 min-w-0 overflow-y-auto">
                      <AppRoutes />
                    </main>
                  </div>
                </RequireAuth>
              }
            />
          </Routes>
        </CategoriasProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
