'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { DataResultTable } from '@/components/DataResultTable'
import { QueryResultsChart } from '@/components/QueryResultsChart'
import { apiClient } from '@/services/api'
import { downloadQueryResultsCsv } from '@/lib/csvExport'
import { queryResultFromExecuteApi } from '@/lib/savedQuery'
import { parseWidgetDisplayConfig, type WidgetView } from '@/lib/widgetDisplay'
import { cn } from '@/lib/utils'
import type { ApiDashboardWidget, QueryResultData } from '@/types'

const DASH_ALIAS = 'default'

type Props = {
  widget: ApiDashboardWidget
  onRemoved: () => void
}

export function DashboardWidgetCard({ widget, onRemoved }: Props) {
  const cfg = parseWidgetDisplayConfig(widget.widget_config)
  const [tab, setTab] = useState<WidgetView>(cfg.defaultView)
  const [data, setData] = useState<QueryResultData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [removing, setRemoving] = useState(false)
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const configSig = JSON.stringify(widget.widget_config)
  useEffect(() => {
    setTab(parseWidgetDisplayConfig(widget.widget_config).defaultView)
  }, [widget.id, configSig])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const raw = await apiClient.executeQuery(widget.saved_query_id)
      setData(queryResultFromExecuteApi(raw as Record<string, unknown>))
    } catch (e: unknown) {
      setData(null)
      setError(e instanceof Error ? e.message : 'Error al cargar datos')
    } finally {
      setLoading(false)
    }
  }, [widget.saved_query_id])

  useEffect(() => {
    void load()
  }, [load])

  const persistDefaultView = useCallback(
    (view: WidgetView) => {
      if (!cfg.showChart || !cfg.showTable) return
      if (persistTimer.current) clearTimeout(persistTimer.current)
      persistTimer.current = setTimeout(() => {
        void apiClient
          .patchDashboardWidget(DASH_ALIAS, widget.id, {
            widget_config: { default_view: view },
          })
          .catch(() => {
            /* silencioso: la vista local ya cambió */
          })
      }, 400)
    },
    [cfg.showChart, cfg.showTable, widget.id]
  )

  const handleTab = (next: WidgetView) => {
    setTab(next)
    persistDefaultView(next)
  }

  const handleRemove = async () => {
    if (!window.confirm('¿Quitar este widget del dashboard?')) return
    setRemoving(true)
    try {
      await apiClient.deleteDashboardWidget(DASH_ALIAS, widget.id)
      onRemoved()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'No se pudo quitar'
      window.alert(msg)
    } finally {
      setRemoving(false)
    }
  }

  const showTabs = cfg.showChart && cfg.showTable

  return (
    <article
      className="flex flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-slate-600 dark:bg-slate-800"
      data-widget-id={widget.id}
    >
      <header className="flex items-start justify-between gap-2 border-b border-gray-100 px-4 py-3 dark:border-slate-700">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-gray-900 dark:text-white">{cfg.title}</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400">Consulta #{widget.saved_query_id}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="rounded-lg px-2 py-1 text-xs font-medium text-violet-600 hover:bg-violet-50 disabled:opacity-50 dark:text-violet-400 dark:hover:bg-slate-700"
          >
            Actualizar
          </button>
          <button
            type="button"
            onClick={() => void handleRemove()}
            disabled={removing}
            className="rounded-lg px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:text-red-400 dark:hover:bg-red-950/40"
          >
            {removing ? '…' : 'Quitar'}
          </button>
        </div>
      </header>

      <div className="min-h-[200px] flex-1 p-4">
        {loading && <p className="text-sm text-gray-500 dark:text-gray-400">Cargando…</p>}
        {!loading && error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        {!loading && !error && data && (
          <>
            {showTabs && (
              <div
                className="mb-3 flex flex-wrap gap-1 rounded-lg border border-gray-200 bg-gray-100/80 p-1 dark:border-slate-600 dark:bg-slate-900/60"
                role="tablist"
                aria-label="Vista del widget"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === 'chart'}
                  onClick={() => handleTab('chart')}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium transition',
                    tab === 'chart'
                      ? 'bg-white text-violet-700 shadow-sm dark:bg-slate-800 dark:text-violet-300'
                      : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
                  )}
                >
                  Gráfica
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === 'table'}
                  onClick={() => handleTab('table')}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium transition',
                    tab === 'table'
                      ? 'bg-white text-violet-700 shadow-sm dark:bg-slate-800 dark:text-violet-300'
                      : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
                  )}
                >
                  Tabla
                </button>
              </div>
            )}

            {cfg.showChart && (tab === 'chart' || !showTabs) && data.column_names.length > 0 && (
              <div className="h-[260px] w-full min-w-0">
                <QueryResultsChart data={data} chartKind={cfg.chartKind} />
              </div>
            )}
            {cfg.showTable && (tab === 'table' || !showTabs) && data.column_names.length > 0 && (
              <div className="space-y-2">
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => downloadQueryResultsCsv(data)}
                    className="rounded-lg bg-violet-600 px-2 py-1 text-xs font-medium text-white hover:bg-violet-700"
                  >
                    CSV
                  </button>
                </div>
                <DataResultTable results={data} />
              </div>
            )}
            {data.column_names.length === 0 && (
              <p className="text-sm text-gray-500 dark:text-gray-400">Sin filas que mostrar.</p>
            )}
          </>
        )}
      </div>
    </article>
  )
}
