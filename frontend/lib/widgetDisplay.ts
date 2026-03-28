/** Configuración persistida en `widget_config` (JSON) para cada widget del dashboard. */

import { fixSpanishSemicolonEnyeTypo } from '@/lib/spanishDisplay'

export type WidgetView = 'chart' | 'table' | 'value'

/** Tipo de gráfica elegido al crear el widget (`auto` = misma heurística que el chat). */
export type WidgetChartKind = 'auto' | 'bar' | 'line' | 'area' | 'pie'

const CHART_KINDS = new Set<string>(['auto', 'bar', 'line', 'area', 'pie'])

export function parseChartKind(config: Record<string, unknown>): WidgetChartKind {
  const raw = config.chart_kind
  if (typeof raw === 'string' && CHART_KINDS.has(raw)) {
    return raw as WidgetChartKind
  }
  return 'auto'
}

export const WIDGET_CHART_OPTIONS: ReadonlyArray<{ value: WidgetChartKind; label: string }> = [
  { value: 'auto', label: 'Automática (según datos)' },
  { value: 'bar', label: 'Barras' },
  { value: 'line', label: 'Líneas' },
  { value: 'area', label: 'Área' },
  { value: 'pie', label: 'Circular (pastel)' },
]

export function parseWidgetDisplayConfig(config: Record<string, unknown>): {
  showChart: boolean
  showTable: boolean
  defaultView: WidgetView
  title: string
  chartKind: WidgetChartKind
} {
  const rawTitle =
    typeof config.title === 'string' && config.title.trim() ? config.title.trim() : 'Consulta'
  const title = fixSpanishSemicolonEnyeTypo(rawTitle)

  const explicitChart = config.show_chart !== undefined
  const explicitTable = config.show_table !== undefined
  let showChart = config.show_chart !== false
  let showTable = config.show_table !== false
  if (!explicitChart && !explicitTable) {
    showChart = true
    showTable = true
  }
  if (!showChart && !showTable) {
    showChart = true
    showTable = true
  }

  let defaultView: WidgetView = 'chart'
  if (config.default_view === 'table') defaultView = 'table'
  else if (config.default_view === 'value') defaultView = 'value'

  if (defaultView === 'chart' && !showChart) defaultView = showTable ? 'table' : 'chart'
  if (defaultView === 'table' && !showTable) defaultView = showChart ? 'chart' : 'table'
  if (defaultView === 'value' && !showChart && !showTable) defaultView = 'chart'

  return { showChart, showTable, defaultView, title, chartKind: parseChartKind(config) }
}
