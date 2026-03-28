'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

/**
 * FAB que lleva al dashboard principal; se apila por encima de accesos rápidos y del chat.
 */
export function FloatingDashboardFab() {
  const pathname = usePathname()
  const { isAuthenticated } = useAuth()

  const hide =
    !isAuthenticated || pathname?.startsWith('/auth') || pathname === '/dashboard'

  /** En /chat no hay FAB de chat: este sube una franja. */
  const chatFabVisible = pathname !== '/chat'

  const fabPosition = chatFabVisible
    ? 'bottom-[9.5rem] right-4 sm:bottom-[10rem] sm:right-6'
    : 'bottom-[5.25rem] right-4 sm:bottom-[5.75rem] sm:right-6'

  if (hide) return null

  return (
    <Link
      href="/dashboard"
      className={cn(
        'fixed z-[194] flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition',
        'bg-emerald-700 text-white hover:bg-emerald-800 focus:outline-none focus:ring-4 focus:ring-emerald-500/35',
        'dark:bg-emerald-600 dark:hover:bg-emerald-500',
        fabPosition
      )}
      aria-label="Ir al dashboard"
    >
      <Home className="h-7 w-7" strokeWidth={2} />
    </Link>
  )
}
