import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import AnimatedTabUnderline from '../../components/AnimatedTabUnderline'
import PageHeader from '../../components/PageHeader'
import {
  AlertTriangle,
  Bot,
  Building2,
  Check,
  Coins,
  Database,
  Info,
  Megaphone,
  Pencil,
  Settings,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
  UserCog,
  UserPlus,
  Users,
  X,
} from 'lucide-react'
import {
  createCliente,
  createClienteCampana,
  createUsuario,
  eliminarConversacionesPorFecha,
  fetchClienteCampanas,
  fetchClientes,
  fetchRoles,
  fetchUsoIA,
  fetchUsuarios,
  generarEsquemaCampana,
  updateCliente,
  updateClienteCampana,
  updateUsuario,
  type CategoriaDef,
  type Campaign,
  type Cliente,
  type EsquemaClasificacion,
  type IndicadorDef,
  type Rol,
  type UsoIA,
  type Usuario,
} from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import StatCard from '../../components/StatCard'

type Tab = 'clientes' | 'campanas' | 'usuarios' | 'uso-ia' | 'mantenimiento'

const TAB_LABEL: Record<Tab, string> = {
  clientes: 'Clients',
  campanas: 'Campaigns',
  usuarios: 'Users',
  'uso-ia': 'AI usage',
  mantenimiento: 'Maintenance',
}

// Réplica en el navegador de `_slugify_db_name` (webapp/admin.py) — solo para
// mostrar una vista previa; el nombre real siempre lo calcula el backend.
function previewDbName(nombreCliente: string): string {
  const slug = nombreCliente
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return slug ? `${slug}_clasificador_chat` : 'clasificador_chat'
}

// Paleta reutilizada del resto de la app (ver lib/categories.ts): verde marca,
// azul y ámbar ya usados en badges/gráficas — así los roles se sienten parte
// del mismo sistema visual en vez de traer colores nuevos.
const ROL_STYLE: Record<string, { badge: string; accent: string; icon: typeof ShieldCheck }> = {
  super_admin: { badge: 'bg-amber-100 text-amber-800', accent: '#eda100', icon: ShieldCheck },
  admin: { badge: 'bg-blue-100 text-blue-800', accent: '#2a78d6', icon: UserCog },
  user: { badge: 'bg-green-100 text-green-800', accent: '#1baf7a', icon: User },
}

const ROL_LABEL: Record<string, string> = {
  super_admin: 'SuperAdmin',
  admin: 'Admin',
  user: 'User',
}

function rolStyle(nombreRol: string) {
  return ROL_STYLE[nombreRol] ?? { badge: 'bg-gray-100 text-gray-700', accent: '#6b7280', icon: User }
}

function rolLabel(nombreRol: string) {
  return ROL_LABEL[nombreRol] ?? nombreRol
}

function formatFecha(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function ConfiguracionPage() {
  const [tab, setTab] = useState<Tab>('clientes')
  const { hasPermiso } = useAuth()
  const puedeEliminarConversaciones = hasPermiso('conversaciones.eliminar')

  const tabs: Tab[] = [
    'clientes',
    'campanas',
    'usuarios',
    'uso-ia',
    ...(puedeEliminarConversaciones ? (['mantenimiento'] as Tab[]) : []),
  ]

  return (
    <div>
      <PageHeader icon={Settings} title="Settings" />
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`relative px-4 py-2 text-sm -mb-px ${
              tab === t ? 'text-[var(--wa-green-dark)] font-semibold' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {TAB_LABEL[t]}
            {tab === t && <AnimatedTabUnderline layoutId="configuracion-tab-underline" />}
          </button>
        ))}
      </div>
      {tab === 'clientes' && <ClientesTab />}
      {tab === 'campanas' && <CampanasTab />}
      {tab === 'usuarios' && <UsuariosTab />}
      {tab === 'uso-ia' && <UsoIATab />}
      {tab === 'mantenimiento' && puedeEliminarConversaciones && <MantenimientoTab />}
    </div>
  )
}

// --- Clientes ----------------------------------------------------------------

function ClientesTab() {
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [nombreNuevo, setNombreNuevo] = useState('')
  const [creando, setCreando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [nombreEditado, setNombreEditado] = useState('')

  const cargar = () => fetchClientes().then(setClientes).catch(() => setClientes([]))

  useEffect(() => {
    cargar()
  }, [])

  const handleCrear = async () => {
    if (!nombreNuevo.trim()) return
    setCreando(true)
    setError(null)
    try {
      await createCliente(nombreNuevo.trim())
      setNombreNuevo('')
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create the client')
    } finally {
      setCreando(false)
    }
  }

  const handleToggleActivo = async (c: Cliente) => {
    await updateCliente(c.id_cliente, { activo: !c.activo })
    cargar()
  }

  const empezarEdicion = (c: Cliente) => {
    setEditandoId(c.id_cliente)
    setNombreEditado(c.nombre_cliente)
    setError(null)
  }

  const guardarNombre = async (id_cliente: number) => {
    if (!nombreEditado.trim()) return
    try {
      await updateCliente(id_cliente, { nombre_cliente: nombreEditado.trim() })
      setEditandoId(null)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not rename the client')
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatCard label="Registered clients" value={clientes.length} icon={Building2} accentColor="#075e54" />
        <div className="bg-[var(--wa-green)]/5 border border-[var(--wa-green)]/20 rounded-lg p-4 flex items-start gap-3">
          <Info size={18} className="text-[var(--wa-green-dark)] shrink-0 mt-0.5" />
          <p className="text-sm text-[var(--wa-green-dark)]">
            Each client gets its own database, provisioned automatically on creation.
          </p>
        </div>
      </div>

      <div className="surface overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
          <Building2 size={16} className="text-[var(--wa-green-dark)]" />
          <h2 className="text-sm font-semibold text-[var(--wa-green-dark)]">New client</h2>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Client name</span>
              <div className="mt-1 relative">
                <Building2 size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={nombreNuevo}
                  onChange={(e) => setNombreNuevo(e.target.value)}
                  placeholder="e.g. Acme Retail"
                  className="w-full text-sm border border-gray-300 rounded-lg pl-8 pr-3 py-2"
                />
              </div>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Database (auto-generated)</span>
              <div className="mt-1 relative">
                <Database size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={nombreNuevo ? previewDbName(nombreNuevo) : ''}
                  disabled
                  placeholder="generated from the name"
                  className="w-full text-sm border border-gray-200 bg-gray-50 text-gray-500 rounded-lg pl-8 pr-3 py-2"
                />
              </div>
            </label>
          </div>
          <button
            onClick={handleCrear}
            disabled={creando || !nombreNuevo.trim()}
            className="btn-primary mt-4 text-sm px-4 py-2"
          >
            {creando ? 'Creating...' : '+ Create client'}
          </button>
          {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        </div>
      </div>

      <div className="surface overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
          <Building2 size={16} className="text-gray-400" />
          <h2 className="text-sm font-semibold text-gray-700">Registered clients ({clientes.length})</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400 uppercase tracking-wide">
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Database</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {clientes.map((c) => (
              <tr key={c.id_cliente} className={!c.activo ? 'opacity-50' : ''}>
                <td className="px-4 py-3">
                  {editandoId === c.id_cliente ? (
                    <div className="flex items-center gap-2">
                      <input
                        value={nombreEditado}
                        onChange={(e) => setNombreEditado(e.target.value)}
                        className="text-sm border border-gray-300 rounded-lg px-2 py-1"
                        autoFocus
                      />
                      <button
                        onClick={() => guardarNombre(c.id_cliente)}
                        className="text-[var(--wa-green-dark)] hover:text-[var(--wa-green)]"
                        title="Save"
                      >
                        <Check size={15} />
                      </button>
                      <button onClick={() => setEditandoId(null)} className="text-gray-400 hover:text-gray-600" title="Cancel">
                        <X size={15} />
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-800">{c.nombre_cliente}</span>
                      <button onClick={() => empezarEdicion(c)} title="Rename" className="text-gray-400 hover:text-[var(--wa-green-dark)]">
                        <Pencil size={13} />
                      </button>
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <code className="text-xs bg-gray-100 text-gray-600 rounded-lg px-1.5 py-0.5">{c.db_name}</code>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`text-xs font-medium rounded-full px-2 py-0.5 ${
                      c.activo ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    {c.activo ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => handleToggleActivo(c)} className="text-xs text-gray-400 hover:text-red-600">
                    {c.activo ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {clientes.length === 0 && <p className="p-4 text-sm text-gray-400">No clients yet.</p>}
      </div>
    </div>
  )
}

// --- Campañas ------------------------------------------------------------------

const TIPO_CONDICION_LABEL: Record<string, string> = {
  regex_bot: 'Bot says',
  regex_customer: 'Customer says',
  boton: 'Exact button',
}

// Edita `configuracion.esquema_clasificacion` (categorías/indicadores/árbol de
// decisión propios de la campaña — ver `analysis/schema.py`) sobre el mismo
// string JSON que ya usa el textarea "avanzado": genera con IA a partir de un
// prompt libre, deja editar categorías/indicadores a mano, y cualquier cambio
// (de acá o del textarea) se refleja en el otro porque comparten la misma
// fuente de verdad (`configJson`).
function EsquemaEditor({
  clienteId,
  configJson,
  onChangeConfigJson,
}: {
  clienteId: number
  configJson: string
  onChangeConfigJson: (json: string) => void
}) {
  const [prompt, setPrompt] = useState('')
  const [generando, setGenerando] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)

  let config: Record<string, unknown> = {}
  let jsonInvalido = false
  try {
    config = configJson.trim() ? JSON.parse(configJson) : {}
  } catch {
    jsonInvalido = true
  }
  const esquema = (config.esquema_clasificacion as EsquemaClasificacion | null | undefined) ?? null

  const setEsquema = (siguiente: EsquemaClasificacion) => {
    onChangeConfigJson(JSON.stringify({ ...config, esquema_clasificacion: siguiente }, null, 2))
  }

  const quitarEsquema = () => {
    const { esquema_clasificacion: _esquema, ...resto } = config
    onChangeConfigJson(Object.keys(resto).length ? JSON.stringify(resto, null, 2) : '')
  }

  const handleGenerar = async () => {
    if (!prompt.trim()) return
    setGenerando(true)
    setGenError(null)
    try {
      const { esquema_clasificacion } = await generarEsquemaCampana(clienteId, prompt.trim())
      setEsquema(esquema_clasificacion)
      setPrompt('')
    } catch (e) {
      setGenError(e instanceof Error ? e.message : 'Could not generate the schema')
    } finally {
      setGenerando(false)
    }
  }

  const actualizarCategoria = (idx: number, cambios: Partial<CategoriaDef>) => {
    if (!esquema) return
    setEsquema({ ...esquema, categorias: esquema.categorias.map((c, i) => (i === idx ? { ...c, ...cambios } : c)) })
  }

  const actualizarIndicador = (idx: number, cambios: Partial<IndicadorDef>) => {
    if (!esquema) return
    setEsquema({ ...esquema, indicadores: esquema.indicadores.map((ind, i) => (i === idx ? { ...ind, ...cambios } : ind)) })
  }

  const actualizarPatron = (idxIndicador: number, idxCondicion: number, patron: string) => {
    if (!esquema) return
    const indicadores = esquema.indicadores.map((ind, i) => {
      if (i !== idxIndicador) return ind
      return { ...ind, condiciones: ind.condiciones.map((c, j) => (j === idxCondicion ? { ...c, patron } : c)) }
    })
    setEsquema({ ...esquema, indicadores })
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2 items-start">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder='Describe in your own words how you want to classify, e.g. "I sell online courses. I want to know who enrolled, who only asked about the price and who showed no interest."'
          rows={2}
          className="flex-1 text-sm border border-gray-300 rounded-lg px-2.5 py-1.5"
        />
        <button
          type="button"
          onClick={handleGenerar}
          disabled={generando || !prompt.trim()}
          className="btn-primary text-xs px-3 py-2 shrink-0 inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          <Sparkles size={13} />
          {generando ? 'Generating...' : esquema ? 'Regenerate with AI' : 'Generate with AI'}
        </button>
      </div>
      {genError && <p className="text-xs text-red-600">{genError}</p>}
      {jsonInvalido && (
        <p className="text-xs text-red-600">The advanced JSON below has a syntax error — fix it to edit here.</p>
      )}

      {esquema && (
        <div className="border border-gray-200 rounded-lg p-3 space-y-3 bg-gray-50/70">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Categories</h4>
            <button type="button" onClick={quitarEsquema} className="text-xs text-gray-400 hover:text-red-600">
              Remove schema (use the default categories)
            </button>
          </div>
          <div className="space-y-1.5">
            {esquema.categorias.map((c, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <input
                  type="color"
                  value={c.color}
                  onChange={(e) => actualizarCategoria(idx, { color: e.target.value })}
                  className="w-7 h-7 rounded border border-gray-300 shrink-0 cursor-pointer"
                  title="Color"
                />
                <input
                  value={c.label}
                  onChange={(e) => actualizarCategoria(idx, { label: e.target.value })}
                  className="flex-1 text-sm border border-gray-300 rounded-lg px-2 py-1"
                />
                <code className="text-[10px] text-gray-400 shrink-0">{c.id}</code>
                {c.id === esquema.categoria_sin_respuesta && (
                  <span className="text-[10px] text-gray-400 shrink-0">(no response)</span>
                )}
              </div>
            ))}
          </div>

          <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wide pt-1">Indicators</h4>
          <div className="space-y-2">
            {esquema.indicadores.map((ind, idx) => (
              <div key={idx} className="border border-gray-200 rounded-lg p-2 bg-white space-y-1.5">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-[10px] font-medium rounded-full px-2 py-0.5 shrink-0 ${
                      ind.tipo === 'ia' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'
                    }`}
                  >
                    {ind.tipo === 'ia' ? 'AI criterion' : 'Rule'}
                  </span>
                  <input
                    value={ind.label}
                    onChange={(e) => actualizarIndicador(idx, { label: e.target.value })}
                    className="flex-1 text-sm border border-gray-300 rounded-lg px-2 py-1"
                  />
                </div>
                {ind.tipo === 'ia' ? (
                  <textarea
                    value={ind.descripcion_ia ?? ''}
                    onChange={(e) => actualizarIndicador(idx, { descripcion_ia: e.target.value })}
                    rows={2}
                    placeholder="Criterion the AI must evaluate"
                    className="w-full text-xs border border-gray-300 rounded-lg px-2 py-1"
                  />
                ) : (
                  <div className="space-y-1">
                    {ind.condiciones.map((cond, j) => (
                      <div key={j} className="flex items-center gap-1.5">
                        <span className="text-[10px] text-gray-400 w-24 shrink-0">
                          {TIPO_CONDICION_LABEL[cond.tipo] ?? cond.tipo}
                        </span>
                        <input
                          value={cond.patron}
                          onChange={(e) => actualizarPatron(idx, j, e.target.value)}
                          className="flex-1 text-xs font-mono border border-gray-300 rounded-lg px-2 py-1"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wide pt-1">Decision tree</h4>
          <ol className="text-xs text-gray-500 space-y-0.5 list-decimal list-inside">
            {esquema.arbol_decision.map((r, i) => (
              <li key={i}>
                {Object.keys(r.condicion).length === 0
                  ? 'in any other case'
                  : Object.entries(r.condicion)
                      .map(([k, v]) => `${k}=${v ? 'yes' : 'no'}`)
                      .join(' and ')}
                {' → '}
                <strong>{esquema.categorias.find((c) => c.id === r.categoria)?.label ?? r.categoria}</strong>
              </li>
            ))}
          </ol>
          <p className="text-[10px] text-gray-400">
            To reorder rows or change the tree logic, edit the advanced JSON below.
          </p>
        </div>
      )}
    </div>
  )
}

function CampanasTab() {
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [clienteId, setClienteId] = useState<number | ''>('')
  const [campanas, setCampanas] = useState<Campaign[]>([])
  const [nombreNuevo, setNombreNuevo] = useState('')
  const [configNueva, setConfigNueva] = useState('')
  const [mostrarConfigNueva, setMostrarConfigNueva] = useState(false)
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [configEditada, setConfigEditada] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchClientes().then((cs) => {
      setClientes(cs)
      if (cs.length > 0) setClienteId(cs[0].id_cliente)
    })
  }, [])

  const cargarCampanas = (id: number) => fetchClienteCampanas(id).then(setCampanas).catch(() => setCampanas([]))

  useEffect(() => {
    if (clienteId !== '') cargarCampanas(clienteId)
  }, [clienteId])

  const parseConfig = (texto: string): object | undefined => {
    if (!texto.trim()) return undefined
    return JSON.parse(texto)
  }

  const handleCrear = async () => {
    if (!nombreNuevo.trim() || clienteId === '') return
    setError(null)
    try {
      const configuracion = parseConfig(configNueva)
      await createClienteCampana(clienteId, nombreNuevo.trim(), configuracion)
      setNombreNuevo('')
      setConfigNueva('')
      setMostrarConfigNueva(false)
      cargarCampanas(clienteId)
    } catch (e) {
      setError(
        e instanceof SyntaxError ? 'The configuration JSON is not valid.' : e instanceof Error ? e.message : 'Could not create the campaign',
      )
    }
  }

  const empezarEdicion = (camp: Campaign) => {
    setEditandoId(camp.id_campana)
    setConfigEditada(JSON.stringify(camp.configuracion, null, 2))
    setError(null)
  }

  const guardarEdicion = async (id_campana: number) => {
    if (clienteId === '') return
    setError(null)
    try {
      const configuracion = JSON.parse(configEditada)
      await updateClienteCampana(clienteId, id_campana, { configuracion })
      setEditandoId(null)
      cargarCampanas(clienteId)
    } catch (e) {
      setError(
        e instanceof SyntaxError ? 'The configuration JSON is not valid.' : e instanceof Error ? e.message : 'Could not update the campaign',
      )
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatCard label="Campaigns for this client" value={campanas.length} icon={Megaphone} accentColor="#2a78d6" />
        <div className="surface p-4 flex items-center gap-3">
          <Building2 size={16} className="text-gray-400 shrink-0" />
          <select
            value={clienteId}
            onChange={(e) => setClienteId(e.target.value ? Number(e.target.value) : '')}
            className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 flex-1"
          >
            <option value="" disabled>
              Select a client...
            </option>
            {clientes.map((c) => (
              <option key={c.id_cliente} value={c.id_cliente}>
                {c.nombre_cliente}
              </option>
            ))}
          </select>
        </div>
      </div>

      {clientes.length === 0 ? (
        <p className="text-sm text-gray-400 surface p-4">
          No clients yet — create one in the "Clients" tab first.
        </p>
      ) : (
        <>
          <div className="surface p-4">
            <div className="flex items-center gap-2 mb-3">
              <Megaphone size={16} className="text-[var(--wa-green-dark)]" />
              <h2 className="text-sm font-semibold text-[var(--wa-green-dark)]">New campaign</h2>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={nombreNuevo}
                onChange={(e) => setNombreNuevo(e.target.value)}
                placeholder="e.g. Credit_Card_Refinancing"
                className="text-sm border border-gray-300 rounded-lg px-3 py-2 flex-1 min-w-[200px]"
              />
              <button
                onClick={handleCrear}
                disabled={!nombreNuevo.trim()}
                className="btn-primary text-sm px-4 py-2"
              >
                + Create campaign
              </button>
            </div>

            <div className="mt-3">
              <EsquemaEditor clienteId={clienteId || 0} configJson={configNueva} onChangeConfigJson={setConfigNueva} />
            </div>

            <button
              onClick={() => setMostrarConfigNueva(!mostrarConfigNueva)}
              className="text-xs text-gray-400 hover:text-gray-600 mt-2"
            >
              {mostrarConfigNueva ? 'Hide advanced JSON' : 'Advanced JSON (full manual editing)'}
            </button>
            {mostrarConfigNueva && (
              <textarea
                value={configNueva}
                onChange={(e) => setConfigNueva(e.target.value)}
                placeholder="Optional JSON — empty = use the defaults (buttons/regex of the credit-line sales bot)"
                rows={6}
                className="text-xs font-mono border border-gray-300 rounded-lg px-2 py-1.5 w-full mt-2"
              />
            )}
            {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
          </div>

          <div className="surface overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
              <Megaphone size={16} className="text-gray-400" />
              <h2 className="text-sm font-semibold text-gray-700">Registered campaigns ({campanas.length})</h2>
            </div>
            <div className="divide-y divide-gray-100">
              {campanas.map((camp) => (
                <div key={camp.id_campana} className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium text-gray-800 text-sm">{camp.nombre_campana}</span>
                      <span className="text-xs text-gray-400 ml-2">({camp.estado})</span>
                    </div>
                    <button
                      onClick={() => (editandoId === camp.id_campana ? setEditandoId(null) : empezarEdicion(camp))}
                      className="text-xs text-[var(--wa-green-dark)] hover:underline"
                    >
                      {editandoId === camp.id_campana ? 'Cancel' : 'Edit configuration'}
                    </button>
                  </div>
                  {editandoId === camp.id_campana && (
                    <div className="mt-2 space-y-2">
                      <EsquemaEditor clienteId={clienteId || 0} configJson={configEditada} onChangeConfigJson={setConfigEditada} />
                      <details>
                        <summary className="text-xs text-gray-400 hover:text-gray-600 cursor-pointer">
                          Advanced JSON (full manual editing)
                        </summary>
                        <textarea
                          value={configEditada}
                          onChange={(e) => setConfigEditada(e.target.value)}
                          rows={10}
                          className="text-xs font-mono border border-gray-300 rounded-lg px-2 py-1.5 w-full mt-2"
                        />
                      </details>
                      <button
                        onClick={() => guardarEdicion(camp.id_campana)}
                        className="btn-primary text-xs px-3 py-1.5"
                      >
                        Save
                      </button>
                      {error && <p className="text-sm text-red-600">{error}</p>}
                    </div>
                  )}
                </div>
              ))}
              {campanas.length === 0 && <p className="p-4 text-sm text-gray-400">No campaigns yet.</p>}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// --- Uso de IA -----------------------------------------------------------------

const TIPO_USO_LABEL: Record<string, string> = {
  clasificacion: 'Conversation classification',
  generar_esquema: 'AI schema generation',
}

function UsoIATab() {
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [clienteId, setClienteId] = useState<number | ''>('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [uso, setUso] = useState<UsoIA | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchClientes().then((cs) => {
      setClientes(cs)
      if (cs.length > 0) setClienteId(cs[0].id_cliente)
    })
  }, [])

  useEffect(() => {
    if (clienteId === '') return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchUsoIA(clienteId, { desde: desde || undefined, hasta: hasta || undefined })
      .then((res) => {
        if (!cancelled) setUso(res)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load AI usage')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [clienteId, desde, hasta])

  // Un total por mes (sumando todos los modelos) — la tabla de abajo ya
  // desglosa por modelo, esto es para ver la tendencia de gasto en el tiempo.
  const gastoPorMes = useMemo(() => {
    if (!uso) return []
    const acumulado = new Map<string, { mes: string; costo: number; tokens: number; incompleto: boolean }>()
    for (const f of uso.por_mes) {
      const entrada = acumulado.get(f.mes) ?? { mes: f.mes, costo: 0, tokens: 0, incompleto: false }
      entrada.tokens += f.tokens_prompt + f.tokens_completion
      if (f.costo_usd != null) entrada.costo += f.costo_usd
      else entrada.incompleto = true
      acumulado.set(f.mes, entrada)
    }
    return Array.from(acumulado.values()).sort((a, b) => a.mes.localeCompare(b.mes))
  }, [uso])
  const algunMesIncompleto = gastoPorMes.some((m) => m.incompleto)

  return (
    <div className="space-y-4">
      {clientes.length === 0 ? (
        <p className="text-sm text-gray-400 surface p-4">
          No clients yet — create one in the "Clients" tab first.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <StatCard label="Tokens used" value={uso?.tokens_totales ?? 0} icon={Bot} accentColor="#2a78d6" />
            <div className="surface p-4 flex items-center gap-3">
              <div className="w-11 h-11 rounded-full flex items-center justify-center bg-[#1baf7a]/10 text-[#1baf7a] shrink-0">
                <Coins size={20} />
              </div>
              <div>
                <div className="text-2xl font-semibold text-gray-800 tabular-nums">
                  {uso?.costo_total_usd != null ? `$${uso.costo_total_usd.toFixed(2)}` : '—'}
                </div>
                <div className="text-xs text-gray-400">
                  Estimated cost (USD){uso && uso.costo_total_usd == null && uso.filas.length > 0 ? ' — no known price for some model' : ''}
                </div>
              </div>
            </div>
          </div>

          <div className="surface p-4 flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-500">Client</span>
              <select
                value={clienteId}
                onChange={(e) => setClienteId(e.target.value ? Number(e.target.value) : '')}
                className="text-sm border border-gray-300 rounded-lg px-2 py-1.5"
              >
                {clientes.map((c) => (
                  <option key={c.id_cliente} value={c.id_cliente}>
                    {c.nombre_cliente}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-500">From</span>
              <input
                type="date"
                value={desde}
                onChange={(e) => setDesde(e.target.value)}
                className="text-sm border border-gray-300 rounded-lg px-2 py-1.5"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-500">To</span>
              <input
                type="date"
                value={hasta}
                onChange={(e) => setHasta(e.target.value)}
                className="text-sm border border-gray-300 rounded-lg px-2 py-1.5"
              />
            </label>
            {loading && <span className="text-xs text-gray-400">Loading...</span>}
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="surface p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Spend per month</h2>
            {gastoPorMes.length === 0 ? (
              <p className="text-sm text-gray-400 py-8 text-center">No AI usage recorded in this range.</p>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={gastoPorMes}>
                    <CartesianGrid vertical={false} stroke="#e1e0d9" />
                    <XAxis dataKey="mes" tick={{ fontSize: 12, fill: '#898781' }} />
                    <YAxis
                      tick={{ fontSize: 12, fill: '#898781' }}
                      tickFormatter={(v: number) => `$${v.toFixed(2)}`}
                    />
                    <Tooltip
                      formatter={(valor: unknown, _nombre: unknown, item: { payload?: { incompleto?: boolean } }) => [
                        `$${Number(valor).toFixed(4)}${item.payload?.incompleto ? ' (parcial)' : ''}`,
                        'Estimated cost',
                      ]}
                    />
                    <Bar dataKey="costo" fill="#1baf7a" radius={[4, 4, 0, 0]} barSize={28} />
                  </BarChart>
                </ResponsiveContainer>
                {algunMesIncompleto && (
                  <p className="text-xs text-gray-400 mt-1">
                    Months marked as "partial" include a model with no known price — their real cost is
                    higher than shown.
                  </p>
                )}
              </>
            )}
          </div>

          <div className="surface overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-700">Breakdown by model</h2>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 uppercase tracking-wide">
                  <th className="px-4 py-2 font-medium">Model</th>
                  <th className="px-4 py-2 font-medium">Usage</th>
                  <th className="px-4 py-2 font-medium text-right">Calls</th>
                  <th className="px-4 py-2 font-medium text-right">Input tokens</th>
                  <th className="px-4 py-2 font-medium text-right">Output tokens</th>
                  <th className="px-4 py-2 font-medium text-right">Estimated cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(uso?.filas ?? []).map((f, i) => (
                  <tr key={i}>
                    <td className="px-4 py-3">
                      <code className="text-xs bg-gray-100 text-gray-600 rounded-lg px-1.5 py-0.5">{f.modelo}</code>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{TIPO_USO_LABEL[f.tipo] ?? f.tipo}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{f.llamadas.toLocaleString('en-US')}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{f.tokens_prompt.toLocaleString('en-US')}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{f.tokens_completion.toLocaleString('en-US')}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {f.costo_usd != null ? `$${f.costo_usd.toFixed(4)}` : 'no disponible'}
                    </td>
                  </tr>
                ))}
                {uso && uso.filas.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center text-gray-400 py-8">
                      No AI usage recorded for this client yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-400">
            Prices are for reference only (see <code className="font-mono">analysis/pricing.py</code> in the
            backend) — check them against OpenAI's official pricing page if you need the exact figure.
          </p>
        </>
      )}
    </div>
  )
}

// --- Mantenimiento (borrado de conversaciones por fecha) ---------------------

function MantenimientoTab() {
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [clienteId, setClienteId] = useState<number | ''>('')
  const [fecha, setFecha] = useState('')
  const [pidiendoConfirmacion, setPidiendoConfirmacion] = useState(false)
  const [eliminando, setEliminando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resultado, setResultado] = useState<{ fecha: string; conversaciones: number; mensajes: number } | null>(null)

  useEffect(() => {
    fetchClientes().then((cs) => {
      setClientes(cs)
      if (cs.length > 0) setClienteId(cs[0].id_cliente)
    })
  }, [])

  const clienteSeleccionado = clientes.find((c) => c.id_cliente === clienteId)

  const handleConfirmar = async () => {
    if (clienteId === '' || !fecha) return
    setEliminando(true)
    setError(null)
    try {
      const res = await eliminarConversacionesPorFecha(clienteId, fecha)
      setResultado({ fecha, conversaciones: res.conversaciones_eliminadas, mensajes: res.mensajes_eliminados })
      setPidiendoConfirmacion(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete the conversations')
    } finally {
      setEliminando(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
        <AlertTriangle size={18} className="text-red-600 shrink-0 mt-0.5" />
        <p className="text-sm text-red-800">
          This permanently deletes the conversations, their messages and their analysis for the date and client you
          pick — it cannot be undone. Meant for discarding an upload with bad data so the file can be uploaded
          again. AI usage already recorded is kept.
        </p>
      </div>

      {clientes.length === 0 ? (
        <p className="text-sm text-gray-400 surface p-4">
          No clients yet — create one in the "Clients" tab first.
        </p>
      ) : (
        <div className="surface p-4">
          <div className="flex items-center gap-2 mb-3">
            <Trash2 size={16} className="text-red-600" />
            <h2 className="text-sm font-semibold text-gray-800">Delete messages by date</h2>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-500">Client</span>
              <select
                value={clienteId}
                onChange={(e) => {
                  setClienteId(e.target.value ? Number(e.target.value) : '')
                  setPidiendoConfirmacion(false)
                  setResultado(null)
                }}
                className="text-sm border border-gray-300 rounded-lg px-2 py-1.5"
              >
                {clientes.map((c) => (
                  <option key={c.id_cliente} value={c.id_cliente}>
                    {c.nombre_cliente}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-500">Date</span>
              <input
                type="date"
                value={fecha}
                onChange={(e) => {
                  setFecha(e.target.value)
                  setPidiendoConfirmacion(false)
                  setResultado(null)
                }}
                className="text-sm border border-gray-300 rounded-lg px-2 py-1.5"
              />
            </label>
            {!pidiendoConfirmacion && (
              <button
                onClick={() => {
                  setResultado(null)
                  setError(null)
                  setPidiendoConfirmacion(true)
                }}
                disabled={clienteId === '' || !fecha}
                className="text-sm px-4 py-2 rounded-full font-semibold text-red-700 border border-red-300 bg-red-50 hover:bg-red-100 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
              >
                <Trash2 size={14} />
                Delete messages for this date
              </button>
            )}
          </div>

          {pidiendoConfirmacion && clienteSeleccionado && (
            <div className="mt-3 border border-red-300 bg-red-50 rounded-lg p-3">
              <p className="text-sm text-red-800">
                Are you sure you want to delete every conversation and message of{' '}
                <strong>{clienteSeleccionado.nombre_cliente}</strong> from{' '}
                <strong>{new Date(`${fecha}T00:00:00`).toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' })}</strong>?
                This action cannot be undone.
              </p>
              <div className="flex items-center gap-2 mt-3">
                <button
                  onClick={handleConfirmar}
                  disabled={eliminando}
                  className="text-sm px-4 py-1.5 rounded-full font-semibold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50"
                >
                  {eliminando ? 'Deleting...' : 'Yes, delete'}
                </button>
                <button
                  onClick={() => setPidiendoConfirmacion(false)}
                  disabled={eliminando}
                  className="text-sm px-4 py-1.5 rounded-full font-medium text-gray-600 border border-gray-300 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {error && <p className="text-sm text-red-600 mt-3">{error}</p>}

          {resultado && (
            <div className="mt-3 border border-green-200 bg-green-50 rounded-lg p-3 flex items-start gap-2.5">
              <Check size={16} className="text-green-700 shrink-0 mt-0.5" />
              <p className="text-sm text-green-800">
                Deleted <strong>{resultado.conversaciones}</strong> conversation(s) and{' '}
                <strong>{resultado.mensajes}</strong> message(s) from{' '}
                {new Date(`${resultado.fecha}T00:00:00`).toLocaleDateString('en-US', {
                  day: 'numeric',
                  month: 'long',
                  year: 'numeric',
                })}
                . You can now upload the file for that date again.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// --- Usuarios ------------------------------------------------------------------

interface EditForm {
  nombre_usuario: string
  id_rol: string
  id_clientes: number[]
}

function ClienteCheckboxList({
  clientes,
  selected,
  onChange,
}: {
  clientes: Cliente[]
  selected: number[]
  onChange: (ids: number[]) => void
}) {
  const toggle = (id: number) => {
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  }
  return (
    <div className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm max-h-28 overflow-y-auto min-w-[170px] bg-white">
      {clientes.length === 0 && <span className="text-gray-400 text-xs">No clients created</span>}
      {clientes.map((c) => (
        <label key={c.id_cliente} className="flex items-center gap-1.5 py-0.5 cursor-pointer">
          <input
            type="checkbox"
            checked={selected.includes(c.id_cliente)}
            onChange={() => toggle(c.id_cliente)}
          />
          <span className="truncate">{c.nombre_cliente}</span>
        </label>
      ))}
    </div>
  )
}

function UsuariosTab() {
  const { user: currentUser } = useAuth()
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [roles, setRoles] = useState<Rol[]>([])
  const [form, setForm] = useState<{ nombre_usuario: string; email: string; id_rol: string; id_clientes: number[] }>({
    nombre_usuario: '',
    email: '',
    id_rol: '',
    id_clientes: [],
  })
  const [creando, setCreando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<EditForm>({ nombre_usuario: '', id_rol: '', id_clientes: [] })
  const [guardando, setGuardando] = useState(false)

  const cargar = () => fetchUsuarios().then(setUsuarios).catch(() => setUsuarios([]))

  useEffect(() => {
    cargar()
    fetchClientes().then(setClientes).catch(() => setClientes([]))
    fetchRoles().then(setRoles).catch(() => setRoles([]))
  }, [])

  const handleCrear = async () => {
    if (!form.nombre_usuario.trim() || !form.email.trim() || !form.id_rol) return
    setCreando(true)
    setError(null)
    try {
      await createUsuario({
        nombre_usuario: form.nombre_usuario.trim(),
        email: form.email.trim(),
        id_rol: Number(form.id_rol),
        id_clientes: form.id_clientes,
      })
      setForm({ nombre_usuario: '', email: '', id_rol: '', id_clientes: [] })
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create the user')
    } finally {
      setCreando(false)
    }
  }

  const handleToggleActivo = async (u: Usuario) => {
    await updateUsuario(u.id_usuario, { activo: !u.activo })
    cargar()
  }

  const empezarEdicion = (u: Usuario) => {
    setEditandoId(u.id_usuario)
    setEditForm({
      nombre_usuario: u.nombre_usuario,
      id_rol: String(u.rol.id_rol),
      id_clientes: u.clientes.map((c) => c.id_cliente),
    })
  }

  const guardarEdicion = async (id_usuario: number) => {
    setGuardando(true)
    try {
      await updateUsuario(id_usuario, {
        nombre_usuario: editForm.nombre_usuario.trim(),
        id_rol: Number(editForm.id_rol),
        id_clientes: editForm.id_clientes,
      })
      setEditandoId(null)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update the user')
    } finally {
      setGuardando(false)
    }
  }

  const total = usuarios.length
  const porRol = (nombreRol: string) => usuarios.filter((u) => u.rol.nombre_rol === nombreRol).length

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total" value={total} icon={Users} accentColor="#075e54" />
        <StatCard label="SuperAdmin" value={porRol('super_admin')} icon={ShieldCheck} accentColor={ROL_STYLE.super_admin.accent} />
        <StatCard label="Admin" value={porRol('admin')} icon={UserCog} accentColor={ROL_STYLE.admin.accent} />
        <StatCard label="User" value={porRol('user')} icon={User} accentColor={ROL_STYLE.user.accent} />
      </div>

      <div className="surface p-4">
        <div className="flex items-center gap-2 mb-3">
          <UserPlus size={16} className="text-[var(--wa-green-dark)]" />
          <h2 className="text-sm font-semibold text-[var(--wa-green-dark)]">Add user</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={form.nombre_usuario}
            onChange={(e) => setForm({ ...form, nombre_usuario: e.target.value })}
            placeholder="Name"
            className="text-sm border border-gray-300 rounded-lg px-2 py-1.5"
          />
          <input
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="correo@example.com"
            className="text-sm border border-gray-300 rounded-lg px-2 py-1.5"
          />
          <select
            value={form.id_rol}
            onChange={(e) => setForm({ ...form, id_rol: e.target.value })}
            className="text-sm border border-gray-300 rounded-lg px-2 py-1.5"
          >
            <option value="">Role...</option>
            {roles.map((r) => (
              <option key={r.id_rol} value={r.id_rol}>
                {rolLabel(r.nombre_rol)}
              </option>
            ))}
          </select>
          <ClienteCheckboxList
            clientes={clientes}
            selected={form.id_clientes}
            onChange={(ids) => setForm({ ...form, id_clientes: ids })}
          />
          <button
            onClick={handleCrear}
            disabled={creando}
            className="btn-primary text-sm px-4 py-1.5"
          >
            {creando ? 'Creating...' : 'Add'}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2">No client selected = super admin (sees all).</p>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </div>

      <div className="surface overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
          <ShieldCheck size={16} className="text-gray-400" />
          <h2 className="text-sm font-semibold text-gray-700">Usuarios registrados ({total})</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400 uppercase tracking-wide">
              <th className="px-4 py-2 font-medium">User</th>
              <th className="px-4 py-2 font-medium">Role</th>
              <th className="px-4 py-2 font-medium">Client</th>
              <th className="px-4 py-2 font-medium">Registered on</th>
              <th className="px-4 py-2 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {usuarios.map((u) => {
              const esUno = u.id_usuario === currentUser?.id_usuario
              const style = rolStyle(u.rol.nombre_rol)
              const editando = editandoId === u.id_usuario

              return (
                <tr key={u.id_usuario} className={!u.activo ? 'opacity-50' : ''}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
                        style={{ backgroundColor: `${style.accent}1a`, color: style.accent }}
                      >
                        {u.nombre_usuario.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        {editando ? (
                          <input
                            value={editForm.nombre_usuario}
                            onChange={(e) => setEditForm({ ...editForm, nombre_usuario: e.target.value })}
                            className="text-sm border border-gray-300 rounded-lg px-2 py-1 w-full"
                          />
                        ) : (
                          <div className="font-medium text-gray-800 truncate">{u.nombre_usuario}</div>
                        )}
                        <div className="text-xs text-gray-400 truncate">
                          {u.email} {esUno && <span className="text-[var(--wa-green-dark)] font-medium">· You</span>}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {editando ? (
                      <select
                        value={editForm.id_rol}
                        onChange={(e) => setEditForm({ ...editForm, id_rol: e.target.value })}
                        className="text-sm border border-gray-300 rounded-lg px-2 py-1"
                      >
                        {roles.map((r) => (
                          <option key={r.id_rol} value={r.id_rol}>
                            {rolLabel(r.nombre_rol)}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${style.badge}`}>
                        {rolLabel(u.rol.nombre_rol)}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {editando ? (
                      <ClienteCheckboxList
                        clientes={clientes}
                        selected={editForm.id_clientes}
                        onChange={(ids) => setEditForm({ ...editForm, id_clientes: ids })}
                      />
                    ) : u.clientes.length > 0 ? (
                      u.clientes.map((c) => c.nombre_cliente).join(', ')
                    ) : (
                      <span className="text-gray-400">no client</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatFecha(u.fecha_creacion)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-3">
                      {esUno ? (
                        <span className="text-gray-300">—</span>
                      ) : editando ? (
                        <>
                          <button
                            onClick={() => guardarEdicion(u.id_usuario)}
                            disabled={guardando}
                            title="Save"
                            className="text-[var(--wa-green-dark)] hover:text-[var(--wa-green)] disabled:opacity-50"
                          >
                            <Check size={16} />
                          </button>
                          <button
                            onClick={() => setEditandoId(null)}
                            title="Cancel"
                            className="text-gray-400 hover:text-gray-600"
                          >
                            <X size={16} />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => empezarEdicion(u)}
                            title="Edit"
                            className="text-gray-400 hover:text-[var(--wa-green-dark)]"
                          >
                            <Pencil size={15} />
                          </button>
                          <button
                            onClick={() => handleToggleActivo(u)}
                            title={u.activo ? 'Deactivate' : 'Activate'}
                            className="text-xs text-gray-400 hover:text-red-600"
                          >
                            {u.activo ? 'Deactivate' : 'Activate'}
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {usuarios.length === 0 && <p className="p-4 text-sm text-gray-400">No users yet.</p>}
      </div>
    </div>
  )
}
