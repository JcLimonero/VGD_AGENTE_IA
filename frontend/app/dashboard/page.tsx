'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { useAuth } from '@/hooks/useAuth'
import { useRouter } from 'next/navigation'

export default function DashboardPage() {
  const router = useRouter()
  const { user, isAuthenticated } = useAuth()

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login')
    }
  }, [isAuthenticated, router])

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      {/* Header */}
      <header className="bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
          <div className="text-sm text-gray-600 dark:text-gray-300">
            Hola, {user?.name}
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Card: Queries */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              📊 Queries
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-4">
              Gestiona tus consultas SQL guardadas
            </p>
            <Link
              href="/queries"
              className="inline-block px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
            >
              Ver Queries
            </Link>
          </div>

          {/* Card: Chat */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              💬 Chat con Agente
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-4">
              Consulta el DWH usando lenguaje natural
            </p>
            <Link
              href="/chat"
              className="inline-block px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition"
            >
              Ir al Chat
            </Link>
          </div>

          {/* Card: Widgets */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              📈 Widget Showcase
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-4">
              Componentes y gráficos disponibles
            </p>
            <button className="inline-block px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition">
              Ver Componentes
            </button>
          </div>

          {/* Card: Configuración */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              ⚙️ Configuración
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-4">
              Parámetros y preferencias
            </p>
            <Link
              href="/settings"
              className="inline-block px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition"
            >
              Configurar
            </Link>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-12 bg-white dark:bg-slate-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
            📊 Estadísticas
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { label: 'Queries Guardadas', value: '0' },
              { label: 'Ejecuciones Hoy', value: '0' },
              { label: 'Alertas Activas', value: '0' },
              { label: 'Usuarios', value: '1' },
            ].map((stat, i) => (
              <div key={i} className="text-center p-4 bg-gray-50 dark:bg-slate-700 rounded-lg">
                <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                  {stat.value}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}
