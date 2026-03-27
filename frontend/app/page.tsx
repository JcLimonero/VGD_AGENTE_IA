'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/hooks/useAuth'

export default function Home() {
  const router = useRouter()
  const { isAuthenticated, user } = useAuth()

  // Si está autenticado, redirigir al dashboard
  useEffect(() => {
    if (isAuthenticated) {
      router.push('/dashboard')
    }
  }, [isAuthenticated, router])

  // Si está autenticado, no mostrar nada (se redirige)
  if (isAuthenticated) {
    return (
      <main className="flex items-center justify-center min-h-screen bg-gradient-to-b from-blue-50 to-indigo-100 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-300">Redirigiendo al dashboard...</p>
        </div>
      </main>
    )
  }

  // Si no está autenticado, mostrar página de bienvenida con enlace al login
  return (
    <main className="flex items-center justify-center min-h-screen bg-gradient-to-b from-blue-50 to-indigo-100 dark:from-slate-900 dark:to-slate-800">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
          VGD Agente IA
        </h1>
        <p className="text-lg text-gray-600 dark:text-gray-300 mb-8">
          Dashboard inteligente para consultas DWH
        </p>
        <div className="flex gap-4 justify-center">
          <Link
            href="/auth/login"
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            Iniciar Sesión
          </Link>
          <Link
            href="/auth/register"
            className="px-6 py-3 bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition dark:bg-gray-600 dark:hover:bg-gray-700"
          >
            Registrarse
          </Link>
        </div>
      </div>
    </main>
  )
}
