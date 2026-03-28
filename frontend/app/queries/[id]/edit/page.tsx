'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { useQuery } from '@/hooks/useQuery'
import { apiClient } from '@/services/api'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import { normalizeSavedQuery, toQueryUpdatePayload } from '@/lib/savedQuery'

export default function EditQueryPage() {
  const params = useParams()
  const id = typeof params.id === 'string' ? params.id : params.id?.[0] ?? ''
  const router = useRouter()
  const { isAuthenticated } = useAuth()
  const { updateQuery } = useQuery()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [sql, setSql] = useState('')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login')
      return
    }
    if (!id) {
      setLoadError('Identificador de widget no válido')
      setLoading(false)
      return
    }

    let cancelled = false
    ;(async () => {
      setLoading(true)
      setLoadError(null)
      try {
        const raw = await apiClient.getQuery(id)
        const q = normalizeSavedQuery(raw as Record<string, unknown>)
        if (cancelled) return
        setName(q.name)
        setDescription(q.description)
        setSql(q.sql)
      } catch (e: unknown) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : 'No se pudo cargar el widget'
          setLoadError(msg)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [isAuthenticated, id, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaveError(null)
    if (!id) return
    setSaving(true)
    try {
      await updateQuery(id, toQueryUpdatePayload({ name, description, sql }))
      router.push('/queries')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Error al guardar'
      setSaveError(msg)
    } finally {
      setSaving(false)
    }
  }

  if (!isAuthenticated) return null

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      <header className="border-b border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto flex max-w-3xl flex-col gap-1 px-4 py-4 sm:px-6 lg:px-8">
          <AppBreadcrumb
            items={[
              { label: 'Dashboard', href: '/dashboard' },
              { label: 'Mis Widgets', href: '/queries' },
              { label: 'Editar widget' },
            ]}
          />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Editar widget</h1>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
        {loading ? (
          <p className="text-center text-gray-600 dark:text-gray-300">Cargando…</p>
        ) : loadError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200">
            {loadError}
            <div className="mt-4">
              <Link
                href="/queries"
                className="font-medium text-blue-600 underline dark:text-blue-400"
              >
                Volver a Mis Widgets
              </Link>
            </div>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="space-y-6 rounded-lg border border-gray-200 bg-white p-6 shadow dark:border-slate-600 dark:bg-slate-800"
          >
            {saveError && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200">
                {saveError}
              </div>
            )}

            <div>
              <label
                htmlFor="q-name"
                className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Título
              </label>
              <input
                id="q-name"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 focus:ring-2 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-white"
              />
            </div>

            <div>
              <label
                htmlFor="q-desc"
                className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Descripción / pregunta original
              </label>
              <textarea
                id="q-desc"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 focus:ring-2 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-white"
              />
            </div>

            <div>
              <label
                htmlFor="q-sql"
                className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                SQL (solo lectura)
              </label>
              <textarea
                id="q-sql"
                required
                rows={12}
                value={sql}
                onChange={(e) => setSql(e.target.value)}
                spellCheck={false}
                className="w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 font-mono text-sm text-gray-900 focus:ring-2 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-900 dark:text-gray-100"
              />
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? 'Guardando…' : 'Guardar cambios'}
              </button>
              <Link
                href="/queries"
                className="rounded-lg border border-gray-300 px-4 py-2 font-medium text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:text-gray-200 dark:hover:bg-slate-700"
              >
                Cancelar
              </Link>
            </div>
          </form>
        )}
      </main>
    </div>
  )
}
