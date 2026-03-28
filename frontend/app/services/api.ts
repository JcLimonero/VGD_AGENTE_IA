import axios, { AxiosInstance, AxiosError } from 'axios'

/**
 * Si NEXT_PUBLIC_API_BASE_URL está definido → llamada directa al FastAPI.
 * Si no (p. ej. .env vacío) → en el navegador usamos /api/upstream (rewrite en next.config.js)
 * para no enviar /auth/* al propio Next (evita 404 en /auth/me).
 */
function resolveApiBaseURL(): string {
  const explicit = (process.env.NEXT_PUBLIC_API_BASE_URL || '').trim()
  if (explicit) {
    return explicit.replace(/\/+$/, '')
  }
  if (typeof window !== 'undefined') {
    return '/api/upstream'
  }
  const serverFallback =
    (process.env.API_UPSTREAM_URL || 'http://127.0.0.1:8501').trim()
  return serverFallback.replace(/\/+$/, '')
}

const API_BASE_URL = resolveApiBaseURL()

class APIClient {
  private client: AxiosInstance

  constructor(baseURL: string) {
    if (!baseURL) {
      throw new Error(
        'API base URL vacía: define NEXT_PUBLIC_API_BASE_URL o usa el proxy /api/upstream (next dev).'
      )
    }
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Interceptor para agregar token JWT si existe (solo en cliente)
    this.client.interceptors.request.use((config) => {
      if (typeof window !== 'undefined') {
        const token = localStorage.getItem('auth_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
      }
      return config
    })

    // Interceptor para manejo de errores
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401 && typeof window !== 'undefined') {
          // Token expirado - ir a login (solo en cliente)
          localStorage.removeItem('auth_token')
          window.location.href = '/auth/login'
        }
        return Promise.reject(error)
      }
    )
  }

  // Auth
  async login(email: string, password: string) {
    const response = await this.client.post('/auth/login', { email, password })
    return response.data
  }

  async logout() {
    await this.client.post('/auth/logout')
    localStorage.removeItem('auth_token')
  }

  /** Valida el JWT y devuelve el usuario actual (usa el token del interceptor). */
  async getMe() {
    const response = await this.client.get<{
      id: string
      email: string
      display_name: string
      role: string
    }>('/auth/me')
    return response.data
  }

  // Queries
  async getQueries() {
    const response = await this.client.get('/api/queries')
    return response.data
  }

  async getQuery(id: string) {
    const response = await this.client.get(`/api/queries/${id}`)
    return response.data
  }

  async createQuery(data: any) {
    const response = await this.client.post('/api/queries', data)
    return response.data
  }

  async updateQuery(id: string, data: any) {
    const response = await this.client.put(`/api/queries/${id}`, data)
    return response.data
  }

  async deleteQuery(id: string) {
    await this.client.delete(`/api/queries/${id}`)
  }

  async executeQuery(queryId: string) {
    const response = await this.client.post(`/api/queries/${queryId}/execute`)
    return response.data
  }

  // Chat / Agent
  async sendMessage(message: string, context?: any, signal?: AbortSignal) {
    const response = await this.client.post(
      '/api/agent/chat',
      {
        message,
        context,
      },
      { signal }
    )
    return response.data
  }

  // Dashboard
  async getDashboardStats() {
    const response = await this.client.get<{
      saved_queries: number
      dashboard_widgets: number
      executions_today: number
      failed_recent: number
      users_total: number | null
    }>('/api/dashboard/stats')
    return response.data
  }

  async getDashboard(dashboardId: string) {
    const response = await this.client.get(`/api/dashboards/${dashboardId}`)
    return response.data
  }

  async createDashboardWidget(
    dashboardId: string,
    body: {
      saved_query_id: string
      pos_x?: number
      pos_y?: number
      width?: number
      height?: number
      widget_config?: Record<string, unknown>
    }
  ) {
    const response = await this.client.post(`/api/dashboards/${dashboardId}/widgets`, body)
    return response.data
  }

  async patchDashboardWidget(
    dashboardId: string,
    widgetId: string,
    body: { widget_config: Record<string, unknown> }
  ) {
    const response = await this.client.patch(`/api/dashboards/${dashboardId}/widgets/${widgetId}`, body)
    return response.data
  }

  async deleteDashboardWidget(dashboardId: string, widgetId: string) {
    await this.client.delete(`/api/dashboards/${dashboardId}/widgets/${widgetId}`)
  }

  async updateDashboard(dashboardId: string, data: any) {
    const response = await this.client.put(`/api/dashboards/${dashboardId}`, data)
    return response.data
  }

  // Schema
  async getSchemaHint() {
    const response = await this.client.get('/api/schema')
    return response.data
  }

  // Health check
  async healthCheck() {
    try {
      const response = await this.client.get('/health')
      return response.status === 200
    } catch {
      return false
    }
  }
}

export const apiClient = new APIClient(API_BASE_URL)
