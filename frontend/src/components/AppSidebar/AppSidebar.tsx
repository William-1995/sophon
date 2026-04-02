/**
 * Left sidebar — Claude Desktop–style navigation (sessions, skills, workspace).
 */

import { useState, useCallback } from 'react'
import { formatSessionId } from '../../utils/session'
import { OrbPagination } from '../OrbPanel/OrbPagination'
import type { TreeRoot, ChildSession, Skill } from '../../types'

export interface AppSidebarProps {
  currentSessionId: string | null
  collapsed: boolean
  onToggleCollapse: () => void
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
  setSidebarSessionsPage: React.Dispatch<React.SetStateAction<number>>
  setSidebarTasksPage: React.Dispatch<React.SetStateAction<number>>
  setSidebarSkillsPage: React.Dispatch<React.SetStateAction<number>>
  setSidebarWorkspacePage: React.Dispatch<React.SetStateAction<number>>
  selectedSkill: Skill | null
  setSelectedSkill: React.Dispatch<React.SetStateAction<Skill | null>>
  onSwitchSession: (id: string) => void
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void
  onNewSession: () => void
  onForkSession: () => void
  /** Open full-page customize / settings (3-column shell) */
  onOpenCustomize?: () => void
  onOpenSettings?: () => void
}

type SidebarSectionKey = 'sessions' | 'recent' | 'skills' | 'workspace' | 'footer'

interface SidebarFoldSectionProps {
  sectionKey: SidebarSectionKey
  title: string
  subtitle?: string
  open: boolean
  onToggle: () => void
  className?: string
  children: React.ReactNode
}

function SidebarFoldSection({
  sectionKey,
  title,
  subtitle,
  open,
  onToggle,
  className,
  children,
}: SidebarFoldSectionProps) {
  const headingId = `sidebar-${sectionKey}-heading`
  const panelId = `sidebar-${sectionKey}-panel`

  return (
    <section
      className={className}
      aria-labelledby={headingId}
    >
      <button
        type="button"
        className="sidebar-section__toggle"
        id={headingId}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <span
          className={`sidebar-section__chevron ${open ? 'sidebar-section__chevron--open' : ''}`}
          aria-hidden
        />
        <span className="sidebar-section__toggle-label">{title}</span>
      </button>
      {open && (
        <div
          id={panelId}
          role="region"
          aria-labelledby={headingId}
          className="sidebar-section__body"
        >
          {subtitle ? (
            <p className="sidebar-section__subtitle">{subtitle}</p>
          ) : null}
          {children}
        </div>
      )}
    </section>
  )
}

export function AppSidebar(props: AppSidebarProps) {
  const {
    currentSessionId,
    collapsed,
    onToggleCollapse,
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
    setSidebarSessionsPage,
    setSidebarTasksPage,
    setSidebarSkillsPage,
    setSidebarWorkspacePage,
    selectedSkill,
    setSelectedSkill,
    onSwitchSession,
    onDeleteSession,
    onNewSession,
    onForkSession,
    onOpenCustomize,
    onOpenSettings,
  } = props

  const [sectionsOpen, setSectionsOpen] = useState<
    Record<SidebarSectionKey, boolean>
  >({
    sessions: true,
    recent: false,
    skills: false,
    workspace: true,
    footer: true,
  })

  const toggleSection = useCallback((key: SidebarSectionKey) => {
    setSectionsOpen((s) => ({ ...s, [key]: !s[key] }))
  }, [])

  const sessionLabel = (id: string) => id.replace(/^web-/, '').slice(0, 8)

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

  if (collapsed) {
    return (
      <aside className="app-sidebar app-sidebar--collapsed" aria-label="Navigation">
        <button
          type="button"
          className="app-sidebar__expand"
          onClick={onToggleCollapse}
          aria-label="Expand sidebar"
          title="Expand sidebar"
        >
          ⟩
        </button>
        {onOpenCustomize && (
          <button
            type="button"
            className="app-sidebar__customize-rail"
            onClick={onOpenCustomize}
            aria-label="Customize and settings"
            title="Customize"
          >
            ⚙
          </button>
        )}
      </aside>
    )
  }

  return (
    <aside className="app-sidebar" aria-label="Navigation">
      <div className="app-sidebar__header">
        <button
          type="button"
          className="app-sidebar__collapse"
          onClick={onToggleCollapse}
          aria-label="Collapse sidebar"
          title="Collapse sidebar"
        >
          ⟨
        </button>
        <div className="app-sidebar__brand">
          <span className="app-sidebar__brand-name">Sophon</span>
          {currentSessionId && (
            <code className="app-sidebar__session-id">
              {formatSessionId(currentSessionId)}
            </code>
          )}
        </div>
      </div>

      <div className="app-sidebar__scroll">
        <SidebarFoldSection
          sectionKey="sessions"
          title="Sessions"
          open={sectionsOpen.sessions}
          onToggle={() => toggleSection('sessions')}
          className="sidebar-section sidebar-section--sessions"
        >
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
          {pagination(safeSessionsPage, sessionsPageCount, setSidebarSessionsPage)}
          <div className="session-actions">
            <button type="button" className="btn-new-session" onClick={onNewSession}>
              + New chat
            </button>
            {currentSessionId && (
              <button type="button" className="btn-fork" onClick={onForkSession}>
                Fork
              </button>
            )}
          </div>
        </SidebarFoldSection>

        {paginatedTasks.length > 0 && (
          <SidebarFoldSection
            sectionKey="recent"
            title="Recent tasks"
            subtitle="Across sessions"
            open={sectionsOpen.recent}
            onToggle={() => toggleSection('recent')}
            className="sidebar-section sidebar-section--recent"
          >
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
                  <span className={`orb-tree-child-status status-${task.status}`}>
                    {task.status}
                  </span>
                </div>
              ))}
            </div>
            {pagination(safeTasksPage, tasksPageCount, setSidebarTasksPage)}
          </SidebarFoldSection>
        )}

        <SidebarFoldSection
          sectionKey="skills"
          title="Skills"
          open={sectionsOpen.skills}
          onToggle={() => toggleSection('skills')}
          className="sidebar-section sidebar-section--skills"
        >
          <ul className="sidebar-section__list">
            {paginatedSkills.map((s) => (
              <li key={s.name}>
                <button
                  type="button"
                  className={`skill-btn ${selectedSkill?.name === s.name ? 'active' : ''}`}
                  onClick={() => setSelectedSkill(s)}
                >
                  {s.name}
                </button>
              </li>
            ))}
          </ul>
          {pagination(safeSkillsPage, skillsPageCount, setSidebarSkillsPage)}
        </SidebarFoldSection>

        <SidebarFoldSection
          sectionKey="workspace"
          title="Workspace"
          open={sectionsOpen.workspace}
          onToggle={() => toggleSection('workspace')}
          className="sidebar-section sidebar-section--workspace"
        >
          <ul className="file-list sidebar-section__list">
            {paginatedWorkspace.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          {pagination(
            safeWorkspacePage,
            workspacePageCount,
            setSidebarWorkspacePage
          )}
        </SidebarFoldSection>

        <SidebarFoldSection
          sectionKey="footer"
          title="More"
          open={sectionsOpen.footer}
          onToggle={() => toggleSection('footer')}
          className="sidebar-section sidebar-section--footer"
        >
          <p className="guide">/ skill · @ file · voice in chat</p>

          {onOpenCustomize && (
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                className="app-sidebar__customize-btn"
                onClick={onOpenCustomize}
                style={{ flex: 1 }}
              >
                Customize…
              </button>
              {onOpenSettings && (
                <button
                  type="button"
                  className="app-sidebar__customize-btn"
                  onClick={onOpenSettings}
                  style={{ width: '40px', padding: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  title="Settings"
                  aria-label="Settings"
                >
                  ⚙
                </button>
              )}
            </div>
          )}

          <div className="app-sidebar__footer-links">
            <span className="app-sidebar__footer-label">Soon</span>
            <span className="app-sidebar__footer-pill">Projects</span>
            <span className="app-sidebar__footer-pill">Scheduled</span>
          </div>
        </SidebarFoldSection>
      </div>
    </aside>
  )
}
