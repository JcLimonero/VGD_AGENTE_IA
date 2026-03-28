// Tipos principales de la aplicación

export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'user'
  created_at: string
}

export interface Query {
  id: string
  name: string
  description: string
  sql: string
  created_by: string
  created_at: string
  updated_at: string
  is_favorite: boolean
  tags: string[]
}

export interface QueryResult {
  query_id: string
  executed_at: string
  rows: Record<string, any>[]
  column_names: string[]
  /** Mapa alias SQL → etiqueta para UI (español), opcional según versión de API. */
  column_labels_es?: Record<string, string>
  total_rows: number
  execution_time_ms: number
}

export interface QueryResultData {
  rows: Record<string, any>[]
  column_names: string[]
  column_labels_es?: Record<string, string>
  total_rows: number
  generated_sql?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata?: {
    query_executed?: boolean
    query_id?: string
    context?: Record<string, any>
    results?: QueryResultData
    /** Pregunta del usuario que originó esta respuesta (para guardar en Mis Widgets). */
    user_question?: string
  }
}

export interface AgentResponse {
  message: string
  query_executed?: boolean
  query_id?: string | null
  results?: QueryResultData
  suggestions?: string[]
  confidence: number
  context?: Record<string, any>
}

export interface DashboardWidget {
  id: string
  type: 'chart' | 'table' | 'metric' | 'gauge'
  title: string
  query_id: string
  position: { x: number; y: number }
  size: { width: number; height: number }
  config: Record<string, any>
}

/** Fila de `dashboard_widgets` devuelta por la API. */
export interface ApiDashboardWidget {
  id: string
  dashboard_id: string
  saved_query_id: string
  pos_x: number
  pos_y: number
  width: number
  height: number
  display_order: number
  widget_config: Record<string, unknown>
  created_at: string
}

export interface AlertConfig {
  id: string
  name: string
  condition: string
  threshold: number
  query_id: string
  enabled: boolean
  created_by: string
}
