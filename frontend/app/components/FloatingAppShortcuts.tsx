'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useCallback, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { BarChart3, GripVertical, LayoutDashboard, LayoutGrid, Settings, X } from 'lucide-react'
import { QuickAccessStats, type DashboardStatsPayload } from '@/components/QuickAccessStats'
import { useAuth } from '@/hooks/useAuth'
import { apiClient } from '@/services/api'
import { cn } from '@/lib/utils'

const SHORTCUT_ITEMS = [
  {
    href: '/queries',
    title: 'Mis Widgets',
    description: 'Consultas guardadas listas para ejecutar o añadir al dashboard',
    icon: BarChart3,
    buttonClass: 'bg-blue-600 hover:bg-blue-700 text-white',
    cta: 'Ver Mis Widgets',
  },
  {
    href: '/dashboard/widgets',
    title: 'Configurar widgets',
    description: 'Añadir al dashboard, vista previa y tipo de gráfica',
    icon: LayoutDashboard,
    buttonClass: 'bg-purple-600 hover:bg-purple-700 text-white',
    cta: 'Abrir gestión',
  },
  {
    href: '/dashboard?organize=1',
    title: 'Organizar tablero',
    description: 'Mover, redimensionar, actualizar o quitar widgets del dashboard',
    icon: GripVertical,
    buttonClass: 'bg-violet-600 hover:bg-violet-700 text-white',
    cta: 'Modo organizar',
  },
  {
    href: '/settings',
    title: 'Configuración',
    description: 'Parámetros y preferencias',
    icon: Settings,
    buttonClass: 'bg-slate-600 hover:bg-slate-700 text-white dark:bg-slate-700 dark:hover:bg-slate-600',
    cta: 'Configurar',
  },
] as const

/**
 * FAB inferior derecho (encima del chat) que abre un diálogo con accesos a Mis Widgets,
 * configuración de widgets, organizar tablero y ajustes — mismo patrón que FloatingChatWidget.
 */
export function FloatingAppShortcuts() {
  const pathname = usePathname()
  const { isAuthenticated } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const [stats, setStats] = useState<DashboardStatsPayload | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState<string | null>(null)

  const loadStats = useCallback(async () => {
    setStatsLoading(true)
    setStatsError(null)
    try {
      const data = await apiClient.getDashboardStats()
      setStats(data)
    } catch (e: unknown) {
      setStatsError(e instanceof Error ? e.message : 'No se pudieron cargar las estadísticas')
    } finally {
      setStatsLoading(false)
    }
  }, [])

  const onOpenChange = useCallback(
    (open: boolean) => {
      setMenuOpen(open)
      if (open) void loadStats()
    },
    [loadStats]
  )

  const hide = !isAuthenticated || pathname?.startsWith('/auth')

  /** En /chat el FAB del agente no se muestra: este botón pasa a la esquina inferior. */
  const chatFabVisible = pathname !== '/chat'
  const fabPosition = chatFabVisible
    ? 'bottom-[5.25rem] right-4 sm:bottom-[5.75rem] sm:right-6'
    : 'bottom-4 right-4 sm:bottom-6 sm:right-6'
  /** Por encima del FAB de dashboard (9.5rem + alto FAB + margen). */
  const panelBottom = chatFabVisible
    ? 'bottom-[13.75rem] right-4 sm:bottom-[14.25rem] sm:right-6'
    : 'bottom-[9.5rem] right-4 sm:bottom-[10.25rem] sm:right-6'

  if (hide) return null

  return (
    <Dialog.Root open={menuOpen} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            'fixed inset-0 z-[186] bg-slate-950/55 backdrop-blur-[2px]',
            'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'duration-200'
          )}
        />
        <Dialog.Content
          className={cn(
            'fixed z-[187] flex max-h-[min(82vh,620px)] w-[min(calc(100vw-2rem),380px)] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl',
            panelBottom,
            'dark:border-slate-600 dark:bg-slate-900',
            'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-bottom-2 data-[state=open]:slide-in-from-bottom-2',
            'duration-200 focus:outline-none'
          )}
        >
          <Dialog.Title className="sr-only">Accesos rápidos</Dialog.Title>
          <Dialog.Description className="sr-only">
            Resumen de estadísticas, Mis Widgets, configurar widgets, organizar tablero y configuración.
          </Dialog.Description>

          <div className="flex items-center justify-between border-b border-gray-100 bg-gradient-to-r from-slate-700 to-slate-800 px-4 py-3 text-white dark:from-slate-800 dark:to-slate-900">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">Accesos rápidos</p>
              <p className="truncate text-xs text-white/75">Widgets, dashboard y ajustes</p>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                className="rounded-lg p-2 text-white/90 transition hover:bg-white/10"
                aria-label="Cerrar menú"
              >
                <X className="h-5 w-5" />
              </button>
            </Dialog.Close>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            <QuickAccessStats
              stats={stats}
              loading={statsLoading}
              error={statsError}
              onRefresh={loadStats}
              compact
            />
            <ul className="mt-3 space-y-3">
              {SHORTCUT_ITEMS.map(({ href, title, description, icon: Icon, buttonClass, cta }) => (
                <li key={href}>
                  <Dialog.Close asChild>
                    <Link
                      href={href}
                      className="block rounded-xl border border-gray-200 bg-gray-50/80 p-4 transition hover:border-violet-300 hover:bg-white dark:border-slate-600 dark:bg-slate-800/80 dark:hover:border-violet-600 dark:hover:bg-slate-800"
                    >
                      <div className="flex gap-3">
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-slate-700 shadow-sm dark:bg-slate-700 dark:text-slate-200">
                          <Icon className="h-5 w-5" aria-hidden />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="font-semibold text-gray-900 dark:text-white">{title}</p>
                          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{description}</p>
                          <span
                            className={cn(
                              'mt-3 inline-block rounded-lg px-3 py-1.5 text-xs font-medium transition',
                              buttonClass
                            )}
                          >
                            {cta}
                          </span>
                        </div>
                      </div>
                    </Link>
                  </Dialog.Close>
                </li>
              ))}
            </ul>
          </div>
        </Dialog.Content>
      </Dialog.Portal>

      <Dialog.Trigger asChild>
        <button
          type="button"
          className={cn(
            'fixed z-[193] flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition',
            'bg-slate-700 text-white hover:bg-slate-800 focus:outline-none focus:ring-4 focus:ring-slate-500/35',
            'dark:bg-slate-600 dark:hover:bg-slate-500',
            fabPosition
          )}
          aria-label="Abrir accesos rápidos"
        >
          <LayoutGrid className="h-7 w-7" strokeWidth={2} />
        </button>
      </Dialog.Trigger>
    </Dialog.Root>
  )
}
