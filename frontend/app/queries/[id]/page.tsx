'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { apiClient } from '@/services/api'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import { DataResultTable } from '@/components/DataResultTable'
import { normalizeSavedQuery, queryResultFromExecuteApi } from '@/lib/savedQuery'
import { getApiErrorMessage } from '@/lib/apiError'
import type { Query, QueryResultData } from '@/types'

export default function ExecuteQueryPage() {
  const params = useParams()
  const id = typeof params.id === 'string' ? params.id : params.id?.[0] ?? ''
  const router = useRouter()
  const { isAuthenticated } = useAuth()

  const [query, setQuery] = useState<Query | null>(null)
  const [result, setResult] = useState<QueryResultData | null>(null)
  const [loadingMeta, setLoadingMeta] = useState(true)
  const [loadingExec, setLoadingExec] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const autoRanForId = useRef<string | null>(null)

  const runExecute = useCallback(async () => {
    if (!id) return
    const sqlSnapshot = query?.sql
    setLoadingExec(true)
    setError(null)
    try {
      const raw = await apiClient.executeQuery(id)
      const r = raw as Record<string, unknown>
      setResult(queryResultFromExecuteApi(r, typeof sqlSnapshot === 'string' ? sqlSnapshot : undefined))
    } catch (e) {
      setResult(null)
      setError(getApiErrorMessage(e, 'Error al ejecutar el widget'))
    } finally {
      setLoadingExec(false)
    }
  }, [id, query])

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login')
      return
    }
    if (!id) {
      setError('Widget no válido')
      setLoadingMeta(false)
      return
    }

    let cancelled = false
    setQuery(null)
    setResult(null)
    autoRanForId.current = null
    ;(async () => {
      setLoadingMeta(true)
      setError(null)
      try {
        const raw = await apiClient.getQuery(id)
        if (cancelled) return
        const q = normalizeSavedQuery(raw as Record<string, unknown>)
        setQuery(q)
      } catch (e) {
        if (!cancelled) setError(getApiErrorMessage(e, 'Error al ejecutar el widget'))
      } finally {
        if (!cancelled) setLoadingMeta(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [isAuthenticated, id, router])

  useEffect(() => {
    if (!query || loadingMeta || !id) return
    if (autoRanForId.current === id) return
    autoRanForId.current = id
    void runExecute()
  }, [query, loadingMeta, id, runExecute])

  if (!isAuthenticated) return null

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      <header className="border-b border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="min-w-0">
            <AppBreadcrumb
              items={[
                { label: 'Dashboard', href: '/dashboard' },
                { label: 'Mis Widgets', href: '/queries' },
                { label: query?.name ?? 'Ejecutar' },
              ]}
            />
            <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
              Ejecutar widget
            </h1>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/queries/${id}/edit`}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:text-gray-200 dark:hover:bg-slate-700"
            >
              Editar
            </Link>
            <Link
              href="/queries"
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:text-gray-200 dark:hover:bg-slate-700"
            >
              Volver a Mis Widgets
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
        {loadingMeta ? (
          <p className="text-center text-gray-600 dark:text-gray-300">Cargando widget…</p>
        ) : query ? (
          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{query.name}</h2>
            {query.description ? (
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{query.description}</p>
            ) : null}
            <div className="mt-4">
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                SQL guardado
              </p>
              <pre className="max-h-48 overflow-auto rounded-md bg-gray-100 p-3 font-mono text-xs text-gray-800 dark:bg-slate-900 dark:text-gray-200">
                {query.sql || '—'}
              </pre>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={loadingExec}
                onClick={() => void runExecute()}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                {loadingExec ? 'Ejecutando…' : 'Ejecutar de nuevo'}
              </button>
            </div>
          </section>
        ) : null}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}

        {loadingExec && query && (
          <p className="text-center text-sm text-blue-600 dark:text-blue-400">Ejecutando consulta…</p>
        )}

        {result && result.column_names.length > 0 && (
          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Resultados</h2>
            </div>
            <DataResultTable results={result} />
          </section>
        )}

        {result && result.column_names.length === 0 && result.total_rows === 0 && !loadingExec && (
          <p className="text-center text-sm text-gray-600 dark:text-gray-300">
            La consulta no devolvió filas.
          </p>
        )}
      </main>
    </div>
  )
}
