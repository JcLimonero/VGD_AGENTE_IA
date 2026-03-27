'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'

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

  console.log('LoginPage render - isAuthenticated:', isAuthenticated)

  // Redirigir si ya está autenticado (usando useEffect para evitar setState durante render)
  useEffect(() => {
    console.log('useEffect - isAuthenticated:', isAuthenticated)
    if (isAuthenticated) {
      console.log('Redirigiendo desde useEffect al dashboard')
      router.push('/dashboard')
    }
  }, [isAuthenticated, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')

    try {
      console.log('Intentando login con:', email, password)
      const success = await login(email, password)
      console.log('Login success:', success)
      if (!success) {
        setError('Credenciales inválidas')
      }
      // La redirección se maneja en el useEffect cuando isAuthenticated cambie
    } catch (err: any) {
      console.error('Error en login:', err)
      setError(err.message || 'Error al iniciar sesión')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-slate-900 dark:to-slate-800">
      <div className="w-full max-w-md">
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-8">
          <div className="mb-6 flex justify-center">
            <AppBreadcrumb
              items={[
                { label: 'Inicio', href: '/' },
                { label: 'Iniciar sesión' },
              ]}
            />
          </div>
          <h1 className="text-2xl font-bold text-center mb-8 text-gray-900 dark:text-white">
            VGD Agente IA
          </h1>

          {error && (
            <div className="mb-6 p-4 bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded-lg text-red-600 dark:text-red-200 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-slate-700 dark:text-white"
                placeholder="usuario@ejemplo.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Contraseña
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-slate-700 dark:text-white"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 rounded-lg transition"
            >
              {isLoading ? 'Cargando...' : 'Iniciar Sesión'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-600 dark:text-gray-400">
            ¿No tienes cuenta?{' '}
            <Link href="/auth/register" className="text-blue-600 hover:underline">
              Regístrate aquí
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
