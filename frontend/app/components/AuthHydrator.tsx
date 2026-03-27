'use client'

import { useEffect } from 'react'
import { useAuthStore } from '@/store/auth'
import { apiClient } from '@/services/api'
import type { User } from '@/types'

function mapApiUserToStore(u: {
  id: string | number
  email: string
  display_name?: string
  role?: string
}): User {
  return {
    id: String(u.id),
    email: u.email,
    name: u.display_name ?? u.email,
    role: u.role === 'admin' ? 'admin' : 'user',
    created_at: new Date().toISOString(),
  }
}

export function AuthHydrator() {
  const { login, logout } = useAuthStore()

  useEffect(() => {
    // Solo ejecutar en el cliente
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('auth_token')
      if (token) {
        console.log('AuthHydrator - Token encontrado en localStorage, validando...')
        apiClient
          .getMe()
          .then((user) => {
            console.log('AuthHydrator - Token válido, usuario:', user)
            login(mapApiUserToStore(user), token)
          })
          .catch(() => {
            console.log('AuthHydrator - Token inválido, limpiando...')
            localStorage.removeItem('auth_token')
            logout()
          })
      } else {
        console.log('AuthHydrator - No hay token en localStorage')
      }
    }
  }, [login, logout])

  return null
}