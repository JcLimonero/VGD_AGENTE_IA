import { useAuthStore } from '@/store/auth'
import { apiClient } from '@/services/api'
import type { User } from '../types'

function mapLoginUser(apiUser: {
  id: string | number
  email: string
  display_name?: string
  role?: string
}): User {
  return {
    id: String(apiUser.id),
    email: apiUser.email,
    name: apiUser.display_name ?? apiUser.email,
    role: apiUser.role === 'admin' ? 'admin' : 'user',
    created_at: new Date().toISOString(),
  }
}

export function useAuth() {
  const { user, token, login, logout, setUser } = useAuthStore()

  const handleLogin = async (email: string, password: string) => {
    try {
      console.log('useAuth - handleLogin called with:', email)
      const response = await apiClient.login(email, password)
      console.log('useAuth - API response:', response)
      const accessToken = response.access_token as string
      if (!accessToken) {
        console.error('useAuth - respuesta sin access_token')
        return false
      }
      login(mapLoginUser(response.user), accessToken)
      console.log('useAuth - login called, token should be set')
      return true
    } catch (error) {
      console.error('Login failed:', error)
      return false
    }
  }

  const handleLogout = async () => {
    try {
      await apiClient.logout()
      logout()
    } catch (error) {
      console.error('Logout failed:', error)
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

