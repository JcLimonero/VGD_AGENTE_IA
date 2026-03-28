'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { DataResultTable } from '@/components/DataResultTable'
import { QueryResultsChart } from '@/components/QueryResultsChart'
import { apiClient } from '@/services/api'
import { downloadQueryResultsCsv } from '@/lib/csvExport'
import { normalizeSavedQuery, queryResultFromExecuteApi } from '@/lib/savedQuery'
import {
  parseWidgetDisplayConfig,
  WIDGET_CHART_OPTIONS,
  type WidgetChartKind,
  type WidgetView,
} from '@/lib/widgetDisplay'
import { cn } from '@/lib/utils'
import type { Query, QueryResultData } from '@/types'

const DEFAULT_DASHBOARD_ID = 'default'

type ViewTab = 'chart' | 'table'

type Props = {
  onWidgetAdded?: () => void
}

export function SavedQueryWidgetPanel({ onWidgetAdded }: Props) {
  const [queries, setQueries] = useState<Query[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [selectedId, setSelectedId] = useState('')
  const [result, setResult] = useState<QueryResultData | null>(null)
  const [runLoading, setRunLoading] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  const [showChart, setShowChart] = useState(true)
  const [showTable, setShowTable] = useState(true)
  const [initialView, setInitialView] = useState<ViewTab>('chart')
  const [previewTab, setPreviewTab] = useState<WidgetView>('chart')
  const [chartKind, setChartKind] = useState<WidgetChartKind>('auto')

  const [addLoading, setAddLoading] = useState(false)
  const [addMsg, setAddMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  const resolvedDefaultView: WidgetView = useMemo(() => {
    if (showChart && !showTable) return 'chart'
    if (!showChart && showTable) return 'table'
    return initialView === 'table' ? 'table' : 'chart'
  }, [showChart, showTable, initialView])

  useEffect(() => {
    setPreviewTab(resolvedDefaultView)
  }, [resolvedDefaultView])

  const previewConfig = useMemo(
    () => ({
      title: queries.find((q) => q.id === selectedId)?.name ?? 'Vista previa',
      show_chart: showChart,
      show_table: showTable,
      default_view: resolvedDefaultView,
      chart_kind: chartKind,
    }),
    [queries, selectedId, showChart, showTable, resolvedDefaultView, chartKind]
  )

  const previewDisplay = parseWidgetDisplayConfig(previewConfig)
  const previewShowTabs = previewDisplay.showChart && previewDisplay.showTable

  const loadQueries = useCallback(async () => {
    setListLoading(true)
    setListError(null)
    try {
      const data = await apiClient.getQueries()
      const list = Array.isArray(data) ? data : []
      setQueries(list.map((item) => normalizeSavedQuery(item as Record<string, unknown>)))
    } catch (e: unknown) {
      setListError(e instanceof Error ? e.message : 'No se pudieron cargar los widgets')
    } finally {
      setListLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadQueries()
  }, [loadQueries])

  const selectedQuery = queries.find((q) => q.id === selectedId)

  const toggleShowChart = (v: boolean) => {
    if (!v && !showTable) return
    setShowChart(v)
  }

  const toggleShowTable = (v: boolean) => {
    if (!v && !showChart) return
    setShowTable(v)
  }

  const runSelected = async () => {
    if (!selectedId) return
    setRunLoading(true)
    setRunError(null)
    setResult(null)
    try {
      const raw = await apiClient.executeQuery(selectedId)
      setResult(queryResultFromExecuteApi(raw as Record<string, unknown>, selectedQuery?.sql))
    } catch (e: unknown) {
      setRunError(e instanceof Error ? e.message : 'Error al ejecutar')
    } finally {
      setRunLoading(false)
    }
  }

  const addWidget = async () => {
    if (!selectedId) return
    if (!showChart && !showTable) {
      setAddMsg({ type: 'err', text: 'Activa al menos gráfica o tabla.' })
      return
    }
    setAddLoading(true)
    setAddMsg(null)
    try {
      await apiClient.createDashboardWidget(DEFAULT_DASHBOARD_ID, {
        saved_query_id: selectedId,
        pos_x: 0,
        pos_y: 0,
        width: 6,
        height: 4,
        widget_config: {
          title: selectedQuery?.name ?? 'Widget',
          show_chart: showChart,
          show_table: showTable,
          default_view: resolvedDefaultView,
          chart_kind: chartKind,
        },
      })
      setAddMsg({ type: 'ok', text: 'Widget guardado en tu dashboard por defecto.' })
      onWidgetAdded?.()
    } catch (e: unknown) {
      let msg = 'Error al registrar el widget'
      if (e && typeof e === 'object' && 'response' in e) {
        const d = (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
        if (typeof d === 'string') msg = d
        else if (d != null) msg = JSON.stringify(d)
      } else if (e instanceof Error) {
        msg = e.message
      }
      setAddMsg({ type: 'err', text: msg })
    } finally {
      setAddLoading(false)
    }
  }

  return (
    <section className="rounded-xl border border-violet-200 bg-gradient-to-br from-violet-50/80 to-white p-6 shadow-sm dark:border-violet-900/40 dark:from-violet-950/40 dark:to-slate-800">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
        Widget con consulta almacenada
      </h2>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
        Elige qué mostrar (gráfica y/o tabla), la vista inicial y añade el widget. Podrás quitarlo o cambiar la vista desde
        la cuadrícula de abajo.
      </p>

      {listLoading ? (
        <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">Cargando widgets…</p>
      ) : listError ? (
        <p className="mt-4 text-sm text-red-600 dark:text-red-400">{listError}</p>
      ) : queries.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-gray-300 p-4 text-center dark:border-slate-600">
          <p className="text-sm text-gray-600 dark:text-gray-400">No hay widgets guardados.</p>
          <Link
            href="/queries/new"
            className="mt-2 inline-block text-sm font-medium text-violet-600 hover:underline dark:text-violet-400"
          >
            Crear un widget
          </Link>
        </div>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <label className="flex min-w-[200px] flex-1 flex-col gap-1 text-sm">
              <span className="font-medium text-gray-700 dark:text-gray-300">Widget guardado</span>
              <select
                value={selectedId}
                onChange={(e) => {
                  setSelectedId(e.target.value)
                  setResult(null)
                  setRunError(null)
                  setAddMsg(null)
                  setChartKind('auto')
                }}
                className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 dark:border-slate-600 dark:bg-slate-900 dark:text-white"
              >
                <option value="">— Seleccionar —</option>
                {queries.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={!selectedId || runLoading}
              onClick={() => void runSelected()}
              className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-violet-700 disabled:opacity-50"
            >
              {runLoading ? 'Ejecutando…' : 'Ejecutar y previsualizar'}
            </button>
            <button
              type="button"
              disabled={!selectedId || addLoading || (!showChart && !showTable)}
              onClick={() => void addWidget()}
              className="rounded-lg border border-violet-600 bg-white px-4 py-2 text-sm font-medium text-violet-700 transition hover:bg-violet-50 disabled:opacity-50 dark:border-violet-500 dark:bg-slate-800 dark:text-violet-300 dark:hover:bg-slate-700"
            >
              {addLoading ? 'Guardando…' : 'Añadir al dashboard'}
            </button>
          </div>

          {selectedId && (
            <fieldset className="mt-4 space-y-3 rounded-lg border border-gray-200 p-4 dark:border-slate-600">
              <legend className="px-1 text-sm font-medium text-gray-800 dark:text-gray-200">
                Qué muestra el widget
              </legend>
              <div className="flex flex-wrap gap-6">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    checked={showChart}
                    onChange={(e) => toggleShowChart(e.target.checked)}
                    className="rounded border-gray-300 text-violet-600 focus:ring-violet-500 dark:border-slate-600"
                  />
                  Gráfica
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    checked={showTable}
                    onChange={(e) => toggleShowTable(e.target.checked)}
                    className="rounded border-gray-300 text-violet-600 focus:ring-violet-500 dark:border-slate-600"
                  />
                  Tabla
                </label>
              </div>
              {showChart && (
                <label className="flex max-w-md flex-col gap-1 text-sm text-gray-700 dark:text-gray-300">
                  <span className="font-medium">Tipo de gráfica</span>
                  <select
                    value={chartKind}
                    onChange={(e) => setChartKind(e.target.value as WidgetChartKind)}
                    className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 dark:border-slate-600 dark:bg-slate-900 dark:text-white"
                  >
                    {WIDGET_CHART_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <span className="text-xs font-normal text-gray-500 dark:text-gray-400">
                    La circular usa la primera métrica numérica y la categoría del eje X.
                  </span>
                </label>
              )}
              {showChart && showTable && (
                <div className="text-sm text-gray-700 dark:text-gray-300">
                  <span className="mr-3 font-medium">Vista inicial:</span>
                  <label className="mr-4 inline-flex cursor-pointer items-center gap-1.5">
                    <input
                      type="radio"
                      name="initialView"
                      checked={initialView === 'chart'}
                      onChange={() => setInitialView('chart')}
                      className="text-violet-600 focus:ring-violet-500"
                    />
                    Gráfica
                  </label>
                  <label className="inline-flex cursor-pointer items-center gap-1.5">
                    <input
                      type="radio"
                      name="initialView"
                      checked={initialView === 'table'}
                      onChange={() => setInitialView('table')}
                      className="text-violet-600 focus:ring-violet-500"
                    />
                    Tabla
                  </label>
                </div>
              )}
            </fieldset>
          )}

          {runError && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{runError}</p>}
          {addMsg && (
            <p
              className={cn(
                'mt-3 text-sm',
                addMsg.type === 'ok'
                  ? 'text-emerald-700 dark:text-emerald-400'
                  : 'text-red-600 dark:text-red-400'
              )}
            >
              {addMsg.text}
            </p>
          )}

          {result && result.column_names.length > 0 && (
            <div className="mt-6 rounded-lg border border-gray-200 bg-white p-4 dark:border-slate-600 dark:bg-slate-900/40">
              <p className="mb-3 text-xs font-medium text-gray-500 dark:text-gray-400">Vista previa (lo que verás en el widget)</p>
              {previewShowTabs && (
                <div
                  className="mb-3 flex flex-wrap gap-1 rounded-lg border border-gray-200 bg-gray-100/80 p-1 dark:border-slate-600 dark:bg-slate-900/60"
                  role="tablist"
                  aria-label="Vista previa"
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={previewTab === 'chart'}
                    onClick={() => setPreviewTab('chart')}
                    className={cn(
                      'rounded-md px-3 py-1.5 text-sm font-medium transition',
                      previewTab === 'chart'
                        ? 'bg-white text-violet-700 shadow-sm dark:bg-slate-800 dark:text-violet-300'
                        : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
                    )}
                  >
                    Gráfica
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={previewTab === 'table'}
                    onClick={() => setPreviewTab('table')}
                    className={cn(
                      'rounded-md px-3 py-1.5 text-sm font-medium transition',
                      previewTab === 'table'
                        ? 'bg-white text-violet-700 shadow-sm dark:bg-slate-800 dark:text-violet-300'
                        : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
                    )}
                  >
                    Tabla
                  </button>
                </div>
              )}
              {previewDisplay.showChart && (previewTab === 'chart' || !previewShowTabs) && (
                <div className="rounded-lg border border-gray-100 p-2 dark:border-slate-700">
                  <QueryResultsChart data={result} chartKind={chartKind} />
                </div>
              )}
              {previewDisplay.showTable && (previewTab === 'table' || !previewShowTabs) && (
                <div className="space-y-3">
                  {previewDisplay.showChart && previewShowTabs && previewTab === 'table' && (
                    <label className="flex flex-wrap items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                      <span className="font-medium">Tipo de gráfica</span>
                      <select
                        value={chartKind}
                        onChange={(e) => setChartKind(e.target.value as WidgetChartKind)}
                        className="max-w-xs rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-gray-900 dark:border-slate-600 dark:bg-slate-900 dark:text-white"
                      >
                        {WIDGET_CHART_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                      <span className="w-full text-xs font-normal text-gray-500 dark:text-gray-400 sm:w-auto">
                        (visible al cambiar a Gráfica)
                      </span>
                    </label>
                  )}
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => downloadQueryResultsCsv(result)}
                      className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-700"
                    >
                      Descargar CSV
                    </button>
                  </div>
                  <DataResultTable results={result} />
                </div>
              )}
            </div>
          )}

          {result && result.column_names.length === 0 && result.total_rows === 0 && (
            <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">La consulta no devolvió filas.</p>
          )}
        </>
      )}
    </section>
  )
}
