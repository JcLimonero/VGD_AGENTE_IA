'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'

/** Credenciales de prueba (coinciden con `agente_dwh/api_routes.py`). Quitar o vaciar antes de producción. */
const TEST_EMAIL = 'admin@example.com'
const TEST_PASSWORD = '123456'

export default function LoginPage() {
  const router = useRouter()
  const { login, isAuthenticated } = useAuth()
  const [email, setEmail] = useState(TEST_EMAIL)
  const [password, setPassword] = useState(TEST_PASSWORD)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [sessionNotice, setSessionNotice] = useState('')

  useEffect(() => {
    if (typeof window === 'undefined') return
    const q = new URLSearchParams(window.location.search)
    if (q.get('session') === 'expired') {
      setSessionNotice('Tu sesión expiró o caducó. Vuelve a iniciar sesión.')
    }
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/dashboard')
    }
  }, [isAuthenticated, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')

    try {
      const result = await login(email, password)
      if (!result.ok) {
        setError(result.error)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#1a1a1a] text-[#1a1a1a]">
      <div className="w-full max-w-md px-4 py-10">
        <div className="rounded-[32px] border border-[#0d0d0d] bg-[#f2f2f2] shadow-2xl shadow-black/20 p-8">
          <div className="flex flex-col items-center gap-4 text-center mb-8">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-[#1a1a1a] shadow-lg shadow-black/40">
              <img
                src="https://grupovanguardia.com/images/logo.png"
                alt="Grupo Vanguardia"
                className="h-12 w-auto"
              />
            </div>
            <h1 className="text-3xl font-semibold text-[#1a1a1a]">
              VGD Agente IA
            </h1>
          </div>

          {sessionNotice && (
            <div
              className="mb-6 rounded-lg border border-[#1a1a1a] bg-white p-4 text-sm text-[#1a1a1a]"
              role="status"
            >
              {sessionNotice}
            </div>
          )}

          {error && (
            <div
              className="mb-6 rounded-lg border border-red-600 bg-red-50 p-4 text-sm text-red-700"
              role="alert"
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-[#1a1a1a] mb-2">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-2xl border border-[#1a1a1a] bg-white px-4 py-3 text-[#1a1a1a] outline-none transition focus:border-[#1a1a1a] focus:ring-2 focus:ring-[#1a1a1a]/20"
                placeholder="usuario@ejemplo.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[#1a1a1a] mb-2">
                Contraseña
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-2xl border border-[#1a1a1a] bg-white px-4 py-3 text-[#1a1a1a] outline-none transition focus:border-[#1a1a1a] focus:ring-2 focus:ring-[#1a1a1a]/20"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full rounded-full bg-[#1a1a1a] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#333] disabled:opacity-50"
            >
              {isLoading ? 'Cargando...' : 'Iniciar Sesión'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
