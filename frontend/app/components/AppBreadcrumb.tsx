'use client'

import Link from 'next/link'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export type BreadcrumbItem = {
  label: string
  href?: string
}

type AppBreadcrumbProps = {
  items: BreadcrumbItem[]
  className?: string
  /** Clases para el último segmento (por ejemplo, como título de página). */
  currentClassName?: string
}

export function AppBreadcrumb({ items, className, currentClassName }: AppBreadcrumbProps) {
  if (items.length === 0) return null

  return (
    <nav aria-label="Ruta de navegación" className={cn(className)}>
      <ol className="m-0 flex list-none flex-wrap items-center gap-1.5 p-0 text-sm">
        {items.map((item, i) => {
          const isLast = i === items.length - 1
          const content =
            item.href && !isLast ? (
              <Link
                href={item.href}
                className="font-medium text-blue-600 transition hover:underline dark:text-blue-400"
              >
                {item.label}
              </Link>
            ) : (
              <span
                className={cn(
                  'font-medium text-gray-700 dark:text-gray-200',
                  isLast && currentClassName
                )}
                aria-current={isLast ? 'page' : undefined}
              >
                {item.label}
              </span>
            )

          return (
            <li key={`${item.label}-${i}`} className="flex items-center gap-1.5">
              {i > 0 && (
                <ChevronRight
                  className="h-4 w-4 shrink-0 text-gray-400 dark:text-gray-500"
                  aria-hidden
                />
              )}
              {content}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
