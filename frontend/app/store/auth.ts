import { create } from 'zustand'
import { User } from '@/types'

interface AuthStore {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (user: User, token: string) => void
  logout: () => void
  setUser: (user: User) => void
  setToken: (token: string | null) => void
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  token: null, // Inicializar como null para SSR
  isLoading: false,

  login: (user, token) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', token)
    }
    set({ user, token, isLoading: false })
  },

  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token')
    }
    set({ user: null, token: null })
  },

  setUser: (user) => set({ user }),
  setToken: (token) => set({ token }),
}))

