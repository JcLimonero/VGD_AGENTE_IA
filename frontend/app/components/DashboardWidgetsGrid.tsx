'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { GripVertical } from 'lucide-react'
import { DashboardWidgetCard } from '@/components/DashboardWidgetCard'
import { apiClient } from '@/services/api'
import type { ApiDashboardWidget } from '@/types'
import {
  clampWidgetGeometry,
  hasAnyPairwiseOverlap,
  packWidgetsFlow,
  resolveLayoutWithPush,
  type WidgetGeometry,
} from '@/lib/dashboardGridGeometry'
const DASH = 'default'
/** Alto aproximado de una fila lógica de cuadrícula (px), para convertir arrastre vertical en filas. */
const ROW_UNIT_PX = 56

type Props = {
  refreshToken?: number
  variant?: 'page' | 'showcase'
  onWidgetsChanged?: () => void
  /** Solo `variant="page"`: modo organizar controlado por el padre (p. ej. accesos rápidos → `?organize=1`). */
  organizeOpen?: boolean
  onOrganizeChange?: (open: boolean) => void
}

type DragSession = {
  widgetId: string
  mode: 'move' | 'resize'
  startX: number
  startY: number
  origin: WidgetGeometry
}

export function DashboardWidgetsGrid({
  refreshToken = 0,
  variant = 'page',
  onWidgetsChanged,
  organizeOpen,
  onOrganizeChange,
}: Props) {
  const [widgets, setWidgets] = useState<ApiDashboardWidget[]>([])
  const [layoutCols, setLayoutCols] = useState(12)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [organizeInternal, setOrganizeInternal] = useState(false)
  const controlledOrganize = variant === 'page' && typeof onOrganizeChange === 'function'
  const organize = controlledOrganize ? Boolean(organizeOpen) : organizeInternal

  const [previewLayout, setPreviewLayout] = useState<Map<string, WidgetGeometry> | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [savingLayout, setSavingLayout] = useState(false)

  const exitOrganizeMode = useCallback(() => {
    setPreviewLayout(null)
    sessionRef.current = null
    setDragActive(false)
    if (controlledOrganize) onOrganizeChange(false)
    else setOrganizeInternal(false)
  }, [controlledOrganize, onOrganizeChange])

  const containerRef = useRef<HTMLDivElement>(null)
  const sessionRef = useRef<DragSession | null>(null)
  const lastPreviewLayoutRef = useRef<Map<string, WidgetGeometry> | null>(null)
  const layoutSnapshotRef = useRef<Map<string, WidgetGeometry>>(new Map())
  const widgetsRef = useRef<ApiDashboardWidget[]>([])
  const geomMapRef = useRef<Map<string, WidgetGeometry>>(new Map())
  const layoutColsRef = useRef(12)
  const loadRef = useRef<() => Promise<void>>(async () => {})
  const onWidgetsChangedRef = useRef<Props['onWidgetsChanged']>(undefined)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const dash = await apiClient.getDashboard('default')
      const raw = dash as { widgets?: unknown; layout_cols?: number }
      const lc =
        typeof raw.layout_cols === 'number' && raw.layout_cols > 0 ? Math.min(raw.layout_cols, 24) : 12
      setLayoutCols(lc)
      const list = Array.isArray(raw.widgets) ? raw.widgets : []
      setWidgets(list as ApiDashboardWidget[])
    } catch (e: unknown) {
      setWidgets([])
      setError(e instanceof Error ? e.message : 'No se pudo cargar el dashboard')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleWidgetRemoved = useCallback(() => {
    void load().then(() => onWidgetsChanged?.())
  }, [load, onWidgetsChanged])

  useEffect(() => {
    void load()
  }, [load, refreshToken])

  const geomMap = useMemo(() => {
    if (!widgets.length) return new Map<string, WidgetGeometry>()
    if (!hasAnyPairwiseOverlap(widgets)) {
      const m = new Map<string, WidgetGeometry>()
      for (const w of widgets) {
        m.set(
          w.id,
          clampWidgetGeometry(
            { pos_x: w.pos_x, pos_y: w.pos_y, width: w.width, height: w.height },
            layoutCols
          )
        )
      }
      return m
    }
    return packWidgetsFlow(widgets, layoutCols)
  }, [widgets, layoutCols])

  useEffect(() => {
    widgetsRef.current = widgets
    geomMapRef.current = geomMap
    layoutColsRef.current = layoutCols
    loadRef.current = load
    onWidgetsChangedRef.current = onWidgetsChanged
  }, [widgets, geomMap, layoutCols, load, onWidgetsChanged])

  const startDrag = useCallback(
    (e: React.PointerEvent, widgetId: string, mode: 'move' | 'resize') => {
      if (!organize) return
      e.preventDefault()
      e.stopPropagation()
      const base = geomMap.get(widgetId)
      if (!base) return
      sessionRef.current = {
        widgetId,
        mode,
        startX: e.clientX,
        startY: e.clientY,
        origin: { ...base },
      }
      layoutSnapshotRef.current = new Map()
      for (const [id, g] of geomMap) {
        layoutSnapshotRef.current.set(id, { ...g })
      }
      lastPreviewLayoutRef.current = null
      setPreviewLayout(null)
      setDragActive(true)
    },
    [organize, geomMap]
  )

  useEffect(() => {
    if (!dragActive) return

    const onMove = (e: PointerEvent) => {
      const s = sessionRef.current
      const el = containerRef.current
      if (!s || !el) return
      const lc = layoutColsRef.current
      const rect = el.getBoundingClientRect()
      const cellW = Math.max(rect.width / lc, 1)
      const dCol = Math.round((e.clientX - s.startX) / cellW)
      const dRow = Math.round((e.clientY - s.startY) / ROW_UNIT_PX)

      let next: WidgetGeometry
      if (s.mode === 'move') {
        next = clampWidgetGeometry(
          {
            ...s.origin,
            pos_x: s.origin.pos_x + dCol,
            pos_y: s.origin.pos_y + dRow,
          },
          lc
        )
      } else {
        next = clampWidgetGeometry(
          {
            ...s.origin,
            width: s.origin.width + dCol,
            height: s.origin.height + dRow,
          },
          lc
        )
      }

      const resolved = resolveLayoutWithPush(
        s.widgetId,
        next,
        layoutSnapshotRef.current,
        lc
      )
      if (resolved) {
        lastPreviewLayoutRef.current = resolved
        setPreviewLayout(new Map(resolved))
      }
    }

    const onUp = () => {
      const s = sessionRef.current
      const finalLayout = lastPreviewLayoutRef.current
      sessionRef.current = null
      lastPreviewLayoutRef.current = null
      setDragActive(false)
      setPreviewLayout(null)

      if (!s || !finalLayout) return

      const snap = layoutSnapshotRef.current
      const updates: { id: string; body: { pos_x: number; pos_y: number; width: number; height: number } }[] = []
      for (const [id, g] of finalLayout) {
        const o = snap.get(id)
        if (
          !o ||
          o.pos_x !== g.pos_x ||
          o.pos_y !== g.pos_y ||
          o.width !== g.width ||
          o.height !== g.height
        ) {
          updates.push({
            id,
            body: { pos_x: g.pos_x, pos_y: g.pos_y, width: g.width, height: g.height },
          })
        }
      }
      if (updates.length === 0) return

      setSavingLayout(true)
      void Promise.all(updates.map((u) => apiClient.patchDashboardWidget(DASH, u.id, u.body)))
        .then(() => loadRef.current())
        .catch(() => {
          /* silencioso; el usuario puede reintentar */
        })
        .finally(() => {
          setSavingLayout(false)
          onWidgetsChangedRef.current?.()
        })
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [dragActive])

  const geomFor = (w: ApiDashboardWidget): WidgetGeometry => {
    const pl = previewLayout?.get(w.id)
    if (pl) return pl
    return (
      geomMap.get(w.id) ??
      clampWidgetGeometry(
        { pos_x: w.pos_x, pos_y: w.pos_y, width: w.width, height: w.height },
        layoutCols
      )
    )
  }

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Widgets en tu dashboard</h2>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            Cuadrícula de {layoutCols} columnas. Desde <strong className="font-medium">Accesos rápidos</strong> (icono de
            cuadrícula abajo a la derecha) abre <strong className="font-medium">Organizar tablero</strong> o{' '}
            <strong className="font-medium">Configurar widgets</strong>. Con el modo organizar activo puedes mover,
            redimensionar, actualizar o quitar widgets; pulsa Listo al terminar.
          </p>
        </div>
        {widgets.length > 0 && variant === 'page' && organize && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => exitOrganizeMode()}
              className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-violet-700"
            >
              Listo
            </button>
          </div>
        )}
      </div>

      {organize && widgets.length > 0 && (
        <p className="mb-3 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-900 dark:border-violet-900/50 dark:bg-violet-950/40 dark:text-violet-200">
          Arrastra el asa <GripVertical className="inline h-3.5 w-3.5 align-text-bottom" aria-hidden /> para mover. Usa
          la esquina inferior derecha para redimensionar. Si ocupas el sitio de otro widget, se desplaza automáticamente.
        </p>
      )}

      {loading && <p className="text-sm text-gray-500 dark:text-gray-400">Cargando widgets…</p>}
      {savingLayout && (
        <p className="mb-2 text-sm text-violet-600 dark:text-violet-400">Guardando posición…</p>
      )}
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
        <div
          ref={containerRef}
          className="grid gap-3"
          style={{
            gridTemplateColumns: `repeat(${layoutCols}, minmax(0, 1fr))`,
            gridAutoRows: 'minmax(88px, auto)',
          }}
        >
          {widgets.map((w) => {
            const g = geomFor(w)
            return (
              <div
                key={w.id}
                className="relative flex min-h-0 flex-col"
                style={{
                  gridColumn: `${g.pos_x + 1} / span ${g.width}`,
                  gridRow: `${g.pos_y + 1} / span ${g.height}`,
                }}
              >
                {organize && (
                  <>
                    <button
                      type="button"
                      aria-label={`Mover widget ${w.id}`}
                      onPointerDown={(e) => startDrag(e, w.id, 'move')}
                      className="absolute left-1 top-1 z-20 flex h-8 w-8 cursor-grab items-center justify-center rounded-md border border-violet-300 bg-white/95 text-violet-700 shadow-sm active:cursor-grabbing dark:border-violet-700 dark:bg-slate-900/95 dark:text-violet-300"
                    >
                      <GripVertical className="h-4 w-4" aria-hidden />
                    </button>
                    <div
                      role="presentation"
                      onPointerDown={(e) => startDrag(e, w.id, 'resize')}
                      className="absolute bottom-1 right-1 z-20 h-4 w-4 cursor-se-resize rounded-sm border-2 border-violet-500 bg-white/90 dark:border-violet-400 dark:bg-slate-900/90"
                    />
                  </>
                )}
                <DashboardWidgetCard
                  widget={w}
                  onRemoved={handleWidgetRemoved}
                  className="h-full"
                  showWidgetActions={variant === 'showcase' || organize}
                />
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
