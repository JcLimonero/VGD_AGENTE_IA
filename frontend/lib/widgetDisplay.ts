/** Configuración persistida en `widget_config` (JSON) para cada widget del dashboard. */

export type WidgetView = 'chart' | 'table'

export function parseWidgetDisplayConfig(config: Record<string, unknown>): {
  showChart: boolean
  showTable: boolean
  defaultView: WidgetView
  title: string
} {
  const title =
    typeof config.title === 'string' && config.title.trim() ? config.title.trim() : 'Consulta'

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

  let defaultView: WidgetView = config.default_view === 'table' ? 'table' : 'chart'
  if (defaultView === 'chart' && !showChart) defaultView = 'table'
  if (defaultView === 'table' && !showTable) defaultView = 'chart'

  return { showChart, showTable, defaultView, title }
}
