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

function cloneGeomMap(m: Map<string, WidgetGeometry>): Map<string, WidgetGeometry> {
  const n = new Map<string, WidgetGeometry>()
  for (const [k, v] of m) n.set(k, { ...v })
  return n
}

export function layoutHasAnyOverlap(M: Map<string, WidgetGeometry>): boolean {
  const ids = [...M.keys()]
  for (let i = 0; i < ids.length; i++) {
    for (let j = i + 1; j < ids.length; j++) {
      if (widgetsOverlap(M.get(ids[i])!, M.get(ids[j])!)) return true
    }
  }
  return false
}

function findNonOverlappingSlot(
  moverId: string,
  mover: WidgetGeometry,
  M: Map<string, WidgetGeometry>,
  layoutCols: number,
  maxScanY: number
): WidgetGeometry | null {
  const lc = Math.max(1, Math.min(Math.floor(layoutCols) || 12, 24))
  const w = Math.max(1, Math.min(Math.floor(mover.width), lc))
  const h = Math.max(1, Math.floor(mover.height))
  for (let y = 0; y < maxScanY; y++) {
    for (let x = 0; x <= lc - w; x++) {
      const cand = clampWidgetGeometry({ pos_x: x, pos_y: y, width: w, height: h }, lc, maxScanY)
      const test = cloneGeomMap(M)
      test.set(moverId, cand)
      if (!layoutHasAnyOverlap(test)) return cand
    }
  }
  return null
}

function tryMoveMoverAwayFromFixed(
  moverId: string,
  fixedId: string,
  M: Map<string, WidgetGeometry>,
  layoutCols: number,
  maxHeight: number
): boolean {
  const fix = M.get(fixedId)
  const mov = M.get(moverId)
  if (!fix || !mov) return false

  const raw: WidgetGeometry[] = [
    { ...mov, pos_x: fix.pos_x + fix.width, pos_y: mov.pos_y },
    { ...mov, pos_x: fix.pos_x + fix.width, pos_y: fix.pos_y },
    { ...mov, pos_x: mov.pos_x, pos_y: fix.pos_y + fix.height },
    { ...mov, pos_x: fix.pos_x, pos_y: fix.pos_y + fix.height },
    { ...mov, pos_x: 0, pos_y: fix.pos_y + fix.height },
  ]

  for (const r of raw) {
    const cand = clampWidgetGeometry(r, layoutCols, maxHeight)
    const test = cloneGeomMap(M)
    test.set(moverId, cand)
    if (!layoutHasAnyOverlap(test)) {
      M.set(moverId, cand)
      return true
    }
  }
  return false
}

/**
 * Coloca el widget activo en `proposed` y empuja los demás para eliminar solapamientos.
 * Usado al mover/redimensionar en modo organizar: el vecino cede sitio en lugar de bloquear.
 */
export function resolveLayoutWithPush(
  activeId: string,
  proposed: WidgetGeometry,
  snapshot: Map<string, WidgetGeometry>,
  layoutCols: number,
  maxHeight = 80
): Map<string, WidgetGeometry> | null {
  const lc = Math.max(1, Math.min(Math.floor(layoutCols) || 12, 24))
  const M = cloneGeomMap(snapshot)
  M.set(activeId, clampWidgetGeometry(proposed, lc, maxHeight))

  const maxIter = 500
  for (let iter = 0; iter < maxIter; iter++) {
    if (!layoutHasAnyOverlap(M)) return M

    const ids = [...M.keys()].sort((a, b) => a.localeCompare(b))
    let idA = ''
    let idB = ''
    outer: for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const ga = M.get(ids[i])!
        const gb = M.get(ids[j])!
        if (widgetsOverlap(ga, gb)) {
          idA = ids[i]
          idB = ids[j]
          break outer
        }
      }
    }

    let mover: string
    let fixed: string
    if (idA === activeId) {
      mover = idB
      fixed = idA
    } else if (idB === activeId) {
      mover = idA
      fixed = idB
    } else {
      mover = idB
      fixed = idA
    }

    if (tryMoveMoverAwayFromFixed(mover, fixed, M, lc, maxHeight)) continue

    const placed = findNonOverlappingSlot(mover, M.get(mover)!, M, lc, maxHeight)
    if (!placed) return null
    M.set(mover, placed)
  }
  return null
}
