import { columnHeaderLabel } from '@/lib/columnLabels'
import type { QueryResultData } from '@/types'

function escapeCsvCell(val: unknown): string {
  if (val === null || val === undefined) return ''
  const s = String(val)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

/** Descarga los resultados como CSV (UTF-8 con BOM para Excel en español). */
export function downloadQueryResultsCsv(data: QueryResultData, filename?: string): void {
  const cols = data.column_names
  const header = cols.map((c) => escapeCsvCell(columnHeaderLabel(c, data.column_labels_es))).join(',')
  const lines = data.rows.map((row) => cols.map((c) => escapeCsvCell(row[c])).join(','))
  const BOM = '\uFEFF'
  const csv = BOM + [header, ...lines].join('\r\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const base = filename ?? `consulta_${new Date().toISOString().slice(0, 10)}`
  a.download = base.endsWith('.csv') ? base : `${base}.csv`
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
