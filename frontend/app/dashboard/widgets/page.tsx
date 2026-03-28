'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import { DashboardWidgetsGrid } from '@/components/DashboardWidgetsGrid'
import { SavedQueryWidgetPanel } from '@/components/SavedQueryWidgetPanel'

export default function WidgetShowcasePage() {
  const router = useRouter()
  const { user, isAuthenticated, logout } = useAuth()
  const [widgetsRefresh, setWidgetsRefresh] = useState(0)

  useEffect(() => {
    if (!isAuthenticated) router.push('/auth/login')
  }, [isAuthenticated, router])

  if (!isAuthenticated) return null

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      <header className="border-b border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="min-w-0">
            <AppBreadcrumb
              items={[
                { label: 'Dashboard', href: '/dashboard' },
                { label: 'Widget showcase' },
              ]}
            />
            <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
              📈 Widget showcase
            </h1>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              Añade widgets desde tus consultas guardadas y gestiona los que ya están en tu dashboard.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600 dark:text-gray-300">{user?.name}</span>
            <Link
              href="/dashboard"
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:text-gray-200 dark:hover:bg-slate-700"
            >
              Volver
            </Link>
            <button
              type="button"
              onClick={() => {
                logout()
                router.push('/auth/login')
              }}
              className="rounded-lg bg-red-50 px-3 py-1.5 text-sm text-red-600 transition hover:bg-red-100 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50"
            >
              Cerrar sesión
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-8 px-4 py-8 sm:px-6 lg:px-8">
        <SavedQueryWidgetPanel onWidgetAdded={() => setWidgetsRefresh((n) => n + 1)} />
        <DashboardWidgetsGrid refreshToken={widgetsRefresh} variant="showcase" />
      </main>
    </div>
  )
}
