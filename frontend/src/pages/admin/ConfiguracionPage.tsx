import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Bot,
  Building2,
  Check,
  ChevronDown,
  Database,
  Info,
  Megaphone,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Trash2,
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
import PageHeader from '../../components/PageHeader'
import SegmentedControl from '../../components/SegmentedControl'
import DateRangeField from '../../components/DateRangeField'
import Badge from '../../components/Badge'
import ClientTile from '../../components/ClientTile'
import Modal from '../../components/Modal'
import { formatLongDate, formatMediumDate, formatNumber, initials, MESES_CORTOS, parseLocalDate } from '../../lib/format'
import { rolLabel, rolTone } from '../../lib/roles'

type Tab = 'clientes' | 'campanas' | 'usuarios' | 'uso-ia' | 'mantenimiento'

const TAB_LABEL: Record<Tab, string> = {
  clientes: 'Clientes',
  campanas: 'Campañas',
  usuarios: 'Usuarios',
  'uso-ia': 'Uso de IA',
  mantenimiento: 'Mantenimiento',
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

function errorMsg(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback
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
    <div className="flex flex-col gap-5 px-7 pt-6 pb-10 box-border max-w-[1400px]">
      <PageHeader title="Configuración" subtitle="Administra clientes, campañas, usuarios y el consumo de IA." />
      <SegmentedControl
        size="lg"
        options={tabs.map((t) => ({ value: t, label: TAB_LABEL[t] }))}
        value={tab}
        onChange={setTab}
        className="max-w-full"
        style={{ width: tabs.length * 136 }}
      />
      <div key={tab} className="animate-estia-fade">
        {tab === 'clientes' && <ClientesTab />}
        {tab === 'campanas' && <CampanasTab />}
        {tab === 'usuarios' && <UsuariosTab />}
        {tab === 'uso-ia' && <UsoIATab />}
        {tab === 'mantenimiento' && puedeEliminarConversaciones && <MantenimientoTab />}
      </div>
    </div>
  )
}

// --- Piezas compartidas ------------------------------------------------------

function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={`surface ${className ?? 'p-5 flex flex-col gap-4'}`}>{children}</section>
}

function CardTitle({ title, subtitle, children }: { title: ReactNode; subtitle?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 flex-wrap">
      <div>
        <h2 className="m-0 text-[15px] font-bold text-ink">{title}</h2>
        {subtitle && <div className="text-[12.5px] text-ink-3 mt-[3px]">{subtitle}</div>}
      </div>
      {children}
    </div>
  )
}

function TableHeader({ title, count, children }: { title: string; count: number; children?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-line-soft flex-wrap">
      <h2 className="m-0 text-[15px] font-bold text-ink">
        {title} <span className="font-medium text-ink-3 ml-1">{count}</span>
      </h2>
      {children}
    </div>
  )
}

function Th({ children, align = 'left', first, last }: { children: ReactNode; align?: 'left' | 'right'; first?: boolean; last?: boolean }) {
  return (
    <th
      className={`eyebrow pt-3 pb-2.5 ${align === 'right' ? 'text-right' : 'text-left'} ${
        first ? 'pl-5 pr-3' : last ? 'pl-3 pr-5' : 'px-3'
      }`}
    >
      {children}
    </th>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 min-w-0">
      <span className="text-xs font-medium text-ink-2">
        {label} {hint && <span className="font-normal text-ink-3">· {hint}</span>}
      </span>
      {children}
    </label>
  )
}

const textareaClass =
  'w-full box-border resize-y px-3 py-2.5 rounded-[10px] border border-line bg-bg text-[13px] leading-[1.6] text-ink outline-0 focus:border-accent transition-colors'

function ClienteSelect({
  clientes,
  value,
  onChange,
  label,
  variant = 'field',
}: {
  clientes: Cliente[]
  value: number | ''
  onChange: (id: number | '') => void
  label?: string
  variant?: 'field' | 'pill'
}) {
  return (
    <span
      className={`field relative pr-2.5 ${variant === 'pill' ? 'h-[38px] bg-surface' : ''}`}
    >
      <Building2 size={15} className="text-ink-3 shrink-0" />
      {label && <span className="text-xs text-ink-3">{label}</span>}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : '')}
        className={`pr-5 ${variant === 'pill' ? 'font-semibold' : 'font-medium'}`}
      >
        <option value="" disabled>
          Selecciona un cliente…
        </option>
        {clientes.map((c) => (
          <option key={c.id_cliente} value={c.id_cliente}>
            {c.nombre_cliente}
          </option>
        ))}
      </select>
      <ChevronDown size={14} className="absolute right-2.5 text-ink-3 pointer-events-none" />
    </span>
  )
}

/** Clientes del sistema + el seleccionado (el primero por defecto), para las pestañas que trabajan sobre uno. */
function useClientesConSeleccion() {
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [clienteId, setClienteId] = useState<number | ''>('')
  const [cargado, setCargado] = useState(false)
  useEffect(() => {
    fetchClientes()
      .then((cs) => {
        setClientes(cs)
        if (cs.length > 0) setClienteId(cs[0]!.id_cliente)
      })
      .catch(() => setClientes([]))
      .finally(() => setCargado(true))
  }, [])
  return { clientes, clienteId, setClienteId, cargado }
}

function SinClientes() {
  return (
    <Card className="p-5">
      <p className="m-0 text-[13px] text-ink-3">Todavía no hay clientes — crea uno primero en la pestaña “Clientes”.</p>
    </Card>
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
      setError(errorMsg(e, 'No se pudo crear el cliente'))
    } finally {
      setCreando(false)
    }
  }

  const handleToggleActivo = async (c: Cliente) => {
    try {
      await updateCliente(c.id_cliente, { activo: !c.activo })
      cargar()
    } catch (e) {
      setError(errorMsg(e, 'No se pudo actualizar el cliente'))
    }
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
      setError(errorMsg(e, 'No se pudo renombrar el cliente'))
    }
  }

  const activos = clientes.filter((c) => c.activo).length

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardTitle
          title="Nuevo cliente"
          subtitle="Cada cliente tiene su propia base de datos, que se crea automáticamente al registrarlo."
        />
        <div className="flex flex-wrap gap-3 items-end [&>label]:flex-[1_1_260px]">
          <Field label="Nombre del cliente">
            <span className="field">
              <Building2 size={15} className="text-ink-3 shrink-0" />
              <input
                value={nombreNuevo}
                onChange={(e) => setNombreNuevo(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCrear()}
                placeholder="Ej: Bancolombia"
              />
            </span>
          </Field>
          <Field label="Base de datos" hint="auto-generada">
            <span className="flex items-center gap-2 h-10 px-3 rounded-[10px] border border-dashed border-line bg-surface-2 min-w-0">
              <Database size={15} className="text-ink-3 shrink-0" />
              <span className={`font-mono text-xs truncate ${nombreNuevo.trim() ? 'text-ink' : 'text-ink-3'}`}>
                {nombreNuevo.trim() ? previewDbName(nombreNuevo) : 'se genera a partir del nombre'}
              </span>
            </span>
          </Field>
          <button type="button" onClick={handleCrear} disabled={creando || !nombreNuevo.trim()} className="btn-primary h-10">
            <Plus size={15} strokeWidth={2.2} />
            {creando ? 'Creando…' : 'Crear cliente'}
          </button>
        </div>
        {error && <p className="m-0 text-[13px] text-bad-fg">{error}</p>}
      </Card>

      <Card className="overflow-hidden">
        <TableHeader title="Clientes registrados" count={clientes.length}>
          <span className="text-xs text-ink-3">{activos} activos</span>
        </TableHeader>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] border-collapse text-[13px]">
            <thead>
              <tr>
                <Th first>Cliente</Th>
                <Th>Base de datos</Th>
                <Th>Estado</Th>
                <Th align="right" last>
                  Acciones
                </Th>
              </tr>
            </thead>
            <tbody>
              {clientes.map((c) => (
                <tr key={c.id_cliente} className="border-t border-line-soft transition-colors hover:bg-bg">
                  <td className="py-4 pl-5 pr-3">
                    <div className="flex items-center gap-3">
                      <ClientTile name={c.nombre_cliente} size="md" />
                      {editandoId === c.id_cliente ? (
                        <span className="field h-8 max-w-[260px]">
                          <input
                            value={nombreEditado}
                            onChange={(e) => setNombreEditado(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') guardarNombre(c.id_cliente)
                              if (e.key === 'Escape') setEditandoId(null)
                            }}
                            autoFocus
                          />
                        </span>
                      ) : (
                        <span className="font-semibold text-ink">{c.nombre_cliente}</span>
                      )}
                    </div>
                  </td>
                  <td className="py-4 px-3">
                    <span className="inline-flex items-center px-2 py-[3px] rounded-md bg-surface-2 font-mono text-[11.5px] text-ink-2">
                      {c.db_name}
                    </span>
                  </td>
                  <td className="py-4 px-3">
                    <Badge tone={c.activo ? 'ok' : 'mute'}>{c.activo ? 'Activo' : 'Inactivo'}</Badge>
                  </td>
                  <td className="py-4 pl-3 pr-5">
                    <div className="flex justify-end gap-1">
                      {editandoId === c.id_cliente ? (
                        <>
                          <button type="button" onClick={() => guardarNombre(c.id_cliente)} title="Guardar" className="btn-icon text-accent">
                            <Check size={16} />
                          </button>
                          <button type="button" onClick={() => setEditandoId(null)} title="Cancelar" className="btn-icon">
                            <X size={16} />
                          </button>
                        </>
                      ) : (
                        <>
                          <button type="button" onClick={() => empezarEdicion(c)} title="Renombrar" className="btn-icon">
                            <Pencil size={15} />
                          </button>
                          <ToggleButton activo={c.activo} onClick={() => handleToggleActivo(c)} />
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {clientes.length === 0 && <p className="m-0 px-5 py-6 text-[13px] text-ink-3">Todavía no hay clientes.</p>}
      </Card>
    </div>
  )
}

function ToggleButton({ activo, onClick }: { activo: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-8 px-3 rounded-lg border border-line bg-surface text-xs font-medium text-ink-2 hover:border-ink-3 hover:text-ink transition-colors"
    >
      {activo ? 'Desactivar' : 'Activar'}
    </button>
  )
}

// --- Campañas ------------------------------------------------------------------

const TIPO_CONDICION_LABEL: Record<string, string> = {
  regex_bot: 'El bot dice',
  regex_customer: 'El cliente dice',
  boton: 'Botón exacto',
}

// `configuracion.esquema_clasificacion` (categorías/indicadores/árbol de
// decisión propios de la campaña — ver `analysis/schema.py`) se edita sobre el
// mismo string JSON que usa el textarea "avanzado": cualquier cambio (de los
// campos o del textarea) se refleja en el otro porque comparten la misma
// fuente de verdad (`configJson`).
function leerConfig(configJson: string): { config: Record<string, unknown>; esquema: EsquemaClasificacion | null; invalido: boolean } {
  try {
    const config = configJson.trim() ? (JSON.parse(configJson) as Record<string, unknown>) : {}
    return { config, esquema: (config.esquema_clasificacion as EsquemaClasificacion | null | undefined) ?? null, invalido: false }
  } catch {
    return { config: {}, esquema: null, invalido: true }
  }
}

function conEsquema(configJson: string, esquema: EsquemaClasificacion | null): string {
  const { config } = leerConfig(configJson)
  if (esquema) return JSON.stringify({ ...config, esquema_clasificacion: esquema }, null, 2)
  const { esquema_clasificacion: _esquema, ...resto } = config
  return Object.keys(resto).length ? JSON.stringify(resto, null, 2) : ''
}

function resumenEsquema(esquema: EsquemaClasificacion | null | undefined): string {
  if (!esquema) return 'Categorías por defecto'
  return `${esquema.categorias.length} categorías · ${esquema.indicadores.length} indicadores`
}

function EsquemaFields({
  esquema,
  onChange,
  onReset,
}: {
  esquema: EsquemaClasificacion
  onChange: (e: EsquemaClasificacion) => void
  onReset: () => void
}) {
  const actualizarCategoria = (idx: number, cambios: Partial<CategoriaDef>) =>
    onChange({ ...esquema, categorias: esquema.categorias.map((c, i) => (i === idx ? { ...c, ...cambios } : c)) })

  const actualizarIndicador = (idx: number, cambios: Partial<IndicadorDef>) =>
    onChange({ ...esquema, indicadores: esquema.indicadores.map((ind, i) => (i === idx ? { ...ind, ...cambios } : ind)) })

  const actualizarPatron = (idxIndicador: number, idxCondicion: number, patron: string) =>
    onChange({
      ...esquema,
      indicadores: esquema.indicadores.map((ind, i) =>
        i !== idxIndicador ? ind : { ...ind, condiciones: ind.condiciones.map((c, j) => (j === idxCondicion ? { ...c, patron } : c)) },
      ),
    })

  return (
    <div className="flex flex-col gap-[22px]">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between gap-2">
          <span className="eyebrow">Categorías</span>
          <button type="button" onClick={onReset} className="text-xs text-ink-2 hover:text-bad-fg hover:underline">
            Usar categorías por defecto
          </button>
        </div>
        <div className="flex flex-col gap-2">
          {esquema.categorias.map((c, idx) => (
            <div
              key={idx}
              className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2.5 py-1.5 pr-1.5 pl-2 rounded-xl border border-line-soft bg-bg focus-within:border-line"
            >
              <label
                title="Cambiar color"
                className="relative w-[26px] h-[26px] rounded-lg cursor-pointer shadow-[inset_0_0_0_1px_rgba(0,0,0,.08)]"
                style={{ backgroundColor: c.color }}
              >
                <input
                  type="color"
                  value={c.color}
                  onChange={(e) => actualizarCategoria(idx, { color: e.target.value })}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
              </label>
              <input
                value={c.label}
                onChange={(e) => actualizarCategoria(idx, { label: e.target.value })}
                className="h-8 border-0 outline-0 bg-transparent text-[13px] font-medium text-ink min-w-0"
              />
              <span className="flex items-center gap-2 pr-1.5">
                {c.id === esquema.categoria_sin_respuesta && <span className="text-[11px] text-ink-3">sin respuesta</span>}
                <span className="font-mono text-[11px] text-ink-3 px-1.5 py-0.5 rounded-md bg-surface border border-line-soft">
                  {c.id}
                </span>
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className="eyebrow">Indicadores</span>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-2.5">
          {esquema.indicadores.map((ind, idx) => (
            <div
              key={idx}
              className="flex flex-col gap-2.5 p-3.5 rounded-xl border border-line-soft bg-surface shadow-[0_1px_2px_rgba(15,23,42,.04)]"
            >
              <div className="flex items-center gap-2">
                <span
                  className={`inline-flex items-center h-[22px] px-2 rounded-full text-[11px] font-semibold shrink-0 ${
                    ind.tipo === 'ia' ? 'bg-accent-soft text-accent-ink' : 'bg-ok-bg text-ok-fg'
                  }`}
                >
                  {ind.tipo === 'ia' ? 'Criterio IA' : 'Regla'}
                </span>
                <input
                  value={ind.label}
                  onChange={(e) => actualizarIndicador(idx, { label: e.target.value })}
                  className="flex-1 min-w-0 border-0 outline-0 bg-transparent text-[13.5px] font-semibold text-ink"
                />
              </div>
              {ind.tipo === 'ia' ? (
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] text-ink-3">Criterio</span>
                  <textarea
                    value={ind.descripcion_ia ?? ''}
                    onChange={(e) => actualizarIndicador(idx, { descripcion_ia: e.target.value })}
                    rows={2}
                    placeholder="Criterio que debe evaluar la IA"
                    className="px-2.5 py-[7px] rounded-lg bg-bg border border-line-soft text-xs leading-normal text-ink-2 outline-0 resize-y focus:border-accent"
                  />
                </div>
              ) : (
                ind.condiciones.map((cond, j) => (
                  <div key={j} className="flex flex-col gap-1">
                    <span className="text-[11px] text-ink-3">{TIPO_CONDICION_LABEL[cond.tipo] ?? cond.tipo}</span>
                    <input
                      value={cond.patron}
                      onChange={(e) => actualizarPatron(idx, j, e.target.value)}
                      className="px-2.5 py-[7px] rounded-lg bg-bg border border-line-soft font-mono text-xs text-ink-2 outline-0 focus:border-accent"
                    />
                  </div>
                ))
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <span className="eyebrow">Árbol de decisión</span>
        <ol className="m-0 pl-5 text-xs text-ink-2 space-y-1 list-decimal">
          {esquema.arbol_decision.map((r, i) => (
            <li key={i}>
              {Object.keys(r.condicion).length === 0
                ? 'en cualquier otro caso'
                : Object.entries(r.condicion)
                    .map(([k, v]) => `${k}=${v ? 'sí' : 'no'}`)
                    .join(' y ')}
              {' → '}
              <strong className="font-semibold text-ink">
                {esquema.categorias.find((c) => c.id === r.categoria)?.label ?? r.categoria}
              </strong>
            </li>
          ))}
        </ol>
        <p className="m-0 text-[11px] text-ink-3">Para reordenar filas o cambiar la lógica del árbol, edita el JSON avanzado.</p>
      </div>
    </div>
  )
}

function useGenerarEsquema(clienteId: number | '') {
  const [generando, setGenerando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const generar = async (prompt: string): Promise<EsquemaClasificacion | null> => {
    if (!prompt.trim() || clienteId === '') return null
    setGenerando(true)
    setError(null)
    try {
      const { esquema_clasificacion } = await generarEsquemaCampana(clienteId, prompt.trim())
      return esquema_clasificacion
    } catch (e) {
      setError(errorMsg(e, 'No se pudo generar el esquema'))
      return null
    } finally {
      setGenerando(false)
    }
  }
  return { generar, generando, error }
}

function NuevaCampana({ clienteId, onCreada }: { clienteId: number | ''; onCreada: () => void }) {
  const [nombre, setNombre] = useState('')
  const [prompt, setPrompt] = useState('')
  const [configJson, setConfigJson] = useState('')
  const [mostrarJson, setMostrarJson] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { generar, generando, error: genError } = useGenerarEsquema(clienteId)
  const { esquema, invalido } = leerConfig(configJson)

  const handleGenerar = async () => {
    const nuevo = await generar(prompt)
    if (nuevo) setConfigJson((json) => conEsquema(json, nuevo))
  }

  const handleCrear = async () => {
    if (!nombre.trim() || clienteId === '') return
    setError(null)
    try {
      const configuracion = configJson.trim() ? JSON.parse(configJson) : undefined
      await createClienteCampana(clienteId, nombre.trim(), configuracion)
      setNombre('')
      setPrompt('')
      setConfigJson('')
      setMostrarJson(false)
      onCreada()
    } catch (e) {
      setError(e instanceof SyntaxError ? 'El JSON de configuración no es válido.' : errorMsg(e, 'No se pudo crear la campaña'))
    }
  }

  return (
    <Card className="p-5 flex flex-col gap-3.5">
      <CardTitle
        title="Nueva campaña"
        subtitle="Describe en lenguaje natural cómo quieres clasificar y la IA generará un esquema borrador para revisar."
      />
      <Field label="Nombre">
        <span className="field">
          <Megaphone size={15} className="text-ink-3 shrink-0" />
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej: Rediferidos_TDC" />
        </span>
      </Field>
      <Field label="Descripción del criterio">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder="Ej: “Vendo cursos online. Quiero saber quién se matriculó, quién solo preguntó el precio y quién no mostró interés.”"
          className={textareaClass}
        />
      </Field>
      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={handleGenerar}
          disabled={generando || !prompt.trim()}
          className="flex items-center gap-2 h-[38px] px-3.5 rounded-[10px] border border-[var(--bubble-out-border)] bg-accent-soft text-accent-ink text-[13px] font-semibold hover:border-accent disabled:opacity-45 disabled:cursor-not-allowed transition-colors"
        >
          <Sparkles size={15} className="text-accent" />
          {generando ? 'Generando…' : esquema ? 'Regenerar esquema con IA' : 'Generar esquema con IA'}
        </button>
        <button type="button" onClick={handleCrear} disabled={!nombre.trim()} className="btn-primary">
          <Plus size={15} strokeWidth={2.2} />
          Crear campaña
        </button>
        <button
          type="button"
          onClick={() => setMostrarJson((v) => !v)}
          className="ml-auto text-xs font-medium text-ink-2 hover:text-ink hover:underline"
        >
          {mostrarJson ? 'Ocultar JSON avanzado' : 'Editar JSON avanzado'}
        </button>
      </div>
      {(genError || error) && <p className="m-0 text-[13px] text-bad-fg">{genError ?? error}</p>}
      {invalido && <p className="m-0 text-xs text-bad-fg">El JSON avanzado tiene un error de sintaxis — corrígelo para editar los campos.</p>}

      {esquema && (
        <div className="pt-4 border-t border-line-soft">
          <EsquemaFields
            esquema={esquema}
            onChange={(e) => setConfigJson((json) => conEsquema(json, e))}
            onReset={() => setConfigJson((json) => conEsquema(json, null))}
          />
        </div>
      )}

      {mostrarJson && (
        <textarea
          value={configJson}
          onChange={(e) => setConfigJson(e.target.value)}
          placeholder="JSON opcional — vacío = usar los valores por defecto (botones/regex del bot de venta de cupo)"
          rows={8}
          className={`${textareaClass} font-mono text-xs`}
        />
      )}
    </Card>
  )
}

function CampanaCard({ camp, clienteId, onGuardada }: { camp: Campaign; clienteId: number | ''; onGuardada: () => void }) {
  const [editando, setEditando] = useState(false)
  const [configJson, setConfigJson] = useState('')
  const [prompt, setPrompt] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const { generar, generando, error: genError } = useGenerarEsquema(clienteId)
  const { esquema, invalido } = leerConfig(configJson)
  const activa = /activ/i.test(camp.estado)

  const empezar = () => {
    setConfigJson(JSON.stringify(camp.configuracion ?? {}, null, 2))
    setPrompt('')
    setError(null)
    setEditando(true)
  }

  const handleGenerar = async () => {
    const nuevo = await generar(prompt)
    if (nuevo) {
      setConfigJson((json) => conEsquema(json, nuevo))
      setPrompt('')
    }
  }

  const guardar = async () => {
    if (clienteId === '') return
    setError(null)
    setGuardando(true)
    try {
      await updateClienteCampana(clienteId, camp.id_campana, { configuracion: JSON.parse(configJson) })
      setEditando(false)
      onGuardada()
    } catch (e) {
      setError(e instanceof SyntaxError ? 'El JSON de configuración no es válido.' : errorMsg(e, 'No se pudo actualizar la campaña'))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className={`flex items-center gap-3 px-5 py-4 flex-wrap ${editando ? 'border-b border-line-soft' : ''}`}>
        <span className="w-9 h-9 rounded-[10px] bg-accent-soft text-accent flex items-center justify-center shrink-0">
          <Megaphone size={17} />
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="m-0 text-[15px] font-bold text-ink">{camp.nombre_campana}</h2>
            <span
              className={`inline-flex items-center h-5 px-2 rounded-full text-[11px] font-semibold tracking-[.04em] uppercase ${
                activa ? 'bg-ok-bg text-ok-fg' : 'bg-mute-bg text-mute-fg'
              }`}
            >
              {camp.estado}
            </span>
          </div>
          <div className="text-xs text-ink-3 mt-0.5">{resumenEsquema(camp.configuracion?.esquema_clasificacion)}</div>
        </div>
        {editando ? (
          <>
            <button
              type="button"
              onClick={() => setEditando(false)}
              disabled={guardando}
              className="h-[34px] px-3 rounded-lg text-[12.5px] font-medium text-ink-2 hover:bg-surface-2 hover:text-ink"
            >
              Cancelar
            </button>
            <button type="button" onClick={guardar} disabled={guardando || invalido} className="btn-primary h-[34px] px-3.5 text-[12.5px] shadow-none">
              {guardando ? 'Guardando…' : 'Guardar cambios'}
            </button>
          </>
        ) : (
          <button type="button" onClick={empezar} className="btn-secondary h-[34px] px-3 text-[12.5px]">
            <Pencil size={14} />
            Editar configuración
          </button>
        )}
      </div>

      {editando && (
        <div className="p-5 flex flex-col gap-[22px]">
          <div className="flex gap-2.5 items-start flex-wrap">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={2}
              placeholder={
                esquema
                  ? 'Describe cómo quieres clasificar para regenerar el esquema…'
                  : 'Describe cómo quieres clasificar para generar un esquema propio…'
              }
              className={`${textareaClass} flex-[1_1_360px] w-auto`}
            />
            <button
              type="button"
              onClick={handleGenerar}
              disabled={generando || !prompt.trim()}
              className="btn-secondary hover:border-accent! hover:text-accent-ink"
            >
              <Sparkles size={15} className="text-accent" />
              {generando ? 'Generando…' : esquema ? 'Regenerar con IA' : 'Generar con IA'}
            </button>
          </div>
          {(genError || error) && <p className="m-0 -mt-3 text-[13px] text-bad-fg">{genError ?? error}</p>}
          {invalido && <p className="m-0 -mt-3 text-xs text-bad-fg">El JSON avanzado tiene un error de sintaxis — corrígelo para editar los campos.</p>}

          {esquema ? (
            <EsquemaFields
              esquema={esquema}
              onChange={(e) => setConfigJson((json) => conEsquema(json, e))}
              onReset={() => setConfigJson((json) => conEsquema(json, null))}
            />
          ) : (
            !invalido && (
              <div className="flex items-start gap-2.5 px-3.5 py-3 rounded-xl bg-bg border border-line-soft text-[12.5px] text-ink-2">
                <Info size={15} className="shrink-0 mt-0.5 text-ink-3" />
                Esta campaña usa las categorías por defecto. Genera un esquema con IA para definir las suyas.
              </div>
            )
          )}

          <details>
            <summary className="text-xs font-medium text-ink-2 hover:text-ink cursor-pointer">JSON avanzado (edición manual completa)</summary>
            <textarea
              value={configJson}
              onChange={(e) => setConfigJson(e.target.value)}
              rows={12}
              className={`${textareaClass} font-mono text-xs mt-2`}
            />
          </details>
        </div>
      )}
    </Card>
  )
}

function CampanasTab() {
  const { clientes, clienteId, setClienteId, cargado } = useClientesConSeleccion()
  const [campanas, setCampanas] = useState<Campaign[]>([])

  const cargarCampanas = (id: number) => fetchClienteCampanas(id).then(setCampanas).catch(() => setCampanas([]))

  useEffect(() => {
    if (clienteId !== '') cargarCampanas(clienteId)
  }, [clienteId])

  if (cargado && clientes.length === 0) return <SinClientes />

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="text-[13px] text-ink-2">Campañas de</span>
        <ClienteSelect clientes={clientes} value={clienteId} onChange={setClienteId} variant="pill" />
        <span className="text-xs text-ink-3">
          · {campanas.length} {campanas.length === 1 ? 'campaña registrada' : 'campañas registradas'}
        </span>
      </div>

      <NuevaCampana clienteId={clienteId} onCreada={() => clienteId !== '' && cargarCampanas(clienteId)} />

      {campanas.map((camp) => (
        <CampanaCard
          key={camp.id_campana}
          camp={camp}
          clienteId={clienteId}
          onGuardada={() => clienteId !== '' && cargarCampanas(clienteId)}
        />
      ))}
      {campanas.length === 0 && (
        <Card className="p-5">
          <p className="m-0 text-[13px] text-ink-3">Este cliente todavía no tiene campañas.</p>
        </Card>
      )}
    </div>
  )
}

// --- Usuarios ------------------------------------------------------------------

// Roles del resumen de Usuarios, con el color de su ícono (mismo tono que su badge).
const ROLES_RESUMEN: { rol: string; cls: string }[] = [
  { rol: 'super_admin', cls: 'bg-warn-bg text-warn-fg' },
  { rol: 'admin', cls: 'bg-accent-soft text-accent-ink' },
  { rol: 'user', cls: 'bg-ok-bg text-ok-fg' },
]

function ClienteChips({
  clientes,
  selected,
  onChange,
}: {
  clientes: Cliente[]
  selected: number[]
  onChange: (ids: number[]) => void
}) {
  if (clientes.length === 0) return <span className="text-xs text-ink-3">No hay clientes creados</span>
  return (
    <>
      {clientes.map((c) => {
        const on = selected.includes(c.id_cliente)
        return (
          <button
            key={c.id_cliente}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(on ? selected.filter((x) => x !== c.id_cliente) : [...selected, c.id_cliente])}
            className={`flex items-center gap-1.5 h-[30px] px-3 rounded-full border text-xs font-medium transition-colors hover:border-ink-3 ${
              on ? 'bg-accent-soft text-accent-ink border-transparent' : 'bg-surface text-ink-2 border-line'
            }`}
          >
            <span
              className={`w-3.5 h-3.5 rounded border-[1.5px] flex items-center justify-center text-white ${
                on ? 'bg-accent border-accent' : 'border-ink-3'
              }`}
            >
              {on && <Check size={10} strokeWidth={3.5} />}
            </span>
            {c.nombre_cliente}
          </button>
        )
      })}
    </>
  )
}

function RolSelect({ roles, value, onChange, placeholder }: { roles: Rol[]; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <span className="field relative pr-2.5">
      <select value={value} onChange={(e) => onChange(e.target.value)} className="pr-5">
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {roles.map((r) => (
          <option key={r.id_rol} value={r.id_rol}>
            {rolLabel(r.nombre_rol)}
          </option>
        ))}
      </select>
      <ChevronDown size={14} className="absolute right-2.5 text-ink-3 pointer-events-none" />
    </span>
  )
}

interface EditForm {
  nombre_usuario: string
  id_rol: string
  id_clientes: number[]
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
  const [busqueda, setBusqueda] = useState('')
  const [filtroRol, setFiltroRol] = useState<string | null>(null)

  const cargar = () => fetchUsuarios().then(setUsuarios).catch(() => setUsuarios([]))

  useEffect(() => {
    cargar()
    fetchClientes().then(setClientes).catch(() => setClientes([]))
    fetchRoles().then(setRoles).catch(() => setRoles([]))
  }, [])

  const formOk = Boolean(form.nombre_usuario.trim() && form.email.trim() && form.id_rol)

  const handleCrear = async () => {
    if (!formOk) return
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
      setError(errorMsg(e, 'No se pudo crear el usuario'))
    } finally {
      setCreando(false)
    }
  }

  const handleToggleActivo = async (u: Usuario) => {
    try {
      await updateUsuario(u.id_usuario, { activo: !u.activo })
      cargar()
    } catch (e) {
      setError(errorMsg(e, 'No se pudo actualizar el usuario'))
    }
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
      setError(errorMsg(e, 'No se pudo actualizar el usuario'))
    } finally {
      setGuardando(false)
    }
  }

  const q = busqueda.trim().toLowerCase()
  const visibles = usuarios.filter(
    (u) =>
      (!q || `${u.nombre_usuario} ${u.email}`.toLowerCase().includes(q)) && (!filtroRol || u.rol.nombre_rol === filtroRol),
  )
  const porRol = (nombreRol: string) => usuarios.filter((u) => u.rol.nombre_rol === nombreRol).length
  const resumen = [
    { key: null, label: 'Total', n: usuarios.length, cls: 'bg-surface-2 text-ink-2' },
    ...ROLES_RESUMEN.map(({ rol, cls }) => ({ key: rol as string | null, label: rolLabel(rol), n: porRol(rol), cls })),
  ]

  return (
    <div className="flex flex-col gap-4">
      <section className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-px bg-line-soft border border-line-soft rounded-2xl shadow-card overflow-hidden">
        {resumen.map((r) => (
          <button
            key={r.label}
            type="button"
            aria-pressed={filtroRol === r.key}
            onClick={() => setFiltroRol(r.key)}
            className={`flex items-center gap-3 px-[18px] py-4 text-left transition-colors hover:bg-bg ${
              filtroRol === r.key ? 'bg-bg' : 'bg-surface'
            }`}
          >
            <span className={`w-9 h-9 rounded-[10px] flex items-center justify-center shrink-0 ${r.cls}`}>
              <Users size={17} />
            </span>
            <span className="flex flex-col">
              <span className="text-[22px] font-bold tracking-[-.02em] text-ink leading-[1.1] tabular-nums">{r.n}</span>
              <span className="text-xs text-ink-2">{r.label}</span>
            </span>
          </button>
        ))}
      </section>

      <Card className="p-5 flex flex-col gap-3.5">
        <CardTitle
          title="Agregar usuario"
          subtitle="Sin ningún cliente marcado, el usuario es super admin y ve todos los clientes."
        />
        <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
          <Field label="Nombre">
            <span className="field">
              <input
                value={form.nombre_usuario}
                onChange={(e) => setForm({ ...form, nombre_usuario: e.target.value })}
                placeholder="Nombre completo"
              />
            </span>
          </Field>
          <Field label="Correo">
            <span className="field">
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="correo@empresa.com"
              />
            </span>
          </Field>
          <Field label="Rol">
            <RolSelect roles={roles} value={form.id_rol} onChange={(id_rol) => setForm({ ...form, id_rol })} placeholder="Selecciona un rol" />
          </Field>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium text-ink-2 mr-1">Clientes</span>
          <ClienteChips clientes={clientes} selected={form.id_clientes} onChange={(ids) => setForm({ ...form, id_clientes: ids })} />
          <button type="button" onClick={handleCrear} disabled={creando || !formOk} className="btn-primary ml-auto">
            <UserPlus size={15} />
            {creando ? 'Agregando…' : 'Agregar usuario'}
          </button>
        </div>
        {error && <p className="m-0 text-[13px] text-bad-fg">{error}</p>}
      </Card>

      <Card className="overflow-hidden">
        <TableHeader title="Usuarios registrados" count={visibles.length}>
          <label className="field h-[34px] w-60 max-w-full px-2.5 rounded-lg">
            <Search size={14} className="text-ink-3 shrink-0" />
            <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar usuario…" className="text-[12.5px]!" />
          </label>
        </TableHeader>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] border-collapse text-[13px]">
            <thead>
              <tr>
                <Th first>Usuario</Th>
                <Th>Rol</Th>
                <Th>Clientes</Th>
                <Th>Registro</Th>
                <Th align="right" last>
                  Acciones
                </Th>
              </tr>
            </thead>
            <tbody>
              {visibles.map((u) => {
                const esUno = u.id_usuario === currentUser?.id_usuario
                const editando = editandoId === u.id_usuario
                return (
                  <tr
                    key={u.id_usuario}
                    className={`border-t border-line-soft align-middle transition-colors hover:bg-bg ${!u.activo ? 'opacity-50' : ''}`}
                  >
                    <td className="py-3.5 pl-5 pr-3">
                      <div className="flex items-center gap-3">
                        <span className="w-9 h-9 rounded-full shrink-0 flex items-center justify-center text-[12.5px] font-semibold bg-surface-2 text-ink-2">
                          {initials(u.nombre_usuario)}
                        </span>
                        <div className="min-w-0 leading-[1.35]">
                          {editando ? (
                            <span className="field h-8">
                              <input
                                value={editForm.nombre_usuario}
                                onChange={(e) => setEditForm({ ...editForm, nombre_usuario: e.target.value })}
                              />
                            </span>
                          ) : (
                            <div className="flex items-center gap-1.5 font-semibold text-ink">
                              {u.nombre_usuario}
                              {esUno && (
                                <span className="text-[10.5px] font-semibold px-[7px] py-px rounded-full bg-accent-soft text-accent-ink">Tú</span>
                              )}
                            </div>
                          )}
                          <div className="text-xs text-ink-3">{u.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-3">
                      {editando ? (
                        <RolSelect roles={roles} value={editForm.id_rol} onChange={(id_rol) => setEditForm({ ...editForm, id_rol })} />
                      ) : (
                        <Badge tone={rolTone(u.rol.nombre_rol)}>{rolLabel(u.rol.nombre_rol)}</Badge>
                      )}
                    </td>
                    <td className="py-3.5 px-3">
                      <div className="flex flex-wrap gap-1">
                        {editando ? (
                          <ClienteChips
                            clientes={clientes}
                            selected={editForm.id_clientes}
                            onChange={(ids) => setEditForm({ ...editForm, id_clientes: ids })}
                          />
                        ) : u.clientes.length > 0 ? (
                          u.clientes.map((c) => (
                            <span key={c.id_cliente} className="px-2 py-0.5 rounded-md bg-surface-2 text-[11.5px] font-medium text-ink-2">
                              {c.nombre_cliente}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-ink-3">Todos los clientes</span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-3 text-ink-2 whitespace-nowrap">{formatMediumDate(u.fecha_creacion)}</td>
                    <td className="py-3.5 pl-3 pr-5">
                      <div className="flex justify-end gap-1">
                        {esUno ? (
                          <span className="text-ink-3">—</span>
                        ) : editando ? (
                          <>
                            <button
                              type="button"
                              onClick={() => guardarEdicion(u.id_usuario)}
                              disabled={guardando}
                              title="Guardar"
                              className="btn-icon text-accent disabled:opacity-50"
                            >
                              <Check size={16} />
                            </button>
                            <button type="button" onClick={() => setEditandoId(null)} title="Cancelar" className="btn-icon">
                              <X size={16} />
                            </button>
                          </>
                        ) : (
                          <>
                            <button type="button" onClick={() => empezarEdicion(u)} title="Editar" className="btn-icon">
                              <Pencil size={15} />
                            </button>
                            <ToggleButton activo={u.activo} onClick={() => handleToggleActivo(u)} />
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {visibles.length === 0 && (
          <p className="m-0 px-5 py-6 text-[13px] text-ink-3">
            {usuarios.length === 0 ? 'Todavía no hay usuarios.' : 'Ningún usuario coincide con la búsqueda.'}
          </p>
        )}
      </Card>
    </div>
  )
}

// --- Uso de IA -----------------------------------------------------------------

const TIPO_USO_LABEL: Record<string, string> = {
  clasificacion: 'Clasificación de conversaciones',
  generar_esquema: 'Generación de esquemas con IA',
}

const usd = (v: number, decimals: number) => `$${v.toFixed(decimals)}`

function mesLabel(mes: string): string {
  const [y, m] = mes.split('-').map(Number)
  const corto = MESES_CORTOS[(m ?? 1) - 1] ?? ''
  return `${corto.charAt(0).toUpperCase()}${corto.slice(1)} ${y}`
}

function mesAnterior(mes: string, n: number): string {
  const [y, m] = mes.split('-').map(Number)
  const d = new Date(y!, (m ?? 1) - 1 - n, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function UsoIATab() {
  const { clientes, clienteId, setClienteId, cargado } = useClientesConSeleccion()
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [uso, setUso] = useState<UsoIA | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

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
        if (!cancelled) setError(errorMsg(e, 'No se pudo cargar el uso de IA'))
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
  // Se muestran al menos los 6 meses que terminan en el último con datos, para
  // que uno o dos meses sueltos no ocupen todo el ancho.
  const meses = useMemo(() => {
    if (!uso || uso.por_mes.length === 0) return []
    const acumulado = new Map<string, { costo: number; incompleto: boolean }>()
    for (const f of uso.por_mes) {
      const entrada = acumulado.get(f.mes) ?? { costo: 0, incompleto: false }
      if (f.costo_usd != null) entrada.costo += f.costo_usd
      else entrada.incompleto = true
      acumulado.set(f.mes, entrada)
    }
    const conDatos = Array.from(acumulado.keys()).sort()
    const ultimo = conDatos[conDatos.length - 1]!
    let inicio = mesAnterior(ultimo, 5)
    if (conDatos[0]! < inicio) inicio = conDatos[0]!
    const lista: string[] = []
    for (let m = inicio; m <= ultimo; m = mesAnterior(m, -1)) lista.push(m)
    return lista.map((mes) => ({ mes, ...(acumulado.get(mes) ?? { costo: 0, incompleto: false }), conDatos: acumulado.has(mes) }))
  }, [uso])
  const maxCosto = Math.max(...meses.map((m) => m.costo), 0)
  const algunMesIncompleto = meses.some((m) => m.incompleto)

  const filas = uso?.filas ?? []
  const tokensEntrada = filas.reduce((a, f) => a + f.tokens_prompt, 0)
  const tokensSalida = filas.reduce((a, f) => a + f.tokens_completion, 0)
  const llamadas = filas.reduce((a, f) => a + f.llamadas, 0)
  const clasif = filas.filter((f) => f.tipo === 'clasificacion')
  const llamadasClasif = clasif.reduce((a, f) => a + f.llamadas, 0)
  const costoClasif = clasif.every((f) => f.costo_usd != null) ? clasif.reduce((a, f) => a + (f.costo_usd ?? 0), 0) : null
  const esquemas = filas.filter((f) => f.tipo === 'generar_esquema').reduce((a, f) => a + f.llamadas, 0)

  const kpis = [
    {
      label: 'Tokens consumidos',
      value: formatNumber(uso?.tokens_totales ?? 0),
      hint: `${formatNumber(tokensEntrada)} entrada · ${formatNumber(tokensSalida)} salida`,
    },
    {
      label: 'Costo estimado',
      value: uso?.costo_total_usd != null ? usd(uso.costo_total_usd, 2) : '—',
      hint:
        uso && uso.costo_total_usd == null && filas.length > 0
          ? 'Algún modelo no tiene precio conocido'
          : `USD · ${desde || hasta ? 'período seleccionado' : 'todo el período'}`,
    },
    {
      label: 'Llamadas a la IA',
      value: formatNumber(llamadas),
      hint: `${formatNumber(llamadasClasif)} clasificaciones · ${formatNumber(esquemas)} esquemas`,
    },
    {
      label: 'Costo por conversación',
      value: costoClasif != null && llamadasClasif > 0 ? usd(costoClasif / llamadasClasif, 4) : '—',
      hint: 'Promedio de las clasificadas por IA',
    },
  ]

  if (cargado && clientes.length === 0) return <SinClientes />

  return (
    <div className="flex flex-col gap-4">
      <section className="surface p-2.5 flex items-center justify-between gap-3 flex-wrap">
        <ClienteSelect clientes={clientes} value={clienteId} onChange={setClienteId} label="Cliente" />
        <div className="flex items-center gap-3">
          {loading && <span className="text-xs text-ink-3">Cargando…</span>}
          <DateRangeField
            desde={desde}
            hasta={hasta}
            onChange={(p) => {
              if (p.desde !== undefined) setDesde(p.desde)
              if (p.hasta !== undefined) setHasta(p.hasta)
            }}
          />
        </div>
      </section>

      {error && <p className="m-0 text-[13px] text-bad-fg">{error}</p>}

      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3.5">
        {kpis.map((k) => (
          <div key={k.label} className="surface flex flex-col gap-3 p-[18px]">
            <span className="text-[13px] font-semibold text-ink-2">{k.label}</span>
            <span className="text-[28px] font-bold tracking-[-.03em] leading-none text-ink tabular-nums">{k.value}</span>
            <span className="text-xs text-ink-3">{k.hint}</span>
          </div>
        ))}
      </div>

      <Card>
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <h2 className="m-0 text-[15px] font-bold text-ink">Gasto por mes</h2>
          <span className="text-xs text-ink-3">USD estimado</span>
        </div>
        {meses.length === 0 ? (
          <p className="m-0 text-[13px] text-ink-3 py-8 text-center">No hay uso de IA registrado en este rango.</p>
        ) : (
          <div>
            <div
              className="grid gap-4 items-end h-[220px] pb-1 border-b border-line-soft bg-[linear-gradient(var(--border-soft)_1px,transparent_1px)] bg-[length:100%_25%]"
              style={{ gridTemplateColumns: `repeat(${meses.length}, minmax(0, 1fr))` }}
            >
              {meses.map((m, i) => (
                <div key={m.mes} className="flex flex-col items-center justify-end gap-1.5 h-full" title={m.incompleto ? 'Parcial: incluye un modelo sin precio conocido' : undefined}>
                  <span className={`text-xs font-semibold tabular-nums ${m.conDatos ? 'text-ink' : 'text-ink-3'}`}>
                    {m.conDatos ? `${usd(m.costo, 2)}${m.incompleto ? '*' : ''}` : '—'}
                  </span>
                  <div
                    className="w-[min(56px,100%)] min-h-[3px] rounded-[8px_8px_3px_3px] transition-[height] duration-[400ms] ease-[cubic-bezier(.2,.8,.2,1)]"
                    style={{
                      height: maxCosto > 0 ? `${((m.costo / (maxCosto * 1.15)) * 100).toFixed(1)}%` : '0%',
                      background: !m.conDatos
                        ? 'var(--surface-2)'
                        : i === meses.length - 1
                          ? 'var(--accent)'
                          : 'color-mix(in srgb, var(--accent) 55%, var(--surface))',
                    }}
                  />
                </div>
              ))}
            </div>
            <div className="grid gap-4 mt-1.5" style={{ gridTemplateColumns: `repeat(${meses.length}, minmax(0, 1fr))` }}>
              {meses.map((m) => (
                <span key={m.mes} className="text-center text-xs text-ink-3">
                  {mesLabel(m.mes)}
                </span>
              ))}
            </div>
            {algunMesIncompleto && (
              <p className="m-0 mt-3 text-xs text-ink-3">
                * Parcial: incluye un modelo sin precio conocido, así que el costo real es mayor al mostrado.
              </p>
            )}
          </div>
        )}
      </Card>

      <Card className="overflow-hidden">
        <div className="px-5 py-4 border-b border-line-soft">
          <h2 className="m-0 text-[15px] font-bold text-ink">Detalle por modelo</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-[13px]">
            <thead>
              <tr>
                <Th first>Modelo</Th>
                <Th>Uso</Th>
                <Th align="right">Llamadas</Th>
                <Th align="right">Tokens entrada</Th>
                <Th align="right">Tokens salida</Th>
                <Th align="right" last>
                  Costo estimado
                </Th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f, i) => (
                <tr key={i} className="border-t border-line-soft">
                  <td className="py-4 pl-5 pr-3">
                    <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-surface-2 font-mono text-xs text-ink">
                      <Bot size={13} className="text-accent" />
                      {f.modelo}
                    </span>
                  </td>
                  <td className="py-4 px-3 text-ink-2">{TIPO_USO_LABEL[f.tipo] ?? f.tipo}</td>
                  <td className="py-4 px-3 text-right tabular-nums text-ink">{formatNumber(f.llamadas)}</td>
                  <td className="py-4 px-3 text-right tabular-nums text-ink">{formatNumber(f.tokens_prompt)}</td>
                  <td className="py-4 px-3 text-right tabular-nums text-ink">{formatNumber(f.tokens_completion)}</td>
                  <td className="py-4 pl-3 pr-5 text-right tabular-nums font-bold text-ink">
                    {f.costo_usd != null ? usd(f.costo_usd, 4) : <span className="font-normal text-ink-3">no disponible</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {uso && filas.length === 0 && (
          <p className="m-0 px-5 py-6 text-[13px] text-ink-3 text-center">Este cliente todavía no tiene uso de IA registrado.</p>
        )}
        <div className="flex items-start gap-2 px-5 py-3 border-t border-line-soft text-xs leading-normal text-ink-3">
          <Info size={14} className="shrink-0 mt-0.5" />
          <span>
            Precios de referencia (ver <code className="font-mono text-[11.5px] text-ink-2">analysis/pricing.py</code>). Verifícalos
            contra la página oficial de precios de OpenAI si necesitas el dato exacto.
          </span>
        </div>
      </Card>
    </div>
  )
}

// --- Mantenimiento (borrado de conversaciones por fecha) ---------------------

function MantenimientoTab() {
  const { clientes, clienteId, setClienteId, cargado } = useClientesConSeleccion()
  const [fecha, setFecha] = useState('')
  const [confirmando, setConfirmando] = useState(false)
  const [textoConfirmacion, setTextoConfirmacion] = useState('')
  const [eliminando, setEliminando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resultado, setResultado] = useState<{ cliente: string; fecha: string; conversaciones: number; mensajes: number } | null>(
    null,
  )

  const clienteSeleccionado = clientes.find((c) => c.id_cliente === clienteId)
  const nombreCliente = clienteSeleccionado?.nombre_cliente ?? ''
  const confirmado = textoConfirmacion.trim() === nombreCliente

  const handleConfirmar = async () => {
    if (clienteId === '' || !fecha || !confirmado) return
    setEliminando(true)
    setError(null)
    try {
      const res = await eliminarConversacionesPorFecha(clienteId, fecha)
      setResultado({ cliente: nombreCliente, fecha, conversaciones: res.conversaciones_eliminadas, mensajes: res.mensajes_eliminados })
      setConfirmando(false)
    } catch (e) {
      setError(errorMsg(e, 'No se pudieron eliminar las conversaciones'))
    } finally {
      setEliminando(false)
    }
  }

  if (cargado && clientes.length === 0) return <SinClientes />

  return (
    <div className="flex flex-col gap-4 max-w-[880px]">
      <Card className="overflow-hidden">
        <div className="flex items-start gap-3.5 p-5 border-b border-line-soft">
          <span className="w-10 h-10 rounded-xl bg-bad-bg text-bad-fg flex items-center justify-center shrink-0">
            <Trash2 size={18} />
          </span>
          <div>
            <h2 className="m-0 text-[15px] font-bold text-ink">Eliminar conversaciones por fecha</h2>
            <p className="mt-1 mb-0 text-[13px] leading-[1.6] text-ink-2">
              Pensado para descartar una carga con datos incorrectos y volver a subir el archivo.
            </p>
          </div>
        </div>
        <div className="p-5 flex flex-col gap-4">
          <div className="flex items-start gap-2.5 px-3.5 py-3 rounded-xl bg-bad-bg text-bad-fg text-[12.5px] leading-[1.55]">
            <AlertTriangle size={16} className="shrink-0 mt-px" />
            <span>
              Se eliminan permanentemente las conversaciones, sus mensajes y su análisis para la fecha y el cliente elegidos.{' '}
              <strong className="font-bold">No se puede deshacer.</strong> El uso de IA ya registrado no se borra.
            </span>
          </div>
          <div className="flex flex-wrap gap-3 items-end [&>label]:flex-[1_1_200px]">
            <Field label="Cliente">
              <ClienteSelect
                clientes={clientes}
                value={clienteId}
                onChange={(id) => {
                  setClienteId(id)
                  setResultado(null)
                }}
              />
            </Field>
            <Field label="Fecha">
              <span className="field">
                <input
                  type="date"
                  value={fecha}
                  onChange={(e) => {
                    setFecha(e.target.value)
                    setResultado(null)
                  }}
                />
              </span>
            </Field>
            <button
              type="button"
              onClick={() => {
                setTextoConfirmacion('')
                setError(null)
                setResultado(null)
                setConfirmando(true)
              }}
              disabled={clienteId === '' || !fecha}
              className="btn-danger"
            >
              <Trash2 size={15} />
              Eliminar conversaciones
            </button>
          </div>
          {resultado && (
            <div className="flex items-start gap-2 px-3.5 py-2.5 rounded-[10px] bg-ok-bg text-ok-fg text-[12.5px] font-medium animate-estia-fade">
              <Check size={15} strokeWidth={2.5} className="shrink-0 mt-px" />
              <span>
                Se eliminaron {formatNumber(resultado.conversaciones)} conversación(es) y {formatNumber(resultado.mensajes)} mensaje(s)
                de {resultado.cliente} del {formatLongDate(parseLocalDate(resultado.fecha))}. Ya puedes volver a subir el archivo
                de esa fecha.
              </span>
            </div>
          )}
        </div>
      </Card>

      <Modal open={confirmando} onClose={() => !eliminando && setConfirmando(false)}>
        <div className="flex flex-col gap-3.5">
          <span className="w-11 h-11 rounded-xl bg-bad-bg text-bad-fg flex items-center justify-center">
            <AlertTriangle size={20} />
          </span>
          <div>
            <h3 className="m-0 text-base font-bold text-ink">
              ¿Eliminar conversaciones del {fecha ? formatLongDate(parseLocalDate(fecha)) : ''}?
            </h3>
            <p className="mt-1.5 mb-0 text-[13px] leading-[1.6] text-ink-2">
              Se borrarán todas las conversaciones de <strong className="text-ink">{nombreCliente}</strong> en esa fecha. Escribe el
              nombre del cliente para confirmar.
            </p>
          </div>
          <input
            value={textoConfirmacion}
            onChange={(e) => setTextoConfirmacion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleConfirmar()}
            placeholder={nombreCliente}
            autoFocus
            className="h-10 px-3 rounded-[10px] border border-line bg-bg font-mono text-[13px] text-ink outline-0 focus:border-accent"
          />
          {error && <p className="m-0 text-[13px] text-bad-fg">{error}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setConfirmando(false)} disabled={eliminando} className="btn-secondary">
              Cancelar
            </button>
            <button type="button" onClick={handleConfirmar} disabled={!confirmado || eliminando} className="btn-danger h-[38px]">
              {eliminando ? 'Eliminando…' : 'Eliminar definitivamente'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
