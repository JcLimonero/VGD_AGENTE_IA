'use client'

import { useState } from 'react'
import { columnHeaderLabel } from '@/lib/columnLabels'
import type { QueryResultData } from '@/types'

export function DataResultTable({ results }: { results: QueryResultData }) {
  const [showAll, setShowAll] = useState(false)
  const [showSql, setShowSql] = useState(false)
  const [copied, setCopied] = useState(false)
  const displayRows = showAll ? results.rows : results.rows.slice(0, 10)
  const cols = results.column_names

  const handleCopySql = () => {
    if (!results.generated_sql) return
    void navigator.clipboard.writeText(results.generated_sql).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-gray-200 bg-white text-xs dark:border-slate-600 dark:bg-slate-800">
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-3 py-2 dark:border-slate-600 dark:bg-slate-700">
        <span className="font-medium text-gray-700 dark:text-slate-200">
          {results.total_rows} registro{results.total_rows !== 1 ? 's' : ''}
        </span>
        <div className="flex gap-2">
          {results.generated_sql && (
            <>
              <button
                type="button"
                onClick={() => setShowSql((v) => !v)}
                className="text-gray-500 underline hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                {showSql ? 'Ocultar SQL' : 'Ver SQL'}
              </button>
              <button
                type="button"
                onClick={handleCopySql}
                className="text-gray-500 underline hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                {copied ? '✓ Copiado' : 'Copiar SQL'}
              </button>
            </>
          )}
        </div>
      </div>

      {showSql && results.generated_sql && (
        <pre className="overflow-x-auto whitespace-pre-wrap bg-gray-900 px-3 py-2 text-xs text-green-400">
          {results.generated_sql}
        </pre>
      )}

      <div className="overflow-x-auto dark:bg-slate-800">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-100 dark:border-slate-600 dark:bg-slate-700">
              {cols.map((col: string) => (
                <th
                  key={col}
                  className="whitespace-nowrap px-3 py-2 font-semibold text-gray-800 dark:text-slate-100"
                >
                  {columnHeaderLabel(col, results.column_labels_es)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row: Record<string, unknown>, i: number) => (
              <tr
                key={i}
                className={
                  i % 2 === 0
                    ? 'border-b border-gray-100 bg-white text-gray-900 dark:border-slate-700/60 dark:bg-slate-800 dark:text-slate-100'
                    : 'border-b border-gray-100 bg-gray-50 text-gray-900 dark:border-slate-700/60 dark:bg-slate-900/85 dark:text-slate-100'
                }
              >
                {cols.map((col: string) => (
                  <td key={col} className="whitespace-nowrap px-3 py-2 text-gray-900 dark:text-slate-100">
                    {row[col] === null || row[col] === undefined ? '—' : String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {results.rows.length > 10 && (
        <div className="border-t border-gray-200 bg-gray-50 px-3 py-2 text-center dark:border-slate-600 dark:bg-slate-700/90">
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="font-medium text-blue-600 hover:underline dark:text-blue-300 dark:hover:text-blue-200"
          >
            {showAll ? 'Mostrar menos' : `Ver los ${results.rows.length} registros`}
          </button>
        </div>
      )}
    </div>
  )
}
