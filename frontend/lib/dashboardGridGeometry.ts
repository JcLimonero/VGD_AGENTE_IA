import type { ApiDashboardWidget } from '@/types'

export type WidgetGeometry = Pick<ApiDashboardWidget, 'pos_x' | 'pos_y' | 'width' | 'height'>

export function clampWidgetGeometry(
  g: WidgetGeometry,
  layoutCols: number,
  maxHeight = 24
): WidgetGeometry {
  const lc = Math.max(1, Math.min(Math.floor(layoutCols) || 12, 24))
  const width = Math.max(1, Math.min(Math.floor(g.width), lc))
  const pos_x = Math.max(0, Math.min(Math.floor(g.pos_x), lc - width))
  const height = Math.max(1, Math.min(Math.floor(g.height), maxHeight))
  const pos_y = Math.max(0, Math.floor(g.pos_y))
  return { pos_x, pos_y, width, height }
}

export function widgetsOverlap(a: WidgetGeometry, b: WidgetGeometry): boolean {
  return !(
    a.pos_x + a.width <= b.pos_x ||
    b.pos_x + b.width <= a.pos_x ||
    a.pos_y + a.height <= b.pos_y ||
    b.pos_y + b.height <= a.pos_y
  )
}

export function overlapsAny(
  widgetId: string,
  g: WidgetGeometry,
  widgets: ApiDashboardWidget[]
): boolean {
  return widgets.some((w) => w.id !== widgetId && widgetsOverlap(g, w))
}

export function hasAnyPairwiseOverlap(widgets: ApiDashboardWidget[]): boolean {
  for (let i = 0; i < widgets.length; i++) {
    const a = widgets[i]
    const ga: WidgetGeometry = {
      pos_x: a.pos_x,
      pos_y: a.pos_y,
      width: a.width,
      height: a.height,
    }
    for (let j = i + 1; j < widgets.length; j++) {
      const b = widgets[j]
      const gb: WidgetGeometry = {
        pos_x: b.pos_x,
        pos_y: b.pos_y,
        width: b.width,
        height: b.height,
      }
      if (widgetsOverlap(ga, gb)) return true
    }
  }
  return false
}

/** Orden visual en filas cuando las posiciones guardadas se solapan. */
export function packWidgetsFlow(
  widgets: ApiDashboardWidget[],
  cols: number
): Map<string, WidgetGeometry> {
  const m = new Map<string, WidgetGeometry>()
  const sorted = [...widgets].sort(
    (a, b) => (a.display_order ?? 0) - (b.display_order ?? 0) || a.id.localeCompare(b.id)
  )
  let x = 0
  let y = 0
  let rowMaxH = 0
  const lc = Math.max(1, Math.floor(cols) || 12)
  for (const w of sorted) {
    const width = Math.min(Math.max(1, Math.floor(w.width)), lc)
    const height = Math.max(1, Math.floor(w.height))
    if (x + width > lc) {
      x = 0
      y += rowMaxH
      rowMaxH = 0
    }
    m.set(w.id, clampWidgetGeometry({ pos_x: x, pos_y: y, width, height }, lc))
    rowMaxH = Math.max(rowMaxH, height)
    x += width
  }
  return m
}
