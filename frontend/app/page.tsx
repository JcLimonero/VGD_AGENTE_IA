'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'

export default function Home() {
  const router = useRouter()
  const { isAuthenticated } = useAuth()

  useEffect(() => {
    if (isAuthenticated) {
      router.replace('/dashboard')
      return
    }
    if (typeof window === 'undefined') return
    if (!localStorage.getItem('auth_token')) {
      router.replace('/auth/login')
    }
  }, [isAuthenticated, router])

  if (isAuthenticated) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 to-indigo-100 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600" />
          <p className="text-gray-600 dark:text-gray-300">Redirigiendo al dashboard...</p>
        </div>
      </main>
    )
  }

  // Token en localStorage: AuthHydrator valida en paralelo; evita mandar al login antes de getMe.
  if (typeof window !== 'undefined' && localStorage.getItem('auth_token')) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 to-indigo-100 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600" />
          <p className="text-gray-600 dark:text-gray-300">Validando sesión...</p>
        </div>
      </main>
    )
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 to-indigo-100 dark:from-slate-900 dark:to-slate-800">
      <div className="text-center">
        <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600" />
        <p className="text-gray-600 dark:text-gray-300">Redirigiendo al inicio de sesión...</p>
      </div>
    </main>
  )
}
