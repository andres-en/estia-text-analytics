export interface ConversationSummary {
  session_id: string
  customer_phone: string | null
  customer_name: string | null
  started_at: string
  ended_at: string
  message_count: number
  session_pattern: string
  iniciada_por: 'CUSTOMER' | 'BOT' | 'SYSTEM'
  contiene_array: boolean
  categoria: string | null
  categoria_label: string | null
  subcategoria?: string | null
  subcategoria_label?: string | null
}

export interface ConversationsResponse {
  items: ConversationSummary[]
  total: number
  page: number
  page_size: number
}

export interface TranscriptMessage {
  sequence_number: number
  timestamp: string
  sender: 'CUSTOMER' | 'BOT' | 'SYSTEM'
  sender_label: string
  message_type: string
  message: string
}

// Indicadores resueltos de la campaña de esta conversación (propios o los 6 de
// Acme por defecto — ver `analysis/schema.py`), ya con su etiqueta lista
// para mostrar.
export interface IndicadorResuelto {
  id: string
  label: string
  valor: boolean
}

export interface ConversationTranscript {
  session_id: string
  customer_phone: string | null
  customer_name: string | null
  started_at: string
  ended_at: string
  conn_id_count: number
  messages: TranscriptMessage[]
  iniciada_por: 'CUSTOMER' | 'BOT' | 'SYSTEM'
  contiene_array: boolean
  categoria: string | null
  categoria_label: string | null
  subcategoria?: string | null
  subcategoria_label?: string | null
  metodo: string | null
  justificacion: string | null
  indicadores: IndicadorResuelto[]
}

export interface RowError {
  source_row: number
  error_type: string
  error_message: string
}

export interface ImportReport {
  file_name: string
  status: string
  rows_received: number
  rows_processed: number
  rows_error: number
  conversations_created: number
  conversations_updated: number
  messages_created: number
  messages_skipped_duplicate: number
  customer_messages: number
  bot_messages: number
  system_messages: number
  warnings: string[]
  row_errors: RowError[]
  analysis_started: boolean
}

export interface AnalysisStatus {
  state: 'idle' | 'running' | 'done' | 'error'
  total: number
  evaluadas: number
  resueltas_por_regla: number
  resueltas_por_ia: number
  pendientes_de_ia: number
  errores: number
  usa_ia: boolean
  started_at: string | null
  finished_at: string | null
  error_message: string | null
}

export interface DashboardData {
  category_counts: Record<string, number>
  subcategory_counts: Record<string, number>
  category_counts_trend: {
    current: Record<string, number>
    previous: Record<string, number>
  }
  method_counts: Record<string, number>
  business_indicators: Record<string, number>
  business_indicators_trend: {
    current: Record<string, number>
    previous: Record<string, number>
  }
  daily_trend: { fecha: string; categoria: string; cantidad: number }[]
}

export interface ConversationFilters {
  q?: string
  categoria?: string[]
  desde?: string
  hasta?: string
  flag?: string
  iniciada_por?: 'CUSTOMER' | 'BOT' | 'SYSTEM'
  contiene_array?: boolean
  page?: number
  page_size?: number
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init)
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ error: resp.statusText }))
    throw new ApiError(body.error ?? `Error ${resp.status}`, resp.status)
  }
  return resp.json() as Promise<T>
}

function apiFetchJson<T>(path: string, method: string, body?: unknown): Promise<T> {
  return apiFetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function fetchConversations(filters: ConversationFilters): Promise<ConversationsResponse> {
  const params = new URLSearchParams()
  if (filters.q) params.set('q', filters.q)
  if (filters.desde) params.set('desde', filters.desde)
  if (filters.hasta) params.set('hasta', filters.hasta)
  if (filters.flag) params.set('flag', filters.flag)
  if (filters.iniciada_por) params.set('iniciada_por', filters.iniciada_por)
  if (filters.contiene_array !== undefined) params.set('contiene_array', String(filters.contiene_array))
  if (filters.page) params.set('page', String(filters.page))
  if (filters.page_size) params.set('page_size', String(filters.page_size))
  for (const c of filters.categoria ?? []) params.append('categoria', c)
  return apiFetch(`/api/conversations?${params.toString()}`)
}

function _exportParams(filters: ConversationFilters): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.q) params.set('q', filters.q)
  if (filters.desde) params.set('desde', filters.desde)
  if (filters.hasta) params.set('hasta', filters.hasta)
  if (filters.flag) params.set('flag', filters.flag)
  if (filters.iniciada_por) params.set('iniciada_por', filters.iniciada_por)
  if (filters.contiene_array !== undefined) params.set('contiene_array', String(filters.contiene_array))
  for (const c of filters.categoria ?? []) params.append('categoria', c)
  return params
}

// Descarga el reporte de conversaciones en Excel, respetando los mismos filtros
// que la tabla (sin paginar: exporta todo lo que cumple el filtro). El navegador
// no puede "descargar" la respuesta de un fetch por sí solo: hay que pedirla como
// blob y simular el click en un <a> temporal con esos bytes.
export async function exportConversations(filters: ConversationFilters): Promise<void> {
  const params = _exportParams(filters)
  const resp = await fetch(`/api/conversations/export?${params.toString()}`)
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ error: resp.statusText }))
    throw new ApiError(body.error ?? `Error ${resp.status}`, resp.status)
  }
  const blob = await resp.blob()
  const disposition = resp.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^";]+)"?/.exec(disposition)
  const filename = match?.[1] ?? 'conversaciones.xlsx'

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function fetchConversationDetail(sessionId: string): Promise<ConversationTranscript> {
  return apiFetch(`/api/conversations/${encodeURIComponent(sessionId)}`)
}

export interface DashboardFilters {
  desde?: string
  hasta?: string
}

// Catálogo de categorías del cliente activo — unión de las categorías de
// todas sus campañas (propias o las de Acme por defecto), más 'SIN_ANALIZAR'.
// Reemplaza las constantes estáticas que antes vivían en frontend/src/lib/categories.ts.
export interface Categoria {
  id: string
  label: string
  color: string
  orden: number
  // La categoría existe (se puede filtrar en la tabla) pero no se grafica en el dashboard.
  ocultar_en_dashboard?: boolean
}

export function fetchCategorias(): Promise<Categoria[]> {
  return apiFetch('/api/categorias')
}

// Segundo nivel de clasificación opcional (ej. "Motivo del interés" en Acme):
// `items` viene vacío si ninguna campaña del cliente define subcategorías.
export interface Subcategorias {
  etiqueta: string
  items: Categoria[]
}

export function fetchSubcategorias(): Promise<Subcategorias> {
  return apiFetch('/api/subcategorias')
}

export function fetchDashboard(filters: DashboardFilters = {}): Promise<DashboardData> {
  const params = new URLSearchParams()
  if (filters.desde) params.set('desde', filters.desde)
  if (filters.hasta) params.set('hasta', filters.hasta)
  const qs = params.toString()
  return apiFetch(`/api/dashboard${qs ? `?${qs}` : ''}`)
}

export function uploadFile(file: File, campanaId: number): Promise<ImportReport> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('campana_id', String(campanaId))
  return apiFetch('/api/upload', { method: 'POST', body: formData })
}

export function fetchAnalysisStatus(): Promise<AnalysisStatus> {
  return apiFetch('/api/analyze/status')
}

// --- Campañas (selector de subida) -----------------------------------------

// Categorías/indicadores/árbol de decisión propios de una campaña, generados
// por IA a partir de una descripción en texto libre (o escritos a mano) — ver
// `analysis/schema.py`. `null`/ausente = la campaña usa el motor fijo de
// Acme (5 categorías hardcodeadas), como hasta ahora.
export interface CategoriaDef {
  id: string
  label: string
  color: string
  orden: number
}

export interface CondicionIndicador {
  tipo: 'regex_bot' | 'regex_customer' | 'boton'
  patron: string
}

export interface IndicadorDef {
  id: string
  label: string
  tipo: 'regla' | 'ia'
  condiciones: CondicionIndicador[]
  descripcion_ia: string | null
}

export interface ReglaDecision {
  condicion: Record<string, boolean>
  categoria: string
}

export interface EsquemaClasificacion {
  categorias: CategoriaDef[]
  indicadores: IndicadorDef[]
  arbol_decision: ReglaDecision[]
  categoria_sin_respuesta: string
  contexto_negocio: string
}

export interface CampanaConfiguracion {
  boton_cupo: string
  boton_asesor: string
  boton_no_interesado: string
  rx_interes_confirmado: string
  rx_encuesta_rechazo: string
  rx_bot_no_resolvio: string
  rx_autorespondedor: string
  cortesias: string[]
  esquema_clasificacion: EsquemaClasificacion | null
}

export interface Campaign {
  id_campana: number
  nombre_campana: string
  estado: string
  configuracion?: CampanaConfiguracion
}

export function fetchCampaigns(): Promise<Campaign[]> {
  return apiFetch('/api/campaigns')
}

// --- Autenticación -----------------------------------------------------------

export interface ClienteRef {
  id_cliente: number
  nombre_cliente: string
}

export interface CurrentUser {
  id_usuario: number
  nombre_usuario: string
  email: string
  rol: string
  permisos: string[]
  es_super_admin: boolean
  clientes: ClienteRef[]
  cliente_activo: ClienteRef | null
}

export function fetchMe(): Promise<CurrentUser> {
  return apiFetch('/api/auth/me')
}

export function logout(): Promise<{ ok: boolean }> {
  return apiFetchJson('/api/auth/logout', 'POST')
}

export function setClienteActivo(cliente_id: number | null): Promise<{ ok: boolean }> {
  return apiFetchJson('/api/auth/session/cliente-activo', 'POST', { cliente_id })
}

export const GOOGLE_LOGIN_URL = '/api/auth/google/login'

// --- Administración (super admin / admin) -----------------------------------

export interface Cliente {
  id_cliente: number
  nombre_cliente: string
  db_name: string
  fecha_registro: string | null
  activo: boolean
}

export function fetchClientes(): Promise<Cliente[]> {
  return apiFetch('/api/admin/clientes')
}

export function createCliente(nombre_cliente: string): Promise<Cliente> {
  return apiFetchJson('/api/admin/clientes', 'POST', { nombre_cliente })
}

export function updateCliente(id_cliente: number, cambios: { nombre_cliente?: string; activo?: boolean }): Promise<Cliente> {
  return apiFetchJson(`/api/admin/clientes/${id_cliente}`, 'PATCH', cambios)
}

export interface Rol {
  id_rol: number
  nombre_rol: string
}

export function fetchRoles(): Promise<Rol[]> {
  return apiFetch('/api/admin/roles')
}

export interface Usuario {
  id_usuario: number
  nombre_usuario: string
  email: string
  rol: Rol
  clientes: ClienteRef[]
  fecha_creacion: string | null
  activo: boolean
}

export function fetchUsuarios(): Promise<Usuario[]> {
  return apiFetch('/api/admin/usuarios')
}

export function createUsuario(datos: {
  nombre_usuario: string
  email: string
  id_rol?: number
  id_clientes: number[]
}): Promise<Usuario> {
  return apiFetchJson('/api/admin/usuarios', 'POST', datos)
}

export function updateUsuario(
  id_usuario: number,
  cambios: { nombre_usuario?: string; id_rol?: number; id_clientes?: number[]; activo?: boolean },
): Promise<Usuario> {
  return apiFetchJson(`/api/admin/usuarios/${id_usuario}`, 'PATCH', cambios)
}

export function fetchClienteCampanas(cliente_id: number): Promise<Campaign[]> {
  return apiFetch(`/api/admin/campanas?cliente_id=${cliente_id}`)
}

export function createClienteCampana(
  cliente_id: number,
  nombre_campana: string,
  configuracion?: Partial<CampanaConfiguracion>,
): Promise<Campaign> {
  return apiFetchJson('/api/admin/campanas', 'POST', { cliente_id, nombre_campana, configuracion })
}

export function updateClienteCampana(
  cliente_id: number,
  id_campana: number,
  cambios: { nombre_campana?: string; estado?: string; configuracion?: Partial<CampanaConfiguracion> | null },
): Promise<Campaign> {
  return apiFetchJson(`/api/admin/campanas/${id_campana}`, 'PATCH', { cliente_id, ...cambios })
}

// No guarda nada — devuelve un esquema propuesto para revisar/editar en el
// formulario y guardarlo después con create/updateClienteCampana.
export function generarEsquemaCampana(
  cliente_id: number,
  prompt: string,
): Promise<{ esquema_clasificacion: EsquemaClasificacion }> {
  return apiFetchJson('/api/admin/campanas/generar-esquema', 'POST', { cliente_id, prompt })
}

// --- Uso de IA (tokens/costo) -------------------------------------------------

export interface UsoIAFila {
  modelo: string
  tipo: 'clasificacion' | 'generar_esquema'
  llamadas: number
  tokens_prompt: number
  tokens_completion: number
  costo_usd: number | null
}

export interface UsoIAMes {
  mes: string // "AAAA-MM"
  modelo: string
  llamadas: number
  tokens_prompt: number
  tokens_completion: number
  costo_usd: number | null
}

export interface UsoIA {
  filas: UsoIAFila[]
  por_mes: UsoIAMes[]
  tokens_totales: number
  costo_total_usd: number | null
}

export function fetchUsoIA(cliente_id: number, filtros: { desde?: string; hasta?: string } = {}): Promise<UsoIA> {
  const params = new URLSearchParams({ cliente_id: String(cliente_id) })
  if (filtros.desde) params.set('desde', filtros.desde)
  if (filtros.hasta) params.set('hasta', filtros.hasta)
  return apiFetch(`/api/admin/uso-ia?${params.toString()}`)
}

// --- Mantenimiento (borrado de conversaciones por fecha) ---------------------

export interface EliminarConversacionesResultado {
  conversaciones_eliminadas: number
  mensajes_eliminados: number
}

// Destructivo: borra las conversaciones/mensajes/análisis de esa fecha (el uso
// de IA se conserva). Pensado para poder reprocesar una carga con datos malos.
export function eliminarConversacionesPorFecha(cliente_id: number, fecha: string): Promise<EliminarConversacionesResultado> {
  return apiFetch('/api/admin/conversaciones', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cliente_id, fecha }),
  })
}
