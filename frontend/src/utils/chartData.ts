/**
 * Chart data parsing from GenUI payloads.
 */

const LABEL_FROM_KIND = (kind: string) =>
  kind.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

interface A2uiEntry {
  key: string
  valueString?: string
  valueNumber?: number
  valueMap?: A2uiEntry[]
}

export function parseA2uiValueMap(
  arr: A2uiEntry[]
): Record<string, unknown> | unknown[] {
  const out: Record<string, unknown> = {}
  for (const e of arr) {
    if (e.valueMap != null) {
      out[e.key] = parseA2uiValueMap(e.valueMap)
    } else if (e.valueNumber != null) {
      out[e.key] = e.valueNumber
    } else {
      out[e.key] = e.valueString ?? ''
    }
  }
  const keys = Object.keys(out).filter((k) => /^\d+$/.test(k))
  if (keys.length === Object.keys(out).length && keys.length > 0) {
    return keys
      .sort((a, b) => parseInt(a, 10) - parseInt(b, 10))
      .map((k) => out[k])
  }
  return out
}

interface DmMessage {
  dataModelUpdate?: {
    contents?: { key: string; valueMap?: A2uiEntry[] }[]
  }
}

export function extractChartsFromA2ui(
  messages: DmMessage[]
): Array<{
  kind: string
  labels?: string[]
  values?: number[]
  x?: string[]
  y?: number[]
  chart_type?: string
}> {
  const dm = messages.find((m) => m.dataModelUpdate?.contents)
  if (!dm?.dataModelUpdate?.contents) return []
  const chartsEntry = dm.dataModelUpdate.contents.find(
    (c: { key: string }) => c.key === 'charts'
  ) as { valueMap?: { key: string; valueMap?: A2uiEntry[] }[] }
  if (!chartsEntry?.valueMap) return []
  return chartsEntry.valueMap.map((item) => {
    const raw = parseA2uiValueMap((item.valueMap ?? []) as A2uiEntry[])
    const data =
      typeof raw === 'object' && raw !== null && !Array.isArray(raw)
        ? raw
        : ({} as Record<string, unknown>)
    return {
      kind: String(data.kind ?? 'chart'),
      labels: Array.isArray(data.labels) ? data.labels.map(String) : undefined,
      values: Array.isArray(data.values) ? data.values.map(Number) : undefined,
      x: Array.isArray(data.x) ? data.x.map(String) : undefined,
      y: Array.isArray(data.y) ? data.y.map(Number) : undefined,
      chart_type: String(data.chart_type ?? 'bar'),
    }
  })
}

export { LABEL_FROM_KIND }
