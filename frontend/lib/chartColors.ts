import type { TableAccentId } from '@/lib/tableAccent'
import { TABLE_ACCENT_CHART_HEX } from '@/lib/tableAccent'

export function chartHexForAccent(id: TableAccentId): string {
  return TABLE_ACCENT_CHART_HEX[id] ?? TABLE_ACCENT_CHART_HEX.blue
}

/** Normaliza #rgb → #rrggbb; devuelve undefined si no es hex válido. */
export function sanitizeHexColor(input: string): string | undefined {
  const s = input.trim()
  if (/^#[0-9a-fA-F]{6}$/.test(s)) return s.toLowerCase()
  if (/^#[0-9a-fA-F]{3}$/.test(s)) {
    const a = s.slice(1)
    return `#${a[0]}${a[0]}${a[1]}${a[1]}${a[2]}${a[2]}`.toLowerCase()
  }
  return undefined
}

export function parseHexColorMap(raw: unknown): Record<string, string> {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  const out: Record<string, string> = {}
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof v !== 'string') continue
    const h = sanitizeHexColor(v)
    if (h) out[k] = h
  }
  return out
}

/** Series adicionales cuando hay varias métricas (la primera usa el acento). */
const SERIES_FALLBACK_HEX = ['#7c3aed', '#0891b2', '#ea580c', '#db2777'] as const

/**
 * Un color por serie: overrides del usuario; si no, primera = acento y el resto paleta fija.
 */
export function seriesStrokeFills(
  primaryHex: string,
  yKeys: string[],
  overrides?: Record<string, string>
): string[] {
  return yKeys.map((k, i) => {
    const o = overrides?.[k]
    if (o && sanitizeHexColor(o)) return sanitizeHexColor(o)!
    if (yKeys.length === 1) return primaryHex
    if (i === 0) return primaryHex
    return SERIES_FALLBACK_HEX[(i - 1) % SERIES_FALLBACK_HEX.length]
  })
}
