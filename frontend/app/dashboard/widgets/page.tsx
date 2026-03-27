'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
} from 'recharts'
import { useAuth } from '@/hooks/useAuth'
import { AppBreadcrumb } from '@/components/AppBreadcrumb'
import { DashboardWidgetsGrid } from '@/components/DashboardWidgetsGrid'
import { SavedQueryWidgetPanel } from '@/components/SavedQueryWidgetPanel'

const MONTHLY = [
  { mes: 'Ene', ventas: 42, meta: 40 },
  { mes: 'Feb', ventas: 38, meta: 42 },
  { mes: 'Mar', ventas: 55, meta: 45 },
  { mes: 'Abr', ventas: 48, meta: 48 },
  { mes: 'May', ventas: 62, meta: 50 },
  { mes: 'Jun', ventas: 58, meta: 52 },
]

const BY_AGENCY = [
  { agencia: 'Norte', unidades: 120 },
  { agencia: 'Sur', unidades: 86 },
  { agencia: 'Centro', unidades: 104 },
  { agencia: 'Occidente', unidades: 72 },
]

const MIX = [
  { name: 'Nuevos', value: 45, color: '#8b5cf6' },
  { name: 'Seminuevos', value: 32, color: '#3b82f6' },
  { name: 'Servicio', value: 23, color: '#10b981' },
]

const tooltipStyle = {
  backgroundColor: 'rgba(15, 23, 42, 0.95)',
  border: '1px solid rgb(51 65 85)',
  borderRadius: '8px',
  fontSize: '12px',
}

const axisStroke = '#64748b'
const gridStroke = '#334155'

export default function WidgetShowcasePage() {
  const router = useRouter()
  const { user, isAuthenticated, logout } = useAuth()
  const [widgetsRefresh, setWidgetsRefresh] = useState(0)

  useEffect(() => {
    if (!isAuthenticated) router.push('/auth/login')
  }, [isAuthenticated, router])

  if (!isAuthenticated) return null

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      <header className="border-b border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="min-w-0">
            <AppBreadcrumb
              items={[
                { label: 'Dashboard', href: '/dashboard' },
                { label: 'Widget showcase' },
              ]}
            />
            <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
              📈 Widget showcase
            </h1>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              Vincula consultas guardadas a widgets y revisa abajo los gráficos de demostración con Recharts.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600 dark:text-gray-300">{user?.name}</span>
            <Link
              href="/dashboard"
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-slate-600 dark:text-gray-200 dark:hover:bg-slate-700"
            >
              Volver
            </Link>
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
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-8 px-4 py-8 sm:px-6 lg:px-8">
        <SavedQueryWidgetPanel onWidgetAdded={() => setWidgetsRefresh((n) => n + 1)} />
        <DashboardWidgetsGrid refreshToken={widgetsRefresh} variant="showcase" />

        {/* Métricas (demo) */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Métricas</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: 'KPI ejemplo', value: '1.284', delta: '+12%', tone: 'text-emerald-600 dark:text-emerald-400' },
              { label: 'Promedio', value: '42', delta: 'mes', tone: 'text-slate-500 dark:text-slate-400' },
              { label: 'Alertas', value: '3', delta: 'activas', tone: 'text-amber-600 dark:text-amber-400' },
              { label: 'Cobertura', value: '98%', delta: 'objetivo 95%', tone: 'text-violet-600 dark:text-violet-400' },
            ].map((m) => (
              <div
                key={m.label}
                className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-slate-600 dark:bg-slate-800"
              >
                <p className="text-sm text-gray-500 dark:text-gray-400">{m.label}</p>
                <p className="mt-2 text-3xl font-bold tracking-tight text-gray-900 dark:text-white">{m.value}</p>
                <p className={`mt-1 text-xs font-medium ${m.tone}`}>{m.delta}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Gráficos */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-slate-600 dark:bg-slate-800">
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              Líneas — ventas vs meta
            </h2>
            <div className="h-[280px] w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={MONTHLY} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                  <XAxis dataKey="mes" stroke={axisStroke} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis stroke={axisStroke} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#e2e8f0' }} />
                  <Legend wrapperStyle={{ fontSize: '12px' }} />
                  <Line type="monotone" dataKey="ventas" name="Ventas" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="meta" name="Meta" stroke="#64748b" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-slate-600 dark:bg-slate-800">
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              Barras — unidades por agencia
            </h2>
            <div className="h-[280px] w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={BY_AGENCY} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                  <XAxis dataKey="agencia" stroke={axisStroke} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis stroke={axisStroke} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#e2e8f0' }} />
                  <Bar dataKey="unidades" name="Unidades" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-slate-600 dark:bg-slate-800">
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Área — tendencia</h2>
            <div className="h-[280px] w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={MONTHLY} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorVentas" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                  <XAxis dataKey="mes" stroke={axisStroke} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis stroke={axisStroke} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#e2e8f0' }} />
                  <Area type="monotone" dataKey="ventas" name="Ventas" stroke="#8b5cf6" fill="url(#colorVentas)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-slate-600 dark:bg-slate-800">
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Pie — mix (demo)</h2>
            <div className="h-[280px] w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={MIX}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={56}
                    outerRadius={88}
                    paddingAngle={2}
                    label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                  >
                    {MIX.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} stroke="transparent" />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#e2e8f0' }} />
                  <Legend wrapperStyle={{ fontSize: '12px' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}
