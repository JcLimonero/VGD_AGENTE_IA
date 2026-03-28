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
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('auth_token')
      if (token) {
        apiClient
          .getMe()
          .then((user) => {
            login(mapApiUserToStore(user), token)
          })
          .catch(() => {
            localStorage.removeItem('auth_token')
            logout()
          })
      }
    }
  }, [login, logout])

  return null
}
