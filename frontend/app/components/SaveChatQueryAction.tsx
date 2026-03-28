'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useQuery } from '@/hooks/useQuery'

type Props = {
  userQuestion: string
  sql: string
}

function defaultTitleFromQuestion(q: string): string {
  const t = q.trim()
  if (!t) return 'Consulta desde chat'
  return t.length > 80 ? `${t.slice(0, 77)}…` : t
}

export function SaveChatQueryAction({ userQuestion, sql }: Props) {
  const { createQuery } = useQuery()
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState(() => defaultTitleFromQuestion(userQuestion))
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const handleSave = async () => {
    const t = title.trim()
    if (!t) {
      setErr('Indica un título')
      return
    }
    setSaving(true)
    setErr(null)
    try {
      await createQuery({
        title: t,
        original_question: userQuestion.trim() || t,
        sql_text: sql,
        chart_type: 'table',
        chart_config: {},
        tags: [],
      })
      setDone(true)
      setOpen(false)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'No se pudo guardar'
      setErr(msg)
    } finally {
      setSaving(false)
    }
  }

  if (done) {
    return (
      <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">
        <span>Widget guardado en Mis Widgets.</span>{' '}
        <Link href="/queries" className="font-medium underline hover:no-underline">
          Ver Mis Widgets
        </Link>
      </div>
    )
  }

  return (
    <div className="mt-3 border-t border-gray-200 pt-3 dark:border-slate-600">
      {!open ? (
        <button
          type="button"
          onClick={() => {
            setOpen(true)
            setTitle(defaultTitleFromQuestion(userQuestion))
            setErr(null)
          }}
          className="text-sm font-medium text-violet-600 underline transition hover:text-violet-800 dark:text-violet-400 dark:hover:text-violet-300"
        >
          Guardar en Mis Widgets
        </button>
      ) : (
        <div className="space-y-2 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-slate-600 dark:bg-slate-900/50">
          <p className="text-xs text-gray-600 dark:text-gray-400">
            Se guardará el SQL que ejecutó el agente. Puedes editar el título.
          </p>
          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
            Título
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-900 dark:border-slate-600 dark:bg-slate-800 dark:text-white"
            />
          </label>
          {err && <p className="text-xs text-red-600 dark:text-red-400">{err}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={saving}
              onClick={() => void handleSave()}
              className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-violet-700 disabled:opacity-50"
            >
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => setOpen(false)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-100 dark:border-slate-600 dark:text-gray-300 dark:hover:bg-slate-700"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
