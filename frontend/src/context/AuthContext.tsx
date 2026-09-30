import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { ApiError, fetchMe, logout as apiLogout, setClienteActivo, type CurrentUser } from '../api/client'

interface AuthContextValue {
  user: CurrentUser | null
  loading: boolean
  hasPermiso: (permiso: string) => boolean
  refresh: () => Promise<void>
  logout: () => Promise<void>
  cambiarClienteActivo: (clienteId: number | null) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const me = await fetchMe()
      setUser(me)
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setUser(null)
      } else {
        throw e
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const logout = useCallback(async () => {
    await apiLogout()
    setUser(null)
  }, [])

  const cambiarClienteActivo = useCallback(
    async (clienteId: number | null) => {
      await setClienteActivo(clienteId)
      await refresh()
    },
    [refresh],
  )

  const hasPermiso = useCallback((permiso: string) => Boolean(user?.permisos.includes(permiso)), [user])

  return (
    <AuthContext.Provider value={{ user, loading, hasPermiso, refresh, logout, cambiarClienteActivo }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
