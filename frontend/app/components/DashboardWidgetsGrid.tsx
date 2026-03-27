'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { DashboardWidgetCard } from '@/components/DashboardWidgetCard'
import { apiClient } from '@/services/api'
import type { ApiDashboardWidget } from '@/types'

type Props = {
  /** Incrementar para volver a cargar el dashboard (p. ej. tras añadir un widget). */
  refreshToken?: number
  /** En la página showcase: oculta el enlace "Gestionar widgets" y acorta textos. */
  variant?: 'page' | 'showcase'
}

export function DashboardWidgetsGrid({ refreshToken = 0, variant = 'page' }: Props) {
  const [widgets, setWidgets] = useState<ApiDashboardWidget[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const dash = await apiClient.getDashboard('default')
      const raw = dash as { widgets?: unknown }
      const list = Array.isArray(raw.widgets) ? raw.widgets : []
      setWidgets(list as ApiDashboardWidget[])
    } catch (e: unknown) {
      setWidgets([])
      setError(e instanceof Error ? e.message : 'No se pudo cargar el dashboard')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load, refreshToken])

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Widgets en tu dashboard</h2>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            Vista fijada según lo que configuraste al añadirlos; puedes cambiar gráfica/tabla y se guarda. Usa Quitar para
            eliminarlos del tablero.
          </p>
        </div>
        {variant === 'page' && (
          <Link
            href="/dashboard/widgets"
            className="text-sm font-medium text-violet-600 hover:underline dark:text-violet-400"
          >
            Gestionar widgets
          </Link>
        )}
      </div>

      {loading && <p className="text-sm text-gray-500 dark:text-gray-400">Cargando widgets…</p>}
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {!loading && !error && widgets.length === 0 && (
        <p className="rounded-lg border border-dashed border-gray-300 py-8 text-center text-sm text-gray-600 dark:border-slate-600 dark:text-gray-400">
          {variant === 'showcase' ? (
            <>Aún no hay widgets. Usa el panel superior para añadir uno.</>
          ) : (
            <>
              Aún no hay widgets en tu dashboard por defecto. Añade uno desde{' '}
              <Link href="/dashboard/widgets" className="font-medium text-violet-600 underline dark:text-violet-400">
                Widget showcase
              </Link>
              .
            </>
          )}
        </p>
      )}
      {!loading && !error && widgets.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {widgets.map((w) => (
            <DashboardWidgetCard key={w.id} widget={w} onRemoved={() => void load()} />
          ))}
        </div>
      )}
    </section>
  )
}
