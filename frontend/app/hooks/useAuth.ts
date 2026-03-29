import { useAuthStore } from '@/store/auth'
import { apiClient } from '@/services/api'
import { getApiErrorMessage } from '@/lib/apiError'
import type { User } from '@/types'

export type LoginOutcome = { ok: true } | { ok: false; error: string }

function mapLoginUser(apiUser: {
  id: string | number
  email: string
  display_name?: string
  role?: string
  role_id?: number | null
  can_create_users?: boolean
  can_access_config?: boolean
}): User {
  return {
    id: String(apiUser.id),
    email: apiUser.email,
    name: apiUser.display_name ?? apiUser.email,
    role: apiUser.role ?? 'viewer',
    role_id: apiUser.role_id ?? null,
    can_create_users: apiUser.can_create_users ?? false,
    can_access_config: apiUser.can_access_config ?? false,
    created_at: new Date().toISOString(),
  }
}

export function useAuth() {
  const { user, token, login, logout, setUser } = useAuthStore()

  const handleLogin = async (email: string, password: string): Promise<LoginOutcome> => {
    try {
      const response = await apiClient.login(email, password)
      const accessToken = response.access_token as string
      if (!accessToken) {
        return { ok: false, error: 'Respuesta del servidor sin token de acceso' }
      }
      login(mapLoginUser(response.user), accessToken)
      return { ok: true }
    } catch (error: unknown) {
      return { ok: false, error: getApiErrorMessage(error, 'Error al iniciar sesión') }
    }
  }

  const handleLogout = async () => {
    try {
      await apiClient.logout()
      logout()
    } catch {
      logout()
    }
  }

  return {
    user,
    token,
    isAuthenticated: !!token,
    login: handleLogin,
    logout: handleLogout,
    setUser,
  }
}
