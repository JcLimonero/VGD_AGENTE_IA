'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import { DashboardWidgetsGrid } from '@/components/DashboardWidgetsGrid'
import { SavedQueryWidgetPanel } from '@/components/SavedQueryWidgetPanel'

function ConfigureWidgetsPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, isAuthenticated, logout } = useAuth()
  const [widgetsRefresh, setWidgetsRefresh] = useState(0)
  const [organizeLayout, setOrganizeLayout] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) router.push('/auth/login')
  }, [isAuthenticated, router])

  useEffect(() => {
    if (searchParams.get('organize') === '1') {
      setOrganizeLayout(true)
      router.replace('/dashboard/widgets', { scroll: false })
    }
  }, [searchParams, router])

  if (!isAuthenticated) return null

  return (
    <div className="box-border min-h-screen bg-gray-50 dark:bg-slate-900 p-[30px]">
      <header className="border-b border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="flex w-full flex-wrap items-center justify-between gap-4 py-4">
          <div className="min-w-0">
            <AppBreadcrumb
              items={[
                { label: 'Dashboard', href: '/dashboard' },
                { label: 'Configurar widgets' },
              ]}
            />
            <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">Configurar widgets</h1>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              Añade widgets desde consultas guardadas, cambia vista y tipo de gráfica, y organiza la cuadrícula del
              tablero.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600 dark:text-gray-300">{user?.name}</span>
            <Link
              href="/dashboard"
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:text-gray-200 dark:hover:bg-slate-700"
            >
              Volver al tablero
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

      <main className="w-full min-w-0 space-y-8 pt-[30px]">
        <SavedQueryWidgetPanel onWidgetAdded={() => setWidgetsRefresh((n) => n + 1)} />
        <DashboardWidgetsGrid
          refreshToken={widgetsRefresh}
          variant="showcase"
          organizeOpen={organizeLayout}
          onOrganizeChange={setOrganizeLayout}
        />
      </main>
    </div>
  )
}

function ConfigureWidgetsFallback() {
  return (
    <div className="box-border min-h-screen bg-gray-50 p-[30px] dark:bg-slate-900">
      <p className="text-sm text-gray-500 dark:text-gray-400">Cargando…</p>
    </div>
  )
}

export default function ConfigureWidgetsPage() {
  return (
    <Suspense fallback={<ConfigureWidgetsFallback />}>
      <ConfigureWidgetsPageInner />
    </Suspense>
  )
}
