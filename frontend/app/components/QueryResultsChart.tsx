'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { columnHeaderLabel } from '@/lib/columnLabels'
import type { QueryResultData } from '@/types'

const tooltipStyle = {
  backgroundColor: 'rgba(15, 23, 42, 0.95)',
  border: '1px solid rgb(51 65 85)',
  borderRadius: '8px',
  fontSize: '12px',
}

const AXIS = '#64748b'
const GRID = '#334155'
const PALETTE = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b']

function numericRatio(rows: Record<string, unknown>[], col: string, limit = 20): number {
  const slice = rows.slice(0, limit)
  let ok = 0
  let tot = 0
  for (const r of slice) {
    const v = r[col]
    if (v === null || v === undefined || v === '') continue
    tot++
    if (typeof v === 'number' && !Number.isNaN(v)) ok++
    else if (typeof v === 'string' && v.trim() !== '' && !Number.isNaN(Number(v))) ok++
  }
  return tot === 0 ? 0 : ok / tot
}

type ChartSpec = {
  chartData: Record<string, string | number>[]
  xKey: string
  yKeys: string[]
  preferLine: boolean
}

function buildChartSpec(data: QueryResultData): ChartSpec | null {
  const { rows, column_names } = data
  if (!rows.length || !column_names.length) return null

  const numericCols = column_names.filter((c) => numericRatio(rows, c) >= 0.65)
  const catCols = column_names.filter((c) => !numericCols.includes(c))

  let xKey = catCols[0] ?? column_names[0]
  let yKeys = numericCols.filter((k) => k !== xKey)

  if (yKeys.length === 0 && numericCols.length >= 2) {
    xKey = numericCols[0]
    yKeys = numericCols.slice(1, 4)
  } else if (yKeys.length === 0 && numericCols.length === 1) {
    const y = numericCols[0]
    const chartData = rows.map((r, i) => ({
      __x: `Fila ${i + 1}`,
      [y]: Number(r[y]) || 0,
    }))
    return { chartData, xKey: '__x', yKeys: [y], preferLine: rows.length > 8 }
  }

  if (yKeys.length === 0) return null

  yKeys = yKeys.slice(0, 4)

  const chartData = rows.map((r) => {
    const out: Record<string, string | number> = {}
    const xv = r[xKey]
    out[xKey] = xv === null || xv === undefined ? '—' : String(xv)
    for (const y of yKeys) {
      const raw = r[y]
      const n = typeof raw === 'number' ? raw : Number(raw)
      out[y] = Number.isFinite(n) ? n : 0
    }
    return out
  })

  const preferLine = rows.length > 6 && numericRatio(rows, xKey, 10) >= 0.5

  return { chartData, xKey, yKeys, preferLine }
}

type Props = {
  data: QueryResultData
}

function ResultsChartTooltip({
  active,
  payload,
  label,
  labelsEs,
}: {
  active?: boolean
  payload?: Array<{ dataKey?: string | number; name?: string; value?: unknown; color?: string }>
  label?: string
  labelsEs?: Record<string, string>
}) {
  if (!active || !payload?.length) return null
  return (
    <div style={tooltipStyle}>
      <p style={{ color: '#e2e8f0', marginBottom: 4 }}>{label}</p>
      {payload.map((p) => {
        const key = p.dataKey != null ? String(p.dataKey) : ''
        const title = key ? columnHeaderLabel(key, labelsEs) : (p.name ?? '')
        return (
          <p key={key || String(p.name)} style={{ color: '#e2e8f0', margin: 0 }}>
            <span style={{ color: p.color ?? '#94a3b8' }}>●</span> {title}: {String(p.value ?? '')}
          </p>
        )
      })}
    </div>
  )
}

export function QueryResultsChart({ data }: Props) {
  const spec = buildChartSpec(data)

  if (!data.rows.length) {
    return (
      <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
        No hay filas para graficar.
      </p>
    )
  }

  if (!spec) {
    return (
      <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
        Este resultado no tiene columnas numéricas claras para una gráfica. Usa la vista de tabla.
      </p>
    )
  }

  const { chartData, xKey, yKeys, preferLine } = spec
  const ChartComponent = preferLine ? LineChart : BarChart
  const labelsEs = data.column_labels_es

  return (
    <div className="h-[320px] w-full min-w-0 pt-2">
      <ResponsiveContainer width="100%" height="100%">
        <ChartComponent data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis
            dataKey={xKey}
            stroke={AXIS}
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            interval={chartData.length > 16 ? 'preserveStartEnd' : 0}
            angle={chartData.length > 10 ? -35 : 0}
            textAnchor={chartData.length > 10 ? 'end' : 'middle'}
            height={chartData.length > 10 ? 64 : 32}
            label={
              xKey === '__x'
                ? undefined
                : {
                    value: columnHeaderLabel(xKey, labelsEs),
                    position: 'insideBottom',
                    offset: chartData.length > 10 ? -8 : -2,
                    style: { fill: '#94a3b8', fontSize: 11 },
                  }
            }
          />
          <YAxis stroke={AXIS} tick={{ fill: '#94a3b8', fontSize: 11 }} />
          <Tooltip
            content={<ResultsChartTooltip labelsEs={labelsEs} />}
            cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }}
          />
          <Legend wrapperStyle={{ fontSize: '12px' }} />
          {preferLine
            ? yKeys.map((k, i) => (
                <Line
                  key={k}
                  type="monotone"
                  dataKey={k}
                  name={columnHeaderLabel(k, labelsEs)}
                  stroke={PALETTE[i % PALETTE.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              ))
            : yKeys.map((k, i) => (
                <Bar
                  key={k}
                  dataKey={k}
                  name={columnHeaderLabel(k, labelsEs)}
                  fill={PALETTE[i % PALETTE.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
        </ChartComponent>
      </ResponsiveContainer>
    </div>
  )
}
