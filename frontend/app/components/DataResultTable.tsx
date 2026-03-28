'use client'

import { useState } from 'react'
import { columnHeaderLabel } from '@/lib/columnLabels'
import { tableAccentClasses, type TableAccentId } from '@/lib/tableAccent'
import { useTableAccentId } from '@/hooks/useTableAccent'
import type { QueryResultData } from '@/types'

type Props = {
  results: QueryResultData
  /** Si se omite o es `undefined`, se usa el color de Configuración. */
  accentId?: TableAccentId | null
}

export function DataResultTable({ results, accentId }: Props) {
  const globalAccent = useTableAccentId()
  const resolvedAccent = accentId != null ? accentId : globalAccent
  const c = tableAccentClasses(resolvedAccent)
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
    <div
      className={`mt-3 overflow-hidden rounded-lg border bg-white text-xs dark:bg-slate-800 ${c.outer}`}
    >
      <div
        className={`flex items-center justify-between border-b px-3 py-2 ${c.headerBar}`}
      >
        <span className={`font-medium ${c.headerBarText}`}>
          {results.total_rows} registro{results.total_rows !== 1 ? 's' : ''}
        </span>
        <div className="flex gap-2">
          {results.generated_sql && (
            <>
              <button
                type="button"
                onClick={() => setShowSql((v) => !v)}
                className={`underline ${c.toolbarMuted}`}
              >
                {showSql ? 'Ocultar SQL' : 'Ver SQL'}
              </button>
              <button
                type="button"
                onClick={handleCopySql}
                className={`underline ${c.toolbarMuted}`}
              >
                {copied ? '✓ Copiado' : 'Copiar SQL'}
              </button>
            </>
          )}
        </div>
      </div>

      {showSql && results.generated_sql && (
        <pre
          className={`overflow-x-auto whitespace-pre-wrap px-3 py-2 text-xs ${c.sqlBlock}`}
        >
          {results.generated_sql}
        </pre>
      )}

      <div className="overflow-x-auto dark:bg-slate-800">
        <table className="w-full text-left">
          <thead>
            <tr className={`border-b ${c.theadRow}`}>
              {cols.map((col: string) => (
                <th key={col} className={`whitespace-nowrap px-3 py-2 font-semibold ${c.thText}`}>
                  {columnHeaderLabel(col, results.column_labels_es)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row: Record<string, unknown>, i: number) => (
              <tr
                key={i}
                className={`border-b ${i % 2 === 0 ? c.rowEven : c.rowOdd}`}
              >
                {cols.map((col: string) => (
                  <td key={col} className={`whitespace-nowrap px-3 py-2 ${c.cellText}`}>
                    {row[col] === null || row[col] === undefined ? '—' : String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {results.rows.length > 10 && (
        <div className={`border-t px-3 py-2 text-center ${c.footerBar}`}>
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className={`font-medium ${c.footerLink}`}
          >
            {showAll ? 'Mostrar menos' : `Ver los ${results.rows.length} registros`}
          </button>
        </div>
      )}
    </div>
  )
}
