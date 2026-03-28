'use client'

import { Suspense, useEffect } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useRouter, useSearchParams } from 'next/navigation'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import { DashboardWidgetsGrid } from '@/components/DashboardWidgetsGrid'

function DashboardPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, isAuthenticated, logout } = useAuth()

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login')
    }
  }, [isAuthenticated, router])

  useEffect(() => {
    if (searchParams.get('organize') === '1') {
      router.replace('/dashboard/widgets?organize=1', { scroll: false })
    }
  }, [searchParams, router])

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className="box-border min-h-screen bg-gray-50 dark:bg-slate-900 p-[30px]">
      <header className="border-b border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="flex w-full flex-wrap items-center justify-between gap-4 py-4">
          <div className="min-w-0">
            <AppBreadcrumb
              items={[{ label: 'Dashboard' }]}
              currentClassName="text-2xl font-bold text-gray-900 dark:text-white"
            />
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600 dark:text-gray-300">Hola, {user?.name}</span>
            <button
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

      <main className="w-full min-w-0 pt-[30px]">
        <DashboardWidgetsGrid />
      </main>
    </div>
  )
}

function DashboardPageFallback() {
  return (
    <div className="box-border min-h-screen bg-gray-50 p-[30px] dark:bg-slate-900">
      <p className="text-sm text-gray-500 dark:text-gray-400">Cargando dashboard…</p>
    </div>
  )
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<DashboardPageFallback />}>
      <DashboardPageInner />
    </Suspense>
  )
}
