'use client'

import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { DataResultTable } from '@/components/DataResultTable'
import { QueryResultsChart } from '@/components/QueryResultsChart'
import { SaveChatQueryAction } from '@/components/SaveChatQueryAction'
import {
  effectiveQueryColumnNames,
  isSingleRowQueryResult,
  SingleQueryResultValuePanel,
} from '@/components/SingleQueryResultValue'
import { downloadQueryResultsCsv } from '@/lib/csvExport'
import type { ChatMessage, QueryResultData } from '@/types'
import { cn } from '@/lib/utils'

type TabId = 'summary' | 'value' | 'chart' | 'table'

type Props = {
  message: ChatMessage
  summary: ReactNode
}

export function AgentResponseDataPanel({ message, summary }: Props) {
  const results = message.metadata?.results
  const hasQuery = Boolean(message.metadata?.query_executed && results)

  const showValueTab = Boolean(results && isSingleRowQueryResult(results))
  const tabs = useMemo(() => {
    const list: { id: TabId; label: string }[] = [{ id: 'summary', label: 'Resumen' }]
    if (showValueTab && results) {
      const nc = effectiveQueryColumnNames(results).length
      list.push({
        id: 'value',
        label: nc === 1 ? 'Solo valor' : 'Valores',
      })
    }
    list.push({ id: 'chart', label: 'Gráfica' }, { id: 'table', label: 'Tabla' })
    return list
  }, [showValueTab, results])

  const [tab, setTab] = useState<TabId>(() => {
    const r = message.metadata?.results
    if (message.metadata?.query_executed && r && isSingleRowQueryResult(r as QueryResultData)) return 'value'
    return 'summary'
  })

  if (!hasQuery || !results) {
    return <>{summary}</>
  }

  return (
    <div className="w-full min-w-0">
      <div
        className="mb-3 flex flex-wrap gap-1 rounded-lg border border-gray-200 bg-gray-100/80 p-1 dark:border-slate-600 dark:bg-slate-900/60"
        role="tablist"
        aria-label="Formato de respuesta"
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm font-medium transition',
              tab === t.id
                ? 'bg-white text-slate-700 shadow-sm dark:bg-slate-800 dark:text-slate-300'
                : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" className="min-h-[2rem]">
        {tab === 'summary' && <div className="text-sm">{summary}</div>}

        {tab === 'value' && showValueTab && <SingleQueryResultValuePanel results={results} />}

        {tab === 'chart' && (
          <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-slate-600 dark:bg-slate-800/50">
            <QueryResultsChart data={results} />
          </div>
        )}

        {tab === 'table' && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {results.total_rows} fila{results.total_rows !== 1 ? 's' : ''}
                {results.total_rows > results.rows.length
                  ? ` (mostrando ${results.rows.length} en la tabla. Descarga el CSV para el conjunto completo.)`
                  : null}
              </p>
              <button
                type="button"
                onClick={() => downloadQueryResultsCsv(results)}
                className="rounded-lg bg-slate-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700"
              >
                Descargar CSV
              </button>
            </div>
            <DataResultTable results={results} />
          </div>
        )}
      </div>

      <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">Consulta ejecutada correctamente.</p>

      {results.generated_sql?.trim() ? (
        <SaveChatQueryAction
          userQuestion={message.metadata?.user_question ?? ''}
          sql={results.generated_sql.trim()}
        />
      ) : null}
    </div>
  )
}
