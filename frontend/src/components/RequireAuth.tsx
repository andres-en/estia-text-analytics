import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function RequireAuth({
  children,
  permiso,
}: {
  children: React.ReactNode
  /** Si se pasa, además de estar logueado el usuario debe tener este permiso. */
  permiso?: string
}) {
  const { user, loading } = useAuth()

  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  if (permiso && !user.permisos.includes(permiso)) return <Navigate to="/" replace />

  return <>{children}</>
}
