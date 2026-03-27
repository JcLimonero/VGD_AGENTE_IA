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
  total_rows: number
  execution_time_ms: number
}

export interface QueryResultData {
  rows: Record<string, any>[]
  column_names: string[]
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

export interface AlertConfig {
  id: string
  name: string
  condition: string
  threshold: number
  query_id: string
  enabled: boolean
  created_by: string
}
