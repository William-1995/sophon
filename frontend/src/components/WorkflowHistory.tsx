/**
 * Workflow History — flat list (no cards). Renders nothing when empty or on load error.
 */

import { useCallback, useEffect, useState } from 'react'
import { listInstances } from '../api/cowork'

export interface WorkflowHistoryProps {
  onSelectInstance: (instanceId: string) => void | Promise<void>
}

type Row = {
  instance_id: string
  workflow_id: string
  status: string
  created_at: string
  error_message?: string
}

function parseErrorMessage(raw: string): string {
  try {
    const j = JSON.parse(raw) as { detail?: string }
    if (j?.detail) return j.detail
  } catch {
    /* plain */
  }
  return raw
}

export function WorkflowHistory({
  onSelectInstance,
}: WorkflowHistoryProps) {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(true)
  /** First fetch finished (so we don't flash content before load). */
  const [ready, setReady] = useState(false)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(10)
  const pageSizes = [10, 30, 50]

  const load = useCallback(async () => {
    setLoading(true)
    const res = await listInstances()
    if (res.error) {
      console.warn('[WorkflowHistory] list failed:', parseErrorMessage(res.error))
      setRows([])
    } else if (res.data?.instances) {
      setRows(res.data.instances)
    } else {
      setRows([])
    }
    setLoading(false)
    setReady(true)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const visibleRows = rows.slice(safePage * pageSize, safePage * pageSize + pageSize)

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount - 1))
  }, [pageCount])

  /** 没有数据就不占版面；有数据时刷新过程中仍保留列表避免闪烁 */
  if (!ready || rows.length === 0) {
    return null
  }

  return (
    <section className="workflow-history workflow-history--flat" aria-label="Recent workflow runs">
      <header className="workflow-history__toolbar">
        <span className="workflow-history__eyebrow">Recent</span>
        <button
          type="button"
          className="workflow-history__link"
          onClick={() => void load()}
          disabled={loading}
        >
          Refresh
        </button>
      </header>
      <ul className="workflow-history__lines">
        {visibleRows.map((r) => (
          <li key={r.instance_id}>
            <button
              type="button"
              className="workflow-history__line"
              onClick={() => void onSelectInstance(r.instance_id)}
            >
              <span className="workflow-history__mono" title={r.instance_id}>
                {r.instance_id.slice(0, 8)}…
              </span>
              <span className="workflow-history__name">{r.workflow_id}</span>
              <span className={`workflow-history__dot workflow-history__dot--${r.status}`} aria-hidden />
              <span className="workflow-history__state">{r.status}</span>
            </button>
          </li>
        ))}
      </ul>
      <footer className="workflow-history__footer">
        <div className="workflow-history__footer-controls">
          <label className="workflow-history__size-picker">
            <span>Per page</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value))
                setPage(0)
              }}
            >
              {pageSizes.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          {pageCount > 1 && (
            <div className="workflow-history__pager-group">
              <div className="workflow-history__pager" aria-label="Workflow history pagination">
                <button
                  type="button"
                  className="workflow-history__link"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={loading || safePage === 0}
                >
                  Prev
                </button>
                <span className="workflow-history__page-indicator">
                  {safePage + 1}/{pageCount}
                </span>
                <button
                  type="button"
                  className="workflow-history__link"
                  onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                  disabled={loading || safePage >= pageCount - 1}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </footer>
    </section>
  )
}
