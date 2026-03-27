'use client'

import { useEffect } from 'react'
import { initThemeFromStorage } from '@/lib/theme'

/** Aplica tema guardado o del sistema antes de pintar la app (evita flash si se amplía luego). */
export function ThemePreferenceBridge() {
  useEffect(() => {
    initThemeFromStorage()
  }, [])
  return null
}
