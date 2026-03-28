'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import { applyTheme, readStoredThemeChoice, type ThemeChoice } from '@/lib/theme'

function apiBaseSummary(): string {
  const explicit = (process.env.NEXT_PUBLIC_API_BASE_URL || '').trim()
  if (explicit) return explicit.replace(/\/+$/, '')
  return '/api/upstream (proxy de Next.js hacia el backend)'
}

const themeOptions: { value: ThemeChoice; label: string; hint: string }[] = [
  { value: 'system', label: 'Sistema', hint: 'Sigue el modo claro u oscuro del dispositivo' },
  { value: 'light', label: 'Claro', hint: 'Interfaz con fondos claros' },
  { value: 'dark', label: 'Oscuro', hint: 'Interfaz con fondos oscuros' },
]

export default function SettingsPage() {
  const router = useRouter()
  const { user, isAuthenticated, logout } = useAuth()
  const [theme, setTheme] = useState<ThemeChoice>('system')
  const [themeReady, setThemeReady] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login')
      return
    }
    setTheme(readStoredThemeChoice())
    setThemeReady(true)
  }, [isAuthenticated, router])

  if (!isAuthenticated) return null

  const handleTheme = (choice: ThemeChoice) => {
    applyTheme(choice)
    setTheme(choice)
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      <header className="border-b border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="min-w-0">
            <AppBreadcrumb
              items={[
                { label: 'Dashboard', href: '/dashboard' },
                { label: 'Configuración' },
              ]}
            />
            <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">Configuración</h1>
          </div>
          <button
            type="button"
            onClick={() => {
              logout()
              router.push('/auth/login')
            }}
            className="rounded-lg bg-red-50 px-3 py-1.5 text-sm text-red-600 transition hover:bg-red-100 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50"
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-8 px-4 py-8 sm:px-6 lg:px-8">
        {/* Cuenta */}
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Cuenta</h2>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            Datos de la sesión actual (solo lectura).
          </p>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Nombre</dt>
              <dd className="font-medium text-gray-900 dark:text-white">{user?.name ?? '—'}</dd>
            </div>
            <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Correo</dt>
              <dd className="break-all font-medium text-gray-900 dark:text-white">{user?.email ?? '—'}</dd>
            </div>
            <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Rol</dt>
              <dd className="font-medium text-gray-900 dark:text-white">{user?.role ?? '—'}</dd>
            </div>
            <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between">
              <dt className="text-gray-500 dark:text-gray-400">ID de usuario</dt>
              <dd className="break-all font-mono text-xs text-gray-800 dark:text-gray-200">{user?.id ?? '—'}</dd>
            </div>
          </dl>
        </section>

        {/* Apariencia */}
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Apariencia</h2>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            El modo se guarda en este navegador.
          </p>
          <div className="mt-4 space-y-3" role="radiogroup" aria-label="Tema de la interfaz">
            {themeOptions.map((opt) => (
              <label
                key={opt.value}
                className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition ${
                  theme === opt.value
                    ? 'border-violet-500 bg-violet-50 dark:border-violet-500 dark:bg-violet-950/40'
                    : 'border-gray-200 hover:border-gray-300 dark:border-slate-600 dark:hover:border-slate-500'
                }`}
              >
                <input
                  type="radio"
                  name="theme"
                  value={opt.value}
                  checked={themeReady && theme === opt.value}
                  onChange={() => handleTheme(opt.value)}
                  className="mt-1 text-violet-600 focus:ring-violet-500"
                />
                <span>
                  <span className="block font-medium text-gray-900 dark:text-white">{opt.label}</span>
                  <span className="mt-0.5 block text-sm text-gray-600 dark:text-gray-400">{opt.hint}</span>
                </span>
              </label>
            ))}
          </div>
        </section>

        {/* Conexión API */}
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Conexión con la API</h2>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            Origen de las peticiones del frontend (útil en desarrollo).
          </p>
          <p className="mt-3 break-all rounded-md bg-gray-100 px-3 py-2 font-mono text-xs text-gray-800 dark:bg-slate-900 dark:text-gray-200">
            {apiBaseSummary()}
          </p>
          <p className="mt-2 text-xs text-gray-500 dark:text-gray-500">
            Para fijar otra URL, define <code className="rounded bg-gray-200 px-1 dark:bg-slate-700">NEXT_PUBLIC_API_BASE_URL</code> en{' '}
            <code className="rounded bg-gray-200 px-1 dark:bg-slate-700">frontend/.env.local</code>.
          </p>
        </section>

        {/* Accesos */}
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Accesos rápidos</h2>
          <ul className="mt-4 flex flex-wrap gap-3">
            {[
              { href: '/dashboard', label: 'Dashboard' },
              { href: '/chat', label: 'Chat' },
              { href: '/queries', label: 'Mis Widgets' },
              { href: '/dashboard/widgets', label: 'Widget showcase' },
            ].map((l) => (
              <li key={l.href}>
                <Link
                  href={l.href}
                  className="inline-flex rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:text-gray-200 dark:hover:bg-slate-700"
                >
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  )
}
