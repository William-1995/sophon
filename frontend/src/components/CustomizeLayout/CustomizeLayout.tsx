/**
 * Three-column customize shell (inspired by desktop app patterns, Sophon-branded).
 * Primary nav → secondary list → detail / empty state.
 */

import { useState, useMemo, useEffect } from 'react'
import type { Skill } from '../../types'

export type CustomizePrimary = 'overview' | 'skills' | 'connectors' | 'plugins' | 'settings'

const PRIMARY_ITEMS: { id: CustomizePrimary; label: string; hint: string }[] = [
  { id: 'overview', label: 'Overview', hint: 'Start here' },
  { id: 'skills', label: 'Skills', hint: 'Reusable instructions' },
  { id: 'connectors', label: 'Connectors', hint: 'MCP & external systems' },
  { id: 'plugins', label: 'Plugin bundles', hint: 'Package skills + connectors' },
  { id: 'settings', label: 'Settings', hint: 'Theme & preferences' },
]

type Theme = 'system' | 'warm' | 'light' | 'dark'

const THEME_OPTIONS: { id: Theme; label: string; description: string }[] = [
  { id: 'system', label: 'System', description: 'Follow your system light/dark preference' },
  { id: 'warm', label: 'Warm', description: 'Eye-care theme with warm beige tones' },
  { id: 'light', label: 'Light', description: 'Clean modern light theme' },
  { id: 'dark', label: 'Dark', description: 'Dark mode for low-light environments' },
]

const CONNECTOR_PLACEHOLDERS = [
  { id: 'mcp', title: 'MCP servers', subtitle: 'Configured in your IDE or gateway' },
  { id: 'workspace', title: 'Workspace API', subtitle: 'Sessions, files, and resources' },
]

const PLUGIN_PLACEHOLDERS = [
  { id: 'local', title: 'Local extensions', subtitle: 'WIP · aligned with skills/' },
  { id: 'bundles', title: 'Bundles', subtitle: 'Ship multiple skills together' },
]

interface CustomizeLayoutProps {
  skills: Skill[]
  onBack: () => void
  onPickSkill?: (skill: Skill) => void
  initialSection?: 'overview' | 'settings'
}

export function CustomizeLayout({
  skills,
  onBack,
  onPickSkill,
  initialSection = 'overview',
}: CustomizeLayoutProps) {
  const [primary, setPrimary] = useState<CustomizePrimary>(initialSection === 'settings' ? 'settings' : 'overview')
  const [secondaryId, setSecondaryId] = useState<string | null>(initialSection === 'settings' ? 'appearance' : null)
  const [currentTheme, setCurrentTheme] = useState<Theme>('system')

  useEffect(() => {
    const savedTheme = localStorage.getItem('sophon-theme') as Theme | null
    if (savedTheme && ['system', 'warm', 'light', 'dark'].includes(savedTheme)) {
      setCurrentTheme(savedTheme)
      if (savedTheme === 'system') {
        document.documentElement.removeAttribute('data-theme')
      } else {
        document.documentElement.setAttribute('data-theme', savedTheme)
      }
      return
    }
    document.documentElement.removeAttribute('data-theme')
  }, [])

  const handleThemeChange = (theme: Theme) => {
    setCurrentTheme(theme)
    if (theme === 'system') {
      document.documentElement.removeAttribute('data-theme')
    } else {
      document.documentElement.setAttribute('data-theme', theme)
    }
    localStorage.setItem('sophon-theme', theme)
  }

  const sortedSkills = useMemo(
    () => [...skills].sort((a, b) => a.name.localeCompare(b.name)),
    [skills]
  )

  const selectedSkill = useMemo(
    () => sortedSkills.find((s) => s.name === secondaryId) ?? null,
    [sortedSkills, secondaryId]
  )

  const handlePrimary = (id: CustomizePrimary) => {
    setPrimary(id)
    setSecondaryId(null)
  }

  return (
    <div className="customize-root" role="application" aria-label="Sophon customize">
      <nav className="customize-col customize-col--primary" aria-label="Primary">
        <button type="button" className="customize-back" onClick={onBack}>
          ← Back to workspace
        </button>
        <p className="customize-primary-title">Customize</p>
        <ul className="customize-primary-list">
          {PRIMARY_ITEMS.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`customize-primary-item ${primary === item.id ? 'active' : ''}`}
                onClick={() => handlePrimary(item.id)}
                title={item.hint}
              >
                <span className="customize-primary-item__label">{item.label}</span>
                <span className="customize-primary-item__hint">{item.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="customize-col customize-col--secondary" aria-label="List">
        {primary === 'overview' && (
          <div className="customize-secondary-empty">
            <p className="customize-secondary-title">Get started</p>
            <p className="customize-secondary-muted">
              Pick Skills, Connectors, or Plugin bundles in the first column to see items here.
            </p>
          </div>
        )}

        {primary === 'skills' && (
          <>
            <p className="customize-secondary-header">Loaded skills</p>
            <ul className="customize-secondary-list">
              {sortedSkills.length === 0 ? (
                <li className="customize-secondary-muted">No skills loaded</li>
              ) : (
                sortedSkills.map((s) => (
                  <li key={s.name}>
                    <button
                      type="button"
                      className={`customize-secondary-row ${secondaryId === s.name ? 'active' : ''}`}
                      onClick={() => {
                        setSecondaryId(s.name)
                        onPickSkill?.(s)
                      }}
                    >
                      <span className="customize-secondary-row__title">{s.name}</span>
                      <span className="customize-secondary-row__sub">
                        {s.description.slice(0, 72)}
                        {s.description.length > 72 ? '…' : ''}
                      </span>
                    </button>
                  </li>
                ))
              )}
            </ul>
          </>
        )}

        {primary === 'connectors' && (
          <>
            <p className="customize-secondary-header">Connectors</p>
            <ul className="customize-secondary-list">
              {CONNECTOR_PLACEHOLDERS.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    className={`customize-secondary-row ${secondaryId === c.id ? 'active' : ''}`}
                    onClick={() => setSecondaryId(c.id)}
                  >
                    <span className="customize-secondary-row__title">{c.title}</span>
                    <span className="customize-secondary-row__sub">{c.subtitle}</span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}

        {primary === 'plugins' && (
          <>
            <div className="customize-secondary-toolbar">
              <p className="customize-secondary-header">Plugin bundles</p>
              <button type="button" className="customize-add-btn" disabled title="Coming soon">
                +
              </button>
            </div>
            <ul className="customize-secondary-list">
              {PLUGIN_PLACEHOLDERS.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    className={`customize-secondary-row ${secondaryId === p.id ? 'active' : ''}`}
                    onClick={() => setSecondaryId(p.id)}
                  >
                    <span className="customize-secondary-row__title">{p.title}</span>
                    <span className="customize-secondary-row__sub">{p.subtitle}</span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}

        {primary === 'settings' && (
          <>
            <p className="customize-secondary-header">Preferences</p>
            <ul className="customize-secondary-list">
              <li>
                <button
                  type="button"
                  className={`customize-secondary-row ${secondaryId === 'appearance' ? 'active' : ''}`}
                  onClick={() => setSecondaryId('appearance')}
                >
                  <span className="customize-secondary-row__title">Appearance</span>
                  <span className="customize-secondary-row__sub">Theme and visual preferences</span>
                </button>
              </li>
            </ul>
          </>
        )}
      </div>

      <main className="customize-col customize-col--detail">
        {primary === 'overview' && (
          <div className="customize-detail-hero">
            <div className="customize-detail-icon" aria-hidden>
              ◈
            </div>
            <h1 className="customize-detail-h1">Manage context & tools</h1>
            <p className="customize-detail-lead">
              Hook up systems you use, curate skills for your team, and keep advanced options out of the main chat—same
              three-column idea as leading desktop assistants, without copying their branding.
            </p>
            <ul className="customize-detail-cards">
              <li>
                <span className="customize-detail-card__icon" aria-hidden>⎘</span>
                <div>
                  <strong>Connect tools</strong>
                  <p>Use MCP and connectors so CRM, browser, and file stores share one assistant context.</p>
                </div>
              </li>
              <li>
                <span className="customize-detail-card__icon" aria-hidden>📋</span>
                <div>
                  <strong>Curate skills</strong>
                  <p>Maintain SKILL.md under <code>skills/</code>; browse and set defaults here.</p>
                </div>
              </li>
              <li>
                <span className="customize-detail-card__icon" aria-hidden>⎗</span>
                <div>
                  <strong>Plugin bundles (planned)</strong>
                  <p>Package skills, connectors, and notes for teams and versioning.</p>
                </div>
              </li>
            </ul>
          </div>
        )}

        {primary === 'skills' && selectedSkill && (
          <div className="customize-detail-panel">
            <h2 className="customize-detail-h2">{selectedSkill.name}</h2>
            <p className="customize-detail-body">{selectedSkill.description}</p>
            <p className="customize-detail-muted">
              Press <kbd>/</kbd> in chat to switch skills; your choice here syncs as the session default.
            </p>
          </div>
        )}

        {primary === 'skills' && !selectedSkill && sortedSkills.length > 0 && (
          <div className="customize-detail-placeholder">
            <p>Select a skill in the middle column to read its description.</p>
          </div>
        )}

        {primary === 'skills' && sortedSkills.length === 0 && (
          <div className="customize-detail-placeholder">
            <p>No skills loaded—check the /skills API and your skills/ tree.</p>
          </div>
        )}

        {primary === 'connectors' && secondaryId && (
          <div className="customize-detail-panel">
            <h2 className="customize-detail-h2">
              {CONNECTOR_PLACEHOLDERS.find((c) => c.id === secondaryId)?.title}
            </h2>
            <p className="customize-detail-body">
              Sophon session and resource APIs are live; MCP is usually wired in the IDE. This panel is for unified docs
              and a future health-check action.
            </p>
          </div>
        )}

        {primary === 'connectors' && !secondaryId && (
          <div className="customize-detail-placeholder">
            <p>Choose a connector type to read more.</p>
          </div>
        )}

        {primary === 'plugins' && secondaryId && (
          <div className="customize-detail-panel">
            <h2 className="customize-detail-h2">
              {PLUGIN_PLACEHOLDERS.find((p) => p.id === secondaryId)?.title}
            </h2>
            <p className="customize-detail-body">
              Bundles will align with the <code>skills/</code> index and an optional manifest—placeholder for now.
            </p>
          </div>
        )}

        {primary === 'plugins' && !secondaryId && (
          <div className="customize-detail-placeholder">
            <p>Select an item or wait for the add flow.</p>
          </div>
        )}

        {primary === 'settings' && (
          <div className="customize-detail-panel">
            <h2 className="customize-detail-h2">Appearance</h2>
            <p className="customize-detail-body">Choose a theme that feels comfortable for your eyes.</p>
            
            <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {THEME_OPTIONS.map((theme) => (
                <button
                  key={theme.id}
                  type="button"
                  onClick={() => handleThemeChange(theme.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '16px',
                    padding: '16px',
                    border: `2px solid ${currentTheme === theme.id ? 'var(--accent)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius)',
                    background: currentTheme === theme.id ? 'var(--accent-dim)' : 'var(--msg-bg)',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div
                    style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border)',
                      background: theme.id === 'warm' ? '#FDF6E3' : theme.id === 'light' ? '#f0eeea' : '#0e0d0c',
                      flexShrink: 0,
                    }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--fg)' }}>
                      {theme.label}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: '4px' }}>
                      {theme.description}
                    </div>
                  </div>
                  {currentTheme === theme.id && (
                    <div style={{ color: 'var(--accent)', fontSize: '1.2rem' }}>✓</div>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
