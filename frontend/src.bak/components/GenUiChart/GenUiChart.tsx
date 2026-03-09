/**
 * GenUiChart - renders charts from gen_ui payload (Recharts).
 */

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
} from 'recharts'
import { LINE_COLORS } from '../../constants'
import { extractChartsFromA2ui, LABEL_FROM_KIND } from '../../utils/chartData'
interface ChartSpec {
  kind?: string
  label?: string
  labels?: string[]
  values?: number[]
  x?: string[]
  y?: number[]
  chart_type?: string
}

function buildChartData(spec: ChartSpec): { name: string; value?: number; [k: string]: unknown }[] {
  const labels = spec.labels ?? spec.x ?? []
  const values = spec.values ?? spec.y ?? []
  return labels.map((l, j) => ({ name: l, value: values[j] ?? 0 }))
}

function SingleChart({
  spec,
  colorIndex,
}: {
  spec: ChartSpec
  colorIndex: number
}) {
  const title = spec.label ?? LABEL_FROM_KIND(spec.kind ?? 'chart')
  const isLine =
    spec.chart_type === 'line' ||
    (spec.x != null && spec.y != null && spec.labels == null)
  const data = buildChartData(spec)
  if (data.length === 0) return null

  const color = LINE_COLORS[colorIndex % LINE_COLORS.length]

  return (
    <div key={title}>
      <div
        style={{
          fontSize: 12,
          color: 'var(--muted)',
          marginBottom: 4,
        }}
      >
        {title}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        {isLine ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="value"
              stroke={color}
              name={title}
              dot={{ r: 2 }}
              strokeWidth={2}
            />
          </LineChart>
        ) : (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill={color} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

function MultiSeriesChart({
  data,
  seriesKeys,
  seriesLabels,
  isLine,
}: {
  data: { name: string; [k: string]: unknown }[]
  seriesKeys: string[]
  seriesLabels?: Record<string, string>
  isLine: boolean
}) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      {isLine ? (
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip />
          <Legend />
          {seriesKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={LINE_COLORS[i % LINE_COLORS.length]}
              name={seriesLabels?.[key] ?? key}
              connectNulls
              isAnimationActive={false}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      ) : (
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="value" fill="#3b82f6" />
        </BarChart>
      )}
    </ResponsiveContainer>
  )
}

export function GenUiChart({
  genUi,
}: {
  genUi: { type?: string; format?: string; payload?: unknown; messages?: unknown[] }
}) {
  if (!genUi?.payload && genUi?.format !== 'a2ui') return null

  if (genUi?.format === 'a2ui' && Array.isArray(genUi.messages) && genUi.messages.length > 0) {
    const charts = extractChartsFromA2ui(
      genUi.messages as Parameters<typeof extractChartsFromA2ui>[0]
    )
    if (charts.length > 0) {
      return (
        <div className="gen-ui-chart">
          {charts.map((c, i) => (
            <SingleChart key={c.kind + String(i)} spec={c} colorIndex={i} />
          ))}
        </div>
      )
    }
  }

  const p = (genUi?.payload ?? {}) as {
    data?: { x?: string[]; y?: number[] } | Record<string, unknown>[]
    multi_series?: boolean
    labels?: string[]
    values?: number[]
    series_labels?: Record<string, string>
    charts?: ChartSpec[]
  }

  if (Array.isArray(p.charts) && p.charts.length > 0) {
    return (
      <div className="gen-ui-chart">
        {p.charts.map((c, i) => (
          <SingleChart key={c.label + String(i)} spec={c} colorIndex={i} />
        ))}
      </div>
    )
  }

  let data: { name: string; value?: number; [k: string]: unknown }[]
  if (p.multi_series && Array.isArray(p.data) && p.data.length > 0) {
    data = p.data as { name: string; [k: string]: unknown }[]
  } else if (
    p.data &&
    !Array.isArray(p.data) &&
    'x' in (p.data as object)
  ) {
    const d = p.data as { x?: string[]; y?: number[] }
    data = (d.x || []).map((x, i) => ({
      name: x,
      value: (d.y || [])[i] ?? 0,
    }))
  } else {
    data = (p.labels || []).map((l, i) => ({
      name: l,
      value: (p.values || [])[i] ?? 0,
    }))
  }

  if (data.length === 0) return null

  const seriesKeys =
    p.multi_series
      ? [...new Set(data.flatMap((row) => Object.keys(row).filter((k) => k !== 'name')))].filter(
          Boolean
        )
      : (data[0] ? Object.keys(data[0]).filter((k) => k !== 'name') : [])

  return (
    <div className="gen-ui-chart">
      {genUi.type === 'line' ? (
        <MultiSeriesChart
          data={data}
          seriesKeys={seriesKeys}
          seriesLabels={p.series_labels}
          isLine
        />
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill="#3b82f6" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
