/**
 * OrbPanel - sessions tree, recent tasks, skills, workspace.
 */

import { formatSessionId } from '../../utils/session'
import { OrbPagination } from './OrbPagination'
import type { TreeRoot, ChildSession, Skill } from '../../types'

interface OrbPanelProps {
  currentSessionId: string | null
  orbOpen: boolean
  setOrbOpen: React.Dispatch<React.SetStateAction<boolean>>
  orbPos: { x: number; y: number } | null
  orbPanelSize: { width: number; height: number }
  paginatedRoots: TreeRoot[]
  paginatedTasks: ChildSession[]
  paginatedSkills: Skill[]
  paginatedWorkspace: string[]
  sessionsPageCount: number
  tasksPageCount: number
  skillsPageCount: number
  workspacePageCount: number
  safeSessionsPage: number
  safeTasksPage: number
  safeSkillsPage: number
  safeWorkspacePage: number
  setOrbSessionsPage: React.Dispatch<React.SetStateAction<number>>
  setOrbTasksPage: React.Dispatch<React.SetStateAction<number>>
  setOrbSkillsPage: React.Dispatch<React.SetStateAction<number>>
  setOrbWorkspacePage: React.Dispatch<React.SetStateAction<number>>
  selectedSkill: Skill | null
  setSelectedSkill: React.Dispatch<React.SetStateAction<Skill | null>>
  onSwitchSession: (id: string) => void
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void
  onNewSession: () => void
  onForkSession: () => void
  onResizePointerDown: (corner: 'se' | 'sw' | 'ne' | 'nw') => (e: React.PointerEvent) => void
  onOrbPointerDown: (e: React.PointerEvent) => void
  onOrbPointerUp: () => void
  onOrbPointerCancel: () => void
  onOrbClick: () => void
  ORB_RESIZE_MIN: { width: number; height: number }
}

export function OrbPanel(props: OrbPanelProps) {
  const {
    currentSessionId,
    orbOpen,
    setOrbOpen,
    orbPos,
    orbPanelSize,
    paginatedRoots,
    paginatedTasks,
    paginatedSkills,
    paginatedWorkspace,
    sessionsPageCount,
    tasksPageCount,
    skillsPageCount,
    workspacePageCount,
    safeSessionsPage,
    safeTasksPage,
    safeSkillsPage,
    safeWorkspacePage,
    setOrbSessionsPage,
    setOrbTasksPage,
    setOrbSkillsPage,
    setOrbWorkspacePage,
    selectedSkill,
    setSelectedSkill,
    onSwitchSession,
    onDeleteSession,
    onNewSession,
    onForkSession,
    onResizePointerDown,
    onOrbPointerDown,
    onOrbPointerUp,
    onOrbPointerCancel,
    onOrbClick,
    ORB_RESIZE_MIN,
  } = props

  const sessionLabel = (id: string) =>
    id.replace(/^web-/, '').slice(0, 8)

  const pagination = (
    page: number,
    count: number,
    setPage: React.Dispatch<React.SetStateAction<number>>
  ) => (
    <OrbPagination
      page={page}
      count={count}
      onPrev={() => setPage((p) => Math.max(0, p - 1))}
      onNext={() => setPage((p) => Math.min(count - 1, p + 1))}
    />
  )

  return (
    <div
      className="orb-wrap"
      style={
        orbPos != null
          ? { left: orbPos.x, top: orbPos.y, right: 'auto', bottom: 'auto' }
          : undefined
      }
    >
      {orbOpen && (
        <div
          className="orb-backdrop"
          onClick={() => setOrbOpen(false)}
          aria-hidden
        />
      )}
      <div
        className={`orb-panel ${orbOpen ? 'open' : ''}`}
        style={{
          width: orbPanelSize.width,
          height: orbPanelSize.height,
          minWidth: ORB_RESIZE_MIN.width,
          minHeight: ORB_RESIZE_MIN.height,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div className="orb-panel-scroll">
          <div className="orb-panel-header">
            Sophon{' '}
            {currentSessionId && (
              <code className="orb-session-id">
                {formatSessionId(currentSessionId)}
              </code>
            )}
          </div>
          <h3 className="orb-section">Sessions</h3>
          <div className="orb-tree">
            {paginatedRoots.map((root) => (
              <div key={root.id} className="orb-tree-root">
                <div
                  role="button"
                  tabIndex={0}
                  className={`session-tab ${currentSessionId === root.id ? 'active' : ''}`}
                  onClick={() => onSwitchSession(root.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onSwitchSession(root.id)
                    }
                  }}
                >
                  <span className="session-tab-label">
                    {sessionLabel(root.id)}
                    {(root.message_count ?? 0) > 0
                      ? ` (${root.message_count})`
                      : ''}
                  </span>
                  <button
                    type="button"
                    className="session-tab-delete"
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteSession(root.id, e)
                    }}
                    aria-label="Delete"
                  >
                    ×
                  </button>
                </div>
                {root.children.length > 0 && (
                  <div className="orb-tree-children">
                    {root.children.map((c) => (
                      <div
                        key={c.session_id}
                        role="button"
                        tabIndex={0}
                        className={`orb-tree-child status-${c.status} ${
                          currentSessionId === c.session_id ? 'active' : ''
                        }`}
                        onClick={() => onSwitchSession(c.session_id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            onSwitchSession(c.session_id)
                          }
                        }}
                      >
                        <span className="orb-tree-child-title">
                          {c.title || sessionLabel(c.session_id)}
                        </span>
                        <span
                          className={`orb-tree-child-status status-${c.status}`}
                        >
                          {c.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          {pagination(safeSessionsPage, sessionsPageCount, setOrbSessionsPage)}
          <div className="session-actions">
            <button
              className="btn-new-session"
              onClick={() => {
                onNewSession()
                setOrbOpen(false)
              }}
            >
              + New chat
            </button>
            {currentSessionId && (
              <button
                className="btn-fork"
                onClick={() => {
                  onForkSession()
                  setOrbOpen(false)
                }}
              >
                Fork
              </button>
            )}
          </div>
          {paginatedTasks.length > 0 && (
            <>
              <h3 className="orb-section">Recent tasks</h3>
              <div className="orb-tree">
                {paginatedTasks.map((task) => (
                  <div
                    key={task.session_id}
                    role="button"
                    tabIndex={0}
                    className={`orb-tree-child status-${task.status} ${
                      currentSessionId === task.session_id ? 'active' : ''
                    }`}
                    onClick={() => onSwitchSession(task.session_id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onSwitchSession(task.session_id)
                      }
                    }}
                  >
                    <span className="orb-tree-child-title">
                      {task.title || sessionLabel(task.session_id)}
                    </span>
                    <span
                      className={`orb-tree-child-status status-${task.status}`}
                    >
                      {task.status}
                    </span>
                  </div>
                ))}
              </div>
              {pagination(safeTasksPage, tasksPageCount, setOrbTasksPage)}
            </>
          )}
          <h3 className="orb-section">Skills</h3>
          <ul>
            {paginatedSkills.map((s) => (
              <li key={s.name}>
                <button
                  type="button"
                  className={`skill-btn ${
                    selectedSkill?.name === s.name ? 'active' : ''
                  }`}
                  onClick={() => {
                    setSelectedSkill(s)
                    setOrbOpen(false)
                  }}
                >
                  {s.name}
                </button>
              </li>
            ))}
          </ul>
          {pagination(safeSkillsPage, skillsPageCount, setOrbSkillsPage)}
          <h3 className="orb-section">Workspace</h3>
          <ul className="file-list">
            {paginatedWorkspace.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          {pagination(
            safeWorkspacePage,
            workspacePageCount,
            setOrbWorkspacePage
          )}
          <p className="guide">/ select skill · @ select file</p>
        </div>
        <div
          className="orb-resize-handle orb-resize-se"
          onPointerDown={onResizePointerDown('se')}
          role="separator"
          aria-label="Resize panel (bottom-right)"
        />
        <div
          className="orb-resize-handle orb-resize-sw"
          onPointerDown={onResizePointerDown('sw')}
          role="separator"
          aria-label="Resize panel (bottom-left)"
        />
        <div
          className="orb-resize-handle orb-resize-ne"
          onPointerDown={onResizePointerDown('ne')}
          role="separator"
          aria-label="Resize panel (top-right)"
        />
        <div
          className="orb-resize-handle orb-resize-nw"
          onPointerDown={onResizePointerDown('nw')}
          role="separator"
          aria-label="Resize panel (top-left)"
        />
      </div>
      <button
        type="button"
        className={`orb-ball ${orbOpen ? 'open' : ''}`}
        onPointerDown={onOrbPointerDown}
        onPointerUp={() => onOrbPointerUp()}
        onPointerCancel={() => onOrbPointerCancel()}
        onClick={onOrbClick}
        aria-label={orbOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={orbOpen}
      >
        <span className="orb-icon">{orbOpen ? '×' : '◉'}</span>
      </button>
    </div>
  )
}
