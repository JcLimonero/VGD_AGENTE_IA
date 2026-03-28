'use client'

import { columnHeaderLabel } from '@/lib/columnLabels'
import type { QueryResultData } from '@/types'

function parseTotalRows(v: unknown): number | undefined {
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v)
    if (Number.isFinite(n)) return n
  }
  return undefined
}

/** Una sola fila devuelta (y presente en `rows`): vista Solo valor / Valores. */
export function isSingleRowQueryResult(r: QueryResultData): boolean {
  if (!r?.rows || !Array.isArray(r.rows) || r.rows.length !== 1) return false
  const row = r.rows[0]
  if (!row || typeof row !== 'object') return false

  const n = parseTotalRows(r.total_rows)
  if (n !== undefined && n > 1) return false

  const cols = r.column_names
  if (Array.isArray(cols) && cols.length > 0) return true
  return Object.keys(row as Record<string, unknown>).length > 0
}

export function effectiveQueryColumnNames(r: QueryResultData): string[] {
  if (r.column_names?.length) return r.column_names
  const row = r.rows[0] as Record<string, unknown> | undefined
  return row ? Object.keys(row) : []
}

export function singleRowValueTabLabel(r: QueryResultData): string {
  return effectiveQueryColumnNames(r).length === 1 ? 'Solo valor' : 'Valores'
}

export function SingleQueryResultValuePanel({ results }: { results: QueryResultData }) {
  const row = results.rows[0] as Record<string, unknown>
  const cols = effectiveQueryColumnNames(results)

  if (cols.length === 1) {
    const col = cols[0]!
    const raw = row[col]
    const display = raw === null || raw === undefined ? '—' : String(raw)
    const label = columnHeaderLabel(col, results.column_labels_es)
    return (
      <div className="rounded-xl border border-violet-200 bg-gradient-to-b from-violet-50 to-white px-5 py-8 text-center dark:border-violet-900/40 dark:from-violet-950/35 dark:to-slate-800/60">
        <p className="text-xs font-medium uppercase tracking-wide text-violet-600/90 dark:text-violet-400/90">
          {label}
        </p>
        <p className="mt-3 break-words font-mono text-2xl font-semibold tabular-nums text-gray-900 dark:text-white sm:text-3xl">
          {display}
        </p>
      </div>
    )
  }

  return (
    <dl className="space-y-3 rounded-xl border border-gray-200 bg-white p-4 dark:border-slate-600 dark:bg-slate-800/60">
      {cols.map((col) => (
        <div
          key={col}
          className="flex flex-col gap-0.5 border-b border-gray-100 pb-3 last:border-0 last:pb-0 dark:border-slate-700/80"
        >
          <dt className="text-xs font-medium text-gray-500 dark:text-gray-400">
            {columnHeaderLabel(col, results.column_labels_es)}
          </dt>
          <dd className="min-w-0 break-words font-mono text-base font-semibold text-gray-900 dark:text-white">
            {row[col] == null ? '—' : String(row[col])}
          </dd>
        </div>
      ))}
    </dl>
  )
}
