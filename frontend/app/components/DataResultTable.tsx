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
    <div className="mt-3 overflow-hidden rounded-lg border border-gray-200 text-xs dark:border-slate-600">
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-3 py-2 dark:border-slate-600 dark:bg-slate-700">
        <span className="font-medium text-gray-700 dark:text-gray-300">
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

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-gray-100 dark:bg-slate-600">
              {cols.map((col: string) => (
                <th
                  key={col}
                  className="whitespace-nowrap px-3 py-2 font-semibold text-gray-700 dark:text-gray-200"
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
                className={i % 2 === 0 ? 'bg-white dark:bg-slate-800' : 'bg-gray-50 dark:bg-slate-750'}
              >
                {cols.map((col: string) => (
                  <td key={col} className="whitespace-nowrap px-3 py-2 text-gray-800 dark:text-gray-200">
                    {row[col] === null || row[col] === undefined ? '—' : String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {results.rows.length > 10 && (
        <div className="border-t border-gray-200 bg-gray-50 px-3 py-2 text-center dark:border-slate-600 dark:bg-slate-700">
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="text-blue-600 hover:underline dark:text-blue-400"
          >
            {showAll ? 'Mostrar menos' : `Ver los ${results.rows.length} registros`}
          </button>
        </div>
      )}
    </div>
  )
}
