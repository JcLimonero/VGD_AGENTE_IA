'use client'

import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useCallback, useEffect, useRef, useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { DataResultTable } from '@/components/DataResultTable'
import { QueryResultsChart } from '@/components/QueryResultsChart'
import {
  isSingleRowQueryResult,
  singleRowValueTabLabel,
  SingleQueryResultValuePanel,
} from '@/components/SingleQueryResultValue'
import { apiClient } from '@/services/api'
import { downloadQueryResultsCsv } from '@/lib/csvExport'
import { queryResultFromExecuteApi } from '@/lib/savedQuery'
import {
  parseChartKind,
  parseWidgetDisplayConfig,
  WIDGET_CHART_OPTIONS,
  type WidgetChartKind,
  type WidgetView,
} from '@/lib/widgetDisplay'
import { parseWidgetTableAccent, TABLE_ACCENT_OPTIONS, type TableAccentId } from '@/lib/tableAccent'
import { buildQueryChartSpec, effectiveCartesianKind } from '@/lib/chartSpec'
import {
  chartHexForAccent,
  parseHexColorMap,
  seriesStrokeFills,
} from '@/lib/chartColors'
import { columnHeaderLabel } from '@/lib/columnLabels'
import { useTableAccentId } from '@/hooks/useTableAccent'
import { cn } from '@/lib/utils'
import { getApiErrorMessage } from '@/lib/apiError'
import type { ApiDashboardWidget, QueryResultData } from '@/types'

const DASH_ALIAS = 'default'

type Props = {
  widget: ApiDashboardWidget
  onRemoved: () => void
  /** p. ej. `h-full min-h-0` dentro de una celda de cuadrícula. */
  className?: string
  /** Actualizar / Quitar: en el tablero solo en vista lectura; en “Configurar widgets” siempre o con “Organizar cuadrícula”. */
  showWidgetActions: boolean
}

export function DashboardWidgetCard({ widget, onRemoved, className, showWidgetActions }: Props) {
  const globalTableAccent = useTableAccentId()
  const cfg = parseWidgetDisplayConfig(widget.widget_config)
  const [tab, setTab] = useState<WidgetView>(cfg.defaultView)
  const [data, setData] = useState<QueryResultData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [removing, setRemoving] = useState(false)
  const [chartKind, setChartKind] = useState<WidgetChartKind>(() =>
    parseChartKind(widget.widget_config as Record<string, unknown>)
  )
  const persistViewTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const persistChartTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const persistTableAccentTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const persistSeriesColorsTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const persistCategoryColorsTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [widgetTableAccent, setWidgetTableAccent] = useState<TableAccentId | undefined>(() =>
    parseWidgetTableAccent(widget.widget_config as Record<string, unknown>)
  )
  const [chartSeriesColors, setChartSeriesColors] = useState<Record<string, string>>({})
  const [chartCategoryColors, setChartCategoryColors] = useState<Record<string, string>>({})

  const configSig = JSON.stringify(widget.widget_config)
  useEffect(() => {
    const wc = widget.widget_config as Record<string, unknown>
    setTab(parseWidgetDisplayConfig(widget.widget_config).defaultView)
    setChartKind(parseChartKind(wc))
    setWidgetTableAccent(parseWidgetTableAccent(wc))
    setChartSeriesColors(parseHexColorMap(wc.chart_series_colors))
    setChartCategoryColors(parseHexColorMap(wc.chart_category_colors))
  }, [widget.id, configSig])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const raw = await apiClient.executeQuery(widget.saved_query_id)
      setData(queryResultFromExecuteApi(raw as Record<string, unknown>))
    } catch (e: unknown) {
      setData(null)
      setError(getApiErrorMessage(e, 'Error al cargar datos'))
    } finally {
      setLoading(false)
    }
  }, [widget.saved_query_id])

  useEffect(() => {
    void load()
  }, [load])

  const persistDefaultView = useCallback(
    (view: WidgetView, canSwitchTabs: boolean) => {
      if (!canSwitchTabs) return
      if (persistViewTimer.current) clearTimeout(persistViewTimer.current)
      persistViewTimer.current = setTimeout(() => {
        void apiClient
          .patchDashboardWidget(DASH_ALIAS, widget.id, {
            widget_config: { default_view: view },
          })
          .catch(() => {
            /* silencioso: la vista local ya cambió */
          })
      }, 400)
    },
    [widget.id]
  )

  const persistChartKind = useCallback(
    (kind: WidgetChartKind) => {
      if (!cfg.showChart) return
      if (persistChartTimer.current) clearTimeout(persistChartTimer.current)
      persistChartTimer.current = setTimeout(() => {
        void apiClient
          .patchDashboardWidget(DASH_ALIAS, widget.id, {
            widget_config: { chart_kind: kind },
          })
          .catch(() => {
            /* silencioso */
          })
      }, 400)
    },
    [cfg.showChart, widget.id]
  )

  const persistWidgetTableAccent = useCallback(
    (choice: TableAccentId | '__global__') => {
      if (!cfg.showTable) return
      const next = choice === '__global__' ? undefined : choice
      setWidgetTableAccent(next)
      if (persistTableAccentTimer.current) clearTimeout(persistTableAccentTimer.current)
      persistTableAccentTimer.current = setTimeout(() => {
        void apiClient
          .patchDashboardWidget(DASH_ALIAS, widget.id, {
            widget_config: { table_accent: choice === '__global__' ? null : choice },
          })
          .catch(() => {
            /* silencioso */
          })
      }, 400)
    },
    [cfg.showTable, widget.id]
  )

  const schedulePersistSeriesColors = useCallback(
    (map: Record<string, string>) => {
      if (persistSeriesColorsTimer.current) clearTimeout(persistSeriesColorsTimer.current)
      persistSeriesColorsTimer.current = setTimeout(() => {
        void apiClient
          .patchDashboardWidget(DASH_ALIAS, widget.id, {
            widget_config: { chart_series_colors: map },
          })
          .catch(() => {})
      }, 400)
    },
    [widget.id]
  )

  const schedulePersistCategoryColors = useCallback(
    (map: Record<string, string>) => {
      if (persistCategoryColorsTimer.current) clearTimeout(persistCategoryColorsTimer.current)
      persistCategoryColorsTimer.current = setTimeout(() => {
        void apiClient
          .patchDashboardWidget(DASH_ALIAS, widget.id, {
            widget_config: { chart_category_colors: map },
          })
          .catch(() => {})
      }, 400)
    },
    [widget.id]
  )

  const handleTab = (next: WidgetView, canSwitchTabs: boolean) => {
    setTab(next)
    persistDefaultView(next, canSwitchTabs)
  }

  const handleChartKindChange = (kind: WidgetChartKind) => {
    setChartKind(kind)
    persistChartKind(kind)
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

  const singleRow = Boolean(data && isSingleRowQueryResult(data))
  const showBothChartTable = cfg.showChart && cfg.showTable
  const needsTabBar =
    showBothChartTable || Boolean(singleRow && (cfg.showChart || cfg.showTable))

  const showDisplayMenu =
    Boolean(data && !loading && !error) && (needsTabBar || cfg.showChart || cfg.showTable)

  useEffect(() => {
    if (!data) return
    if (tab === 'value' && !isSingleRowQueryResult(data)) {
      setTab(cfg.showChart ? 'chart' : 'table')
    }
  }, [data, tab, cfg.showChart, cfg.showTable])

  const chartColorMeta = (() => {
    if (!data) return null
    const spec = buildQueryChartSpec(data)
    if (!spec) return null
    const cart = effectiveCartesianKind(chartKind, spec.preferLine)
    return { spec, cartKind: cart, yKeys: spec.yKeys }
  })()

  const accentForChart =
    widgetTableAccent !== undefined ? widgetTableAccent : globalTableAccent
  const chartPrimaryHex = chartHexForAccent(accentForChart)

  const categoryLabelsForColors =
    chartColorMeta &&
    chartColorMeta.yKeys.length === 1 &&
    chartColorMeta.cartKind === 'bar' &&
    chartColorMeta.spec.chartData.length > 2
      ? [...new Set(chartColorMeta.spec.chartData.map((r) => String(r[chartColorMeta.spec.xKey] ?? '')))].slice(
          0,
          20
        )
      : []

  return (
    <article
      className={cn(
        'flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-slate-600 dark:bg-slate-800',
        className
      )}
      data-widget-id={widget.id}
    >
      <header className="flex items-start justify-between gap-2 border-b border-gray-100 px-4 py-3 dark:border-slate-700">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-gray-900 dark:text-white">{cfg.title}</h3>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {showDisplayMenu && (
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button
                  type="button"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 dark:text-gray-400 dark:hover:bg-slate-700 dark:hover:text-white"
                  aria-label="Vista, gráfica y color de tabla"
                >
                  <SlidersHorizontal className="h-4 w-4" aria-hidden />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  sideOffset={6}
                  align="end"
                  className={cn(
                    'z-[200] max-h-[min(70vh,420px)] w-56 overflow-y-auto rounded-lg border border-gray-200 bg-white p-1 shadow-lg',
                    'dark:border-slate-600 dark:bg-slate-900'
                  )}
                >
                  {needsTabBar && (
                    <>
                      <DropdownMenu.Label className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                        Vista
                      </DropdownMenu.Label>
                      <DropdownMenu.RadioGroup
                        value={tab}
                        onValueChange={(v) => handleTab(v as WidgetView, needsTabBar)}
                      >
                        {cfg.showChart && (
                          <DropdownMenu.RadioItem
                            value="chart"
                            className={cn(
                              'relative flex cursor-pointer select-none items-center rounded-md px-2 py-1.5 pl-7 text-sm text-gray-900 outline-none',
                              'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
                              'data-[highlighted]:bg-slate-50 data-[state=checked]:font-medium dark:text-white dark:data-[highlighted]:bg-slate-800'
                            )}
                          >
                            <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                              <DropdownMenu.ItemIndicator className="inline-flex">
                                <span className="h-1.5 w-1.5 rounded-full bg-slate-600 dark:bg-slate-400" />
                              </DropdownMenu.ItemIndicator>
                            </span>
                            Gráfica
                          </DropdownMenu.RadioItem>
                        )}
                        {singleRow && data && (
                          <DropdownMenu.RadioItem
                            value="value"
                            className={cn(
                              'relative flex cursor-pointer select-none items-center rounded-md px-2 py-1.5 pl-7 text-sm text-gray-900 outline-none',
                              'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
                              'data-[highlighted]:bg-slate-50 data-[state=checked]:font-medium dark:text-white dark:data-[highlighted]:bg-slate-800'
                            )}
                          >
                            <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                              <DropdownMenu.ItemIndicator className="inline-flex">
                                <span className="h-1.5 w-1.5 rounded-full bg-slate-600 dark:bg-slate-400" />
                              </DropdownMenu.ItemIndicator>
                            </span>
                            {singleRowValueTabLabel(data)}
                          </DropdownMenu.RadioItem>
                        )}
                        {cfg.showTable && (
                          <DropdownMenu.RadioItem
                            value="table"
                            className={cn(
                              'relative flex cursor-pointer select-none items-center rounded-md px-2 py-1.5 pl-7 text-sm text-gray-900 outline-none',
                              'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
                              'data-[highlighted]:bg-slate-50 data-[state=checked]:font-medium dark:text-white dark:data-[highlighted]:bg-slate-800'
                            )}
                          >
                            <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                              <DropdownMenu.ItemIndicator className="inline-flex">
                                <span className="h-1.5 w-1.5 rounded-full bg-slate-600 dark:bg-slate-400" />
                              </DropdownMenu.ItemIndicator>
                            </span>
                            Tabla
                          </DropdownMenu.RadioItem>
                        )}
                      </DropdownMenu.RadioGroup>
                    </>
                  )}
                  {needsTabBar && cfg.showChart && <DropdownMenu.Separator className="my-1 h-px bg-gray-100 dark:bg-slate-700" />}
                  {cfg.showChart && (
                    <>
                      <DropdownMenu.Label className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                        Tipo de gráfica
                      </DropdownMenu.Label>
                      <DropdownMenu.RadioGroup
                        value={chartKind}
                        onValueChange={(v) => handleChartKindChange(v as WidgetChartKind)}
                      >
                        {WIDGET_CHART_OPTIONS.map((opt) => (
                          <DropdownMenu.RadioItem
                            key={opt.value}
                            value={opt.value}
                            className={cn(
                              'relative flex cursor-pointer select-none items-center rounded-md px-2 py-1.5 pl-7 text-sm text-gray-900 outline-none',
                              'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
                              'data-[highlighted]:bg-slate-50 data-[state=checked]:font-medium dark:text-white dark:data-[highlighted]:bg-slate-800'
                            )}
                          >
                            <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                              <DropdownMenu.ItemIndicator className="inline-flex">
                                <span className="h-1.5 w-1.5 rounded-full bg-slate-600 dark:bg-slate-400" />
                              </DropdownMenu.ItemIndicator>
                            </span>
                            {opt.label}
                          </DropdownMenu.RadioItem>
                        ))}
                      </DropdownMenu.RadioGroup>
                    </>
                  )}
                  {cfg.showTable && (
                    <>
                      {(needsTabBar || cfg.showChart) && (
                        <DropdownMenu.Separator className="my-1 h-px bg-gray-100 dark:bg-slate-700" />
                      )}
                      <DropdownMenu.Label className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                        Color de la tabla
                      </DropdownMenu.Label>
                      <DropdownMenu.RadioGroup
                        value={widgetTableAccent ?? '__global__'}
                        onValueChange={(v) => persistWidgetTableAccent(v as TableAccentId | '__global__')}
                      >
                        <DropdownMenu.RadioItem
                          value="__global__"
                          className={cn(
                            'relative flex cursor-pointer select-none items-center rounded-md px-2 py-1.5 pl-7 text-sm text-gray-900 outline-none',
                            'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
                            'data-[highlighted]:bg-slate-50 data-[state=checked]:font-medium dark:text-white dark:data-[highlighted]:bg-slate-800'
                          )}
                        >
                          <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                            <DropdownMenu.ItemIndicator className="inline-flex">
                              <span className="h-1.5 w-1.5 rounded-full bg-slate-600 dark:bg-slate-400" />
                            </DropdownMenu.ItemIndicator>
                          </span>
                          Predeterminado (configuración)
                        </DropdownMenu.RadioItem>
                        {TABLE_ACCENT_OPTIONS.map((opt) => (
                          <DropdownMenu.RadioItem
                            key={opt.id}
                            value={opt.id}
                            className={cn(
                              'relative flex cursor-pointer select-none items-center rounded-md px-2 py-1.5 pl-7 text-sm text-gray-900 outline-none',
                              'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
                              'data-[highlighted]:bg-slate-50 data-[state=checked]:font-medium dark:text-white dark:data-[highlighted]:bg-slate-800'
                            )}
                          >
                            <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                              <DropdownMenu.ItemIndicator className="inline-flex">
                                <span className="h-1.5 w-1.5 rounded-full bg-slate-600 dark:bg-slate-400" />
                              </DropdownMenu.ItemIndicator>
                            </span>
                            <span className="flex items-center gap-2">
                              <span
                                className={cn('h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-black/15', opt.swatch)}
                                aria-hidden
                              />
                              {opt.label}
                            </span>
                          </DropdownMenu.RadioItem>
                        ))}
                      </DropdownMenu.RadioGroup>
                    </>
                  )}
                  {cfg.showChart &&
                    chartKind !== 'pie' &&
                    chartColorMeta &&
                    chartColorMeta.yKeys.length > 2 && (
                      <>
                        <DropdownMenu.Separator className="my-1 h-px bg-gray-100 dark:bg-slate-700" />
                        <DropdownMenu.Label className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                          Color por métrica
                        </DropdownMenu.Label>
                        <p className="px-2 pb-1 text-[10px] leading-snug text-gray-500 dark:text-gray-400">
                          Más de dos columnas numéricas: un color por serie. La primera toma el acento del widget; el
                          resto tiene sugerencias editables aquí.
                        </p>
                        <div
                          className="max-h-44 overflow-y-auto px-1 py-1"
                          onPointerDown={(e) => e.stopPropagation()}
                        >
                          {chartColorMeta.yKeys.map((k, i) => {
                            const def = seriesStrokeFills(
                              chartPrimaryHex,
                              chartColorMeta.yKeys,
                              chartSeriesColors
                            )[i]
                            const val = chartSeriesColors[k] ?? def
                            return (
                              <div key={k} className="flex items-center gap-2 px-1 py-1">
                                <span
                                  className="min-w-0 flex-1 truncate text-xs text-gray-800 dark:text-gray-200"
                                  title={columnHeaderLabel(k, data?.column_labels_es)}
                                >
                                  {columnHeaderLabel(k, data?.column_labels_es)}
                                </span>
                                <input
                                  type="color"
                                  value={val}
                                  onChange={(e) => {
                                    const hex = e.target.value
                                    const next = { ...chartSeriesColors, [k]: hex }
                                    setChartSeriesColors(next)
                                    schedulePersistSeriesColors(next)
                                  }}
                                  className="h-8 w-10 shrink-0 cursor-pointer overflow-hidden rounded border border-gray-300 bg-white p-0 dark:border-slate-600"
                                  aria-label={`Color de la serie ${k}`}
                                />
                              </div>
                            )
                          })}
                        </div>
                      </>
                    )}
                  {cfg.showChart &&
                    chartKind !== 'pie' &&
                    categoryLabelsForColors.length > 0 && (
                      <>
                        <DropdownMenu.Separator className="my-1 h-px bg-gray-100 dark:bg-slate-700" />
                        <DropdownMenu.Label className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                          Color por categoría (eje X)
                        </DropdownMenu.Label>
                        <p className="px-2 pb-1 text-[10px] leading-snug text-gray-500 dark:text-gray-400">
                          Solo barras con una métrica y más de dos categorías. Cada barra puede tener su color.
                        </p>
                        <div
                          className="max-h-44 overflow-y-auto px-1 py-1"
                          onPointerDown={(e) => e.stopPropagation()}
                        >
                          {categoryLabelsForColors.map((label) => {
                            const val = chartCategoryColors[label] ?? chartPrimaryHex
                            return (
                              <div key={label || '__empty'} className="flex items-center gap-2 px-1 py-1">
                                <span
                                  className="min-w-0 flex-1 truncate text-xs text-gray-800 dark:text-gray-200"
                                  title={label || '—'}
                                >
                                  {label || '—'}
                                </span>
                                <input
                                  type="color"
                                  value={val}
                                  onChange={(e) => {
                                    const hex = e.target.value
                                    const next = { ...chartCategoryColors, [label]: hex }
                                    setChartCategoryColors(next)
                                    schedulePersistCategoryColors(next)
                                  }}
                                  className="h-8 w-10 shrink-0 cursor-pointer overflow-hidden rounded border border-gray-300 bg-white p-0 dark:border-slate-600"
                                  aria-label={`Color categoría ${label || 'vacía'}`}
                                />
                              </div>
                            )
                          })}
                        </div>
                      </>
                    )}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          )}
          {showWidgetActions && (
            <div
              className={cn(
                'flex items-center gap-1',
                showDisplayMenu && 'ml-1 border-l border-gray-200 pl-2 dark:border-slate-600'
              )}
            >
              <button
                type="button"
                onClick={() => void load()}
                disabled={loading}
                className="rounded-lg px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 dark:text-slate-400 dark:hover:bg-slate-700"
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
          )}
        </div>
      </header>

      <div className="min-h-[200px] flex-1 p-4 pt-3">
        {loading && <p className="text-sm text-gray-500 dark:text-gray-400">Cargando…</p>}
        {!loading && error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        {!loading && !error && data && (
          <>
            {cfg.showChart &&
              (!needsTabBar ? tab === 'chart' || !showBothChartTable : tab === 'chart') &&
              data.column_names.length > 0 && (
                <div className="h-[260px] w-full min-w-0">
                  <QueryResultsChart
                    data={data}
                    chartKind={chartKind}
                    accentId={widgetTableAccent}
                    seriesColors={chartSeriesColors}
                    categoryColors={chartCategoryColors}
                  />
                </div>
              )}
            {singleRow && tab === 'value' && <SingleQueryResultValuePanel results={data} />}
            {cfg.showTable &&
              (!needsTabBar ? tab === 'table' || !showBothChartTable : tab === 'table') &&
              data.column_names.length > 0 && (
                <div className="space-y-2">
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => downloadQueryResultsCsv(data)}
                      className="rounded-lg bg-slate-600 px-2 py-1 text-xs font-medium text-white hover:bg-slate-700"
                    >
                      CSV
                    </button>
                  </div>
                  <DataResultTable results={data} accentId={widgetTableAccent} />
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
