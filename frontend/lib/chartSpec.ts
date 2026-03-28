import type { QueryResultData } from '@/types'
import type { WidgetChartKind } from '@/lib/widgetDisplay'

function numericRatio(rows: Record<string, unknown>[], col: string, limit = 20): number {
  const slice = rows.slice(0, limit)
  let ok = 0
  let tot = 0
  for (const r of slice) {
    const v = r[col]
    if (v === null || v === undefined || v === '') continue
    tot++
    if (typeof v === 'number' && !Number.isNaN(v)) ok++
    else if (typeof v === 'string' && v.trim() !== '' && !Number.isNaN(Number(v))) ok++
  }
  return tot === 0 ? 0 : ok / tot
}

export type QueryChartSpec = {
  chartData: Record<string, string | number>[]
  xKey: string
  yKeys: string[]
  preferLine: boolean
}

export function buildQueryChartSpec(data: QueryResultData): QueryChartSpec | null {
  const { rows, column_names } = data
  if (!rows.length || !column_names.length) return null

  const numericCols = column_names.filter((c) => numericRatio(rows, c) >= 0.65)
  const catCols = column_names.filter((c) => !numericCols.includes(c))

  let xKey = catCols[0] ?? column_names[0]
  let yKeys = numericCols.filter((k) => k !== xKey)

  if (yKeys.length === 0 && numericCols.length >= 2) {
    xKey = numericCols[0]
    yKeys = numericCols.slice(1, 4)
  } else if (yKeys.length === 0 && numericCols.length === 1) {
    const y = numericCols[0]
    const chartData = rows.map((r, i) => ({
      __x: `Fila ${i + 1}`,
      [y]: Number(r[y]) || 0,
    }))
    return { chartData, xKey: '__x', yKeys: [y], preferLine: rows.length > 8 }
  }

  if (yKeys.length === 0) return null

  yKeys = yKeys.slice(0, 4)

  const chartData = rows.map((r) => {
    const out: Record<string, string | number> = {}
    const xv = r[xKey]
    out[xKey] = xv === null || xv === undefined ? '—' : String(xv)
    for (const y of yKeys) {
      const raw = r[y]
      const n = typeof raw === 'number' ? raw : Number(raw)
      out[y] = Number.isFinite(n) ? n : 0
    }
    return out
  })

  const preferLine = rows.length > 6 && numericRatio(rows, xKey, 10) >= 0.5

  return { chartData, xKey, yKeys, preferLine }
}

export function effectiveCartesianKind(
  kind: WidgetChartKind | undefined,
  preferLine: boolean
): 'bar' | 'line' | 'area' {
  if (kind === 'bar' || kind === 'line' || kind === 'area') return kind
  return preferLine ? 'line' : 'bar'
}
