export const THEME_STORAGE_KEY = 'vgd_theme'

export type ThemeChoice = 'system' | 'light' | 'dark'

/** Aplica tema y persiste (excepto sistema: borra la clave). Solo en cliente. */
export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement
  if (choice === 'dark') {
    root.classList.add('dark')
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    return
  }
  if (choice === 'light') {
    root.classList.remove('dark')
    localStorage.setItem(THEME_STORAGE_KEY, 'light')
    return
  }
  localStorage.removeItem(THEME_STORAGE_KEY)
  root.classList.toggle('dark', window.matchMedia('(prefers-color-scheme: dark)').matches)
}

/** Primera carga: lee localStorage o preferencia del sistema. */
export function initThemeFromStorage(): void {
  const root = document.documentElement
  const v = localStorage.getItem(THEME_STORAGE_KEY)
  if (v === 'dark') {
    root.classList.add('dark')
    return
  }
  if (v === 'light') {
    root.classList.remove('dark')
    return
  }
  root.classList.toggle('dark', window.matchMedia('(prefers-color-scheme: dark)').matches)
}

export function readStoredThemeChoice(): ThemeChoice {
  if (typeof window === 'undefined') return 'system'
  const v = localStorage.getItem(THEME_STORAGE_KEY)
  if (v === 'dark' || v === 'light') return v
  return 'system'
}
