'use client'

import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export type DashboardStatsPayload = {
  saved_queries: number
  dashboard_widgets: number
  executions_today: number
  failed_recent: number
  users_total: number | null
}

type Props = {
  stats: DashboardStatsPayload | null
  loading: boolean
  error: string | null
  onRefresh: () => void
  compact?: boolean
}

/**
 * Resumen numérico para el panel de accesos rápidos (mismas métricas que exponía el dashboard).
 */
export function QuickAccessStats({ stats, loading, error, onRefresh, compact }: Props) {
  const pending = loading && stats === null

  const cell = (value: string) => <span className="tabular-nums">{value}</span>

  const rows: { label: string; hint?: string; display: ReactNode }[] = [
    {
      label: 'Widgets guardados',
      hint: stats != null ? `${stats.dashboard_widgets} en el dashboard` : undefined,
      display: pending
        ? cell('…')
        : stats
          ? cell(stats.saved_queries.toLocaleString('es-MX'))
          : cell('—'),
    },
    {
      label: 'Ejecuciones hoy',
      hint: 'Consultas guardadas ejecutadas hoy',
      display: pending ? cell('…') : stats ? cell(stats.executions_today.toLocaleString('es-MX')) : cell('—'),
    },
    {
      label: 'Alertas activas',
      hint: 'Fallos en los últimos 7 días',
      display: pending ? cell('…') : stats ? cell(stats.failed_recent.toLocaleString('es-MX')) : cell('—'),
    },
    {
      label: 'Usuarios',
      hint:
        stats?.users_total != null ? 'Total en plataforma (admin)' : 'Solo visible para administradores',
      display: pending
        ? cell('…')
        : stats?.users_total != null
          ? cell(stats.users_total.toLocaleString('es-MX'))
          : cell('—'),
    },
  ]

  return (
    <div
      className={cn(
        'rounded-xl border border-gray-200 bg-slate-50/90 p-3 dark:border-slate-600 dark:bg-slate-800/60',
        compact && 'p-2.5'
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          Estadísticas
        </p>
        <button
          type="button"
          onClick={() => void onRefresh()}
          disabled={loading}
          className="text-xs font-medium text-violet-600 hover:underline disabled:opacity-50 dark:text-violet-400"
        >
          {loading ? 'Actualizando…' : 'Actualizar'}
        </button>
      </div>
      {error ? <p className="mb-2 text-xs text-red-600 dark:text-red-400">{error}</p> : null}
      <div className="grid grid-cols-2 gap-2">
        {rows.map((row) => (
          <div
            key={row.label}
            className="rounded-lg bg-white/90 px-2 py-2 text-center dark:bg-slate-900/50"
          >
            <div
              className={cn(
                'font-bold text-violet-600 dark:text-violet-400',
                compact ? 'text-base' : 'text-lg'
              )}
            >
              {row.display}
            </div>
            <div className="mt-0.5 text-[10px] font-medium leading-tight text-gray-600 dark:text-gray-400">
              {row.label}
            </div>
            {row.hint ? (
              <div className="mt-0.5 text-[9px] leading-tight text-gray-400 dark:text-gray-500">{row.hint}</div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}
