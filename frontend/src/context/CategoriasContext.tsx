import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchCategorias, fetchSubcategorias, type Categoria, type Subcategorias } from '../api/client'
import { useAuth } from './AuthContext'

export interface CategoriaMeta {
  id: string
  label: string
  color: string
}

const SIN_SUBCATEGORIAS: Subcategorias = { etiqueta: 'Subcategory', items: [] }

const FALLBACK: CategoriaMeta = { id: 'SIN_ANALIZAR', label: 'Not analyzed', color: '#898781' }

interface CategoriasContextValue {
  categorias: Categoria[]
  subcategorias: Subcategorias
  loading: boolean
  meta: (categoria: string | null) => CategoriaMeta
}

const CategoriasContext = createContext<CategoriasContextValue | null>(null)

// Catálogo de categorías del cliente activo (ver `/api/categorias`) — antes
// era la constante estática `lib/categories.ts`, ahora depende de las
// campañas de cada cliente (cada una con sus propias categorías, o las 5 de
// Acme por defecto). Un solo fetch por cliente activo, compartido por toda
// la app (dashboard, tabla de conversaciones, gráficas, filtro, panel lateral).
export function CategoriasProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const clienteActivoId = user?.cliente_activo?.id_cliente ?? null
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [subcategorias, setSubcategorias] = useState<Subcategorias>(SIN_SUBCATEGORIAS)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (clienteActivoId === null) {
      setCategorias([])
      setSubcategorias(SIN_SUBCATEGORIAS)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    fetchSubcategorias()
      .then((subs) => {
        if (!cancelled) setSubcategorias(subs)
      })
      .catch(() => {
        if (!cancelled) setSubcategorias(SIN_SUBCATEGORIAS)
      })
    fetchCategorias()
      .then((cs) => {
        if (!cancelled) setCategorias(cs)
      })
      .catch(() => {
        if (!cancelled) setCategorias([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [clienteActivoId])

  const meta = (categoria: string | null): CategoriaMeta => {
    const id = categoria ?? 'SIN_ANALIZAR'
    const encontrada = categorias.find((c) => c.id === id)
    if (encontrada) return encontrada
    if (id === 'SIN_ANALIZAR') return FALLBACK
    return { id, label: id, color: '#6b7280' }
  }

  return <CategoriasContext.Provider value={{ categorias, subcategorias, loading, meta }}>{children}</CategoriasContext.Provider>
}

export function useCategorias(): CategoriasContextValue {
  const ctx = useContext(CategoriasContext)
  if (!ctx) throw new Error('useCategorias must be used within <CategoriasProvider>')
  return ctx
}
