'use client'

import { useEffect, useState } from 'react'
import { readStoredTableAccent, type TableAccentId } from '@/lib/tableAccent'

export function useTableAccentId(): TableAccentId {
  const [id, setId] = useState<TableAccentId>(() => readStoredTableAccent())

  useEffect(() => {
    const sync = () => setId(readStoredTableAccent())
    window.addEventListener('storage', sync)
    window.addEventListener('vgd-table-accent-change', sync)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener('vgd-table-accent-change', sync)
    }
  }, [])

  return id
}
