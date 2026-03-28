export const TABLE_ACCENT_STORAGE_KEY = 'vgd_table_accent'

export type TableAccentId =
  | 'blue'
  | 'emerald'
  | 'violet'
  | 'amber'
  | 'rose'
  | 'cyan'
  | 'orange'
  | 'slate'

export type TableAccentClasses = {
  outer: string
  headerBar: string
  headerBarText: string
  toolbarMuted: string
  sqlBlock: string
  theadRow: string
  thText: string
  rowEven: string
  rowOdd: string
  cellText: string
  footerBar: string
  footerLink: string
}

export const TABLE_ACCENT_OPTIONS: {
  id: TableAccentId
  label: string
  swatch: string
}[] = [
  { id: 'blue', label: 'Azul', swatch: 'bg-blue-600' },
  { id: 'emerald', label: 'Verde', swatch: 'bg-emerald-600' },
  { id: 'violet', label: 'Violeta', swatch: 'bg-violet-600' },
  { id: 'amber', label: 'Ámbar', swatch: 'bg-amber-500' },
  { id: 'rose', label: 'Rosa', swatch: 'bg-rose-600' },
  { id: 'cyan', label: 'Cian', swatch: 'bg-cyan-600' },
  { id: 'orange', label: 'Naranja', swatch: 'bg-orange-600' },
  { id: 'slate', label: 'Gris', swatch: 'bg-slate-500' },
]

/** Color principal para Recharts (bar / línea / área) alineado con el acento de UI. */
export const TABLE_ACCENT_CHART_HEX: Record<TableAccentId, string> = {
  blue: '#2563eb',
  emerald: '#059669',
  violet: '#7c3aed',
  amber: '#d97706',
  rose: '#e11d48',
  cyan: '#0891b2',
  orange: '#ea580c',
  slate: '#64748b',
}

const VALID_IDS = new Set(TABLE_ACCENT_OPTIONS.map((o) => o.id))

/** Lee `table_accent` del JSON del widget; `null`/ausente/inválido → usar acento global. */
export function parseWidgetTableAccent(config: Record<string, unknown>): TableAccentId | undefined {
  const raw = config.table_accent
  if (raw === null || raw === undefined) return undefined
  if (typeof raw === 'string' && VALID_IDS.has(raw as TableAccentId)) {
    return raw as TableAccentId
  }
  return undefined
}

export function readStoredTableAccent(): TableAccentId {
  if (typeof window === 'undefined') return 'blue'
  const v = localStorage.getItem(TABLE_ACCENT_STORAGE_KEY)
  if (v && VALID_IDS.has(v as TableAccentId)) return v as TableAccentId
  return 'blue'
}

export function persistTableAccent(id: TableAccentId): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(TABLE_ACCENT_STORAGE_KEY, id)
  window.dispatchEvent(new Event('vgd-table-accent-change'))
}

const TABLE_ACCENT_CLASS_MAP: Record<TableAccentId, TableAccentClasses> = {
  blue: {
    outer: 'border-gray-200 dark:border-slate-600',
    headerBar: 'border-gray-200 bg-gray-50 dark:border-slate-600 dark:bg-slate-700',
    headerBarText: 'text-gray-700 dark:text-slate-200',
    toolbarMuted:
      'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200',
    sqlBlock: 'bg-gray-900 text-green-400',
    theadRow: 'border-gray-200 bg-gray-100 dark:border-slate-600 dark:bg-slate-700',
    thText: 'text-gray-800 dark:text-slate-100',
    rowEven: 'border-gray-100 bg-white dark:border-slate-700/60 dark:bg-slate-800',
    rowOdd: 'border-gray-100 bg-gray-50 dark:border-slate-700/60 dark:bg-slate-900/85',
    cellText: 'text-gray-900 dark:text-slate-100',
    footerBar: 'border-gray-200 bg-gray-50 dark:border-slate-600 dark:bg-slate-700/90',
    footerLink: 'text-blue-600 hover:underline dark:text-blue-300 dark:hover:text-blue-200',
  },
  emerald: {
    outer: 'border-emerald-200/90 dark:border-emerald-800/80',
    headerBar: 'border-emerald-200/80 bg-emerald-50/90 dark:border-emerald-800/60 dark:bg-emerald-950/45',
    headerBarText: 'text-emerald-900 dark:text-emerald-100',
    toolbarMuted:
      'text-emerald-700/80 hover:text-emerald-900 dark:text-emerald-300/90 dark:hover:text-emerald-100',
    sqlBlock: 'bg-emerald-950 text-emerald-300',
    theadRow: 'border-emerald-200/90 bg-emerald-100/70 dark:border-emerald-800/50 dark:bg-emerald-950/35',
    thText: 'text-emerald-950 dark:text-emerald-50',
    rowEven: 'border-emerald-100/80 bg-white dark:border-emerald-900/25 dark:bg-slate-800',
    rowOdd: 'border-emerald-100/80 bg-emerald-50/40 dark:border-emerald-900/20 dark:bg-slate-900/85',
    cellText: 'text-gray-900 dark:text-slate-100',
    footerBar: 'border-emerald-200/80 bg-emerald-50/80 dark:border-emerald-800/50 dark:bg-emerald-950/40',
    footerLink: 'text-emerald-700 hover:underline dark:text-emerald-400 dark:hover:text-emerald-300',
  },
  violet: {
    outer: 'border-violet-200/90 dark:border-violet-800/80',
    headerBar: 'border-violet-200/80 bg-violet-50/90 dark:border-violet-800/60 dark:bg-violet-950/45',
    headerBarText: 'text-violet-900 dark:text-violet-100',
    toolbarMuted:
      'text-violet-700/80 hover:text-violet-900 dark:text-violet-300/90 dark:hover:text-violet-100',
    sqlBlock: 'bg-violet-950 text-violet-300',
    theadRow: 'border-violet-200/90 bg-violet-100/70 dark:border-violet-800/50 dark:bg-violet-950/35',
    thText: 'text-violet-950 dark:text-violet-50',
    rowEven: 'border-violet-100/80 bg-white dark:border-violet-900/25 dark:bg-slate-800',
    rowOdd: 'border-violet-100/80 bg-violet-50/40 dark:border-violet-900/20 dark:bg-slate-900/85',
    cellText: 'text-gray-900 dark:text-slate-100',
    footerBar: 'border-violet-200/80 bg-violet-50/80 dark:border-violet-800/50 dark:bg-violet-950/40',
    footerLink: 'text-violet-700 hover:underline dark:text-violet-400 dark:hover:text-violet-300',
  },
  amber: {
    outer: 'border-amber-200/90 dark:border-amber-800/80',
    headerBar: 'border-amber-200/80 bg-amber-50/90 dark:border-amber-800/60 dark:bg-amber-950/45',
    headerBarText: 'text-amber-950 dark:text-amber-100',
    toolbarMuted:
      'text-amber-800/80 hover:text-amber-950 dark:text-amber-300/90 dark:hover:text-amber-100',
    sqlBlock: 'bg-amber-950 text-amber-200',
    theadRow: 'border-amber-200/90 bg-amber-100/70 dark:border-amber-800/50 dark:bg-amber-950/35',
    thText: 'text-amber-950 dark:text-amber-50',
    rowEven: 'border-amber-100/80 bg-white dark:border-amber-900/25 dark:bg-slate-800',
    rowOdd: 'border-amber-100/80 bg-amber-50/50 dark:border-amber-900/20 dark:bg-slate-900/85',
    cellText: 'text-gray-900 dark:text-slate-100',
    footerBar: 'border-amber-200/80 bg-amber-50/80 dark:border-amber-800/50 dark:bg-amber-950/40',
    footerLink: 'text-amber-800 hover:underline dark:text-amber-400 dark:hover:text-amber-300',
  },
  rose: {
    outer: 'border-rose-200/90 dark:border-rose-800/80',
    headerBar: 'border-rose-200/80 bg-rose-50/90 dark:border-rose-800/60 dark:bg-rose-950/45',
    headerBarText: 'text-rose-900 dark:text-rose-100',
    toolbarMuted:
      'text-rose-700/80 hover:text-rose-900 dark:text-rose-300/90 dark:hover:text-rose-100',
    sqlBlock: 'bg-rose-950 text-rose-300',
    theadRow: 'border-rose-200/90 bg-rose-100/70 dark:border-rose-800/50 dark:bg-rose-950/35',
    thText: 'text-rose-950 dark:text-rose-50',
    rowEven: 'border-rose-100/80 bg-white dark:border-rose-900/25 dark:bg-slate-800',
    rowOdd: 'border-rose-100/80 bg-rose-50/40 dark:border-rose-900/20 dark:bg-slate-900/85',
    cellText: 'text-gray-900 dark:text-slate-100',
    footerBar: 'border-rose-200/80 bg-rose-50/80 dark:border-rose-800/50 dark:bg-rose-950/40',
    footerLink: 'text-rose-700 hover:underline dark:text-rose-400 dark:hover:text-rose-300',
  },
  cyan: {
    outer: 'border-cyan-200/90 dark:border-cyan-800/80',
    headerBar: 'border-cyan-200/80 bg-cyan-50/90 dark:border-cyan-800/60 dark:bg-cyan-950/45',
    headerBarText: 'text-cyan-900 dark:text-cyan-100',
    toolbarMuted:
      'text-cyan-700/80 hover:text-cyan-900 dark:text-cyan-300/90 dark:hover:text-cyan-100',
    sqlBlock: 'bg-cyan-950 text-cyan-300',
    theadRow: 'border-cyan-200/90 bg-cyan-100/70 dark:border-cyan-800/50 dark:bg-cyan-950/35',
    thText: 'text-cyan-950 dark:text-cyan-50',
    rowEven: 'border-cyan-100/80 bg-white dark:border-cyan-900/25 dark:bg-slate-800',
    rowOdd: 'border-cyan-100/80 bg-cyan-50/40 dark:border-cyan-900/20 dark:bg-slate-900/85',
    cellText: 'text-gray-900 dark:text-slate-100',
    footerBar: 'border-cyan-200/80 bg-cyan-50/80 dark:border-cyan-800/50 dark:bg-cyan-950/40',
    footerLink: 'text-cyan-700 hover:underline dark:text-cyan-400 dark:hover:text-cyan-300',
  },
  orange: {
    outer: 'border-orange-200/90 dark:border-orange-800/80',
    headerBar: 'border-orange-200/80 bg-orange-50/90 dark:border-orange-800/60 dark:bg-orange-950/45',
    headerBarText: 'text-orange-950 dark:text-orange-100',
    toolbarMuted:
      'text-orange-800/80 hover:text-orange-950 dark:text-orange-300/90 dark:hover:text-orange-100',
    sqlBlock: 'bg-orange-950 text-orange-300',
    theadRow: 'border-orange-200/90 bg-orange-100/70 dark:border-orange-800/50 dark:bg-orange-950/35',
    thText: 'text-orange-950 dark:text-orange-50',
    rowEven: 'border-orange-100/80 bg-white dark:border-orange-900/25 dark:bg-slate-800',
    rowOdd: 'border-orange-100/80 bg-orange-50/40 dark:border-orange-900/20 dark:bg-slate-900/85',
    cellText: 'text-gray-900 dark:text-slate-100',
    footerBar: 'border-orange-200/80 bg-orange-50/80 dark:border-orange-800/50 dark:bg-orange-950/40',
    footerLink: 'text-orange-700 hover:underline dark:text-orange-400 dark:hover:text-orange-300',
  },
  slate: {
    outer: 'border-slate-200 dark:border-slate-600',
    headerBar: 'border-slate-200 bg-slate-100 dark:border-slate-600 dark:bg-slate-800',
    headerBarText: 'text-slate-800 dark:text-slate-200',
    toolbarMuted:
      'text-slate-600 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200',
    sqlBlock: 'bg-slate-900 text-slate-300',
    theadRow: 'border-slate-200 bg-slate-200/80 dark:border-slate-600 dark:bg-slate-800',
    thText: 'text-slate-900 dark:text-slate-100',
    rowEven: 'border-slate-100 bg-white dark:border-slate-700/60 dark:bg-slate-800',
    rowOdd: 'border-slate-100 bg-slate-50 dark:border-slate-700/60 dark:bg-slate-900/85',
    cellText: 'text-gray-900 dark:text-slate-100',
    footerBar: 'border-slate-200 bg-slate-100 dark:border-slate-600 dark:bg-slate-800/90',
    footerLink: 'text-slate-700 hover:underline dark:text-slate-300 dark:hover:text-slate-200',
  },
}

export function tableAccentClasses(id: TableAccentId): TableAccentClasses {
  return TABLE_ACCENT_CLASS_MAP[id] ?? TABLE_ACCENT_CLASS_MAP.blue
}
