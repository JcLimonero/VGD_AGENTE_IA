'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { useQuery } from '@/hooks/useQuery'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'

export default function QueriesPage() {
  const router = useRouter()
  const { isAuthenticated } = useAuth()
  const { queries, isLoading, error, fetchQueries } = useQuery()

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login')
      return
    }

    fetchQueries()
  }, [isAuthenticated, router])

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      {/* Header */}
      <header className="bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center gap-4">
          <div className="min-w-0 flex flex-col gap-1">
            <AppBreadcrumb
              items={[
                { label: 'Dashboard', href: '/dashboard' },
                { label: 'Mis queries' },
              ]}
            />
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">📊 Mis Queries</h1>
          </div>
          <Link
            href="/queries/new"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
          >
            + Nueva Query
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded-lg text-red-600 dark:text-red-200 text-sm">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="text-center py-12">
            <p className="text-gray-600 dark:text-gray-300">Cargando queries...</p>
          </div>
        ) : queries.length === 0 ? (
          <div className="text-center py-12 bg-white dark:bg-slate-800 rounded-lg">
            <p className="text-gray-600 dark:text-gray-300 mb-4">
              No tienes queries guardadas
            </p>
            <Link
              href="/queries/new"
              className="inline-block px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
            >
              Crear tu primera Query
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {queries.map((query) => (
              <div
                key={query.id}
                className="bg-white dark:bg-slate-800 rounded-lg shadow hover:shadow-lg transition p-6"
              >
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {query.name}
                  </h3>
                  {query.is_favorite && <span className="text-lg">⭐</span>}
                </div>

                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  {query.description}
                </p>

                <div className="mb-4">
                  <code className="text-xs bg-gray-100 dark:bg-slate-700 p-2 rounded block overflow-x-auto text-gray-800 dark:text-gray-200">
                    {query.sql
                      ? `${query.sql.slice(0, 50)}${query.sql.length > 50 ? '…' : ''}`
                      : '—'}
                  </code>
                </div>

                <div className="flex space-x-2">
                  <Link
                    href={`/queries/${query.id}`}
                    className="flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-center text-sm rounded transition"
                  >
                    Ejecutar
                  </Link>
                  <Link
                    href={`/queries/${query.id}/edit`}
                    className="px-3 py-2 bg-gray-200 dark:bg-slate-700 hover:bg-gray-300 dark:hover:bg-slate-600 text-gray-900 dark:text-white text-sm rounded transition text-center"
                  >
                    Editar
                  </Link>
                </div>

                <div className="mt-4 text-xs text-gray-500 dark:text-gray-400">
                  Creada: {new Date(query.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
