/**
 * Orb panel hook - draggable position, resize, pagination.
 */

import { useState, useRef, useCallback } from 'react'
import {
  ORB_RESIZE_MIN,
  ORB_RESIZE_MAX,
  ORB_PAGE_SIZE,
  ORB_TASK_PAGE_SIZE,
} from '../constants'
import type { TreeRoot, Skill, ResizeCorner } from '../types'

interface UseOrbPanelOptions {
  treeRoots: TreeRoot[]
  skills: Skill[]
  workspaceFiles: string[]
}

interface OrbPanelSize {
  width: number
  height: number
}

export function useOrbPanel(options: UseOrbPanelOptions) {
  const { treeRoots, skills, workspaceFiles } = options

  const [orbOpen, setOrbOpen] = useState(false)
  const [orbPos, setOrbPos] = useState<{ x: number; y: number } | null>(null)
  const [orbPanelSize, setOrbPanelSize] = useState<OrbPanelSize>({
    width: 280,
    height: 420,
  })
  const [orbSessionsPage, setOrbSessionsPage] = useState(0)
  const [orbTasksPage, setOrbTasksPage] = useState(0)
  const [orbSkillsPage, setOrbSkillsPage] = useState(0)
  const [orbWorkspacePage, setOrbWorkspacePage] = useState(0)

  const orbDragRef = useRef<{
    startX: number
    startY: number
    startPos: { x: number; y: number }
  } | null>(null)
  const orbJustDraggedRef = useRef(false)
  const orbResizeRef = useRef<{
    startX: number
    startY: number
    startW: number
    startH: number
  } | null>(null)
  const orbListenersRef = useRef<{ cleanup: () => void } | null>(null)

  const allChildSessions = treeRoots
    .flatMap((r) => r.children || [])
    .slice()
    .sort((a, b) => (b.created_at || 0) - (a.created_at || 0))

  const sessionsPageCount = Math.max(1, Math.ceil(treeRoots.length / ORB_PAGE_SIZE))
  const tasksPageCount = Math.max(1, Math.ceil(allChildSessions.length / ORB_TASK_PAGE_SIZE))
  const skillsPageCount = Math.max(1, Math.ceil(skills.length / ORB_PAGE_SIZE))
  const workspacePageCount = Math.max(
    1,
    Math.ceil(workspaceFiles.length / ORB_PAGE_SIZE)
  )

  const safeSessionsPage = Math.min(orbSessionsPage, Math.max(0, sessionsPageCount - 1))
  const safeTasksPage = Math.min(orbTasksPage, Math.max(0, tasksPageCount - 1))
  const safeSkillsPage = Math.min(orbSkillsPage, Math.max(0, skillsPageCount - 1))
  const safeWorkspacePage = Math.min(orbWorkspacePage, Math.max(0, workspacePageCount - 1))

  const paginatedRoots = treeRoots.slice(
    safeSessionsPage * ORB_PAGE_SIZE,
    (safeSessionsPage + 1) * ORB_PAGE_SIZE
  )
  const paginatedTasks = allChildSessions.slice(
    safeTasksPage * ORB_TASK_PAGE_SIZE,
    (safeTasksPage + 1) * ORB_TASK_PAGE_SIZE
  )
  const paginatedSkills = skills.slice(
    safeSkillsPage * ORB_PAGE_SIZE,
    (safeSkillsPage + 1) * ORB_PAGE_SIZE
  )
  const paginatedWorkspace = workspaceFiles.slice(
    safeWorkspacePage * ORB_PAGE_SIZE,
    (safeWorkspacePage + 1) * ORB_PAGE_SIZE
  )

  const handleOrbPointerDown = useCallback((e: React.PointerEvent) => {
    const el = e.currentTarget as HTMLElement
    const pointerId = e.pointerId
    el.setPointerCapture(pointerId)
    orbJustDraggedRef.current = false
    const startPos = orbPos ?? {
      x: window.innerWidth - 24 - 48,
      y: window.innerHeight - 24 - 48,
    }
    orbDragRef.current = { startX: e.clientX, startY: e.clientY, startPos }

    const onMove = (ev: PointerEvent) => {
      if (ev.pointerId !== pointerId || !orbDragRef.current) return
      const dx = ev.clientX - orbDragRef.current.startX
      const dy = ev.clientY - orbDragRef.current.startY
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) orbJustDraggedRef.current = true
      const nx = orbDragRef.current.startPos.x + dx
      const ny = orbDragRef.current.startPos.y + dy
      setOrbPos({
        x: Math.max(0, Math.min(window.innerWidth - 48, nx)),
        y: Math.max(0, Math.min(window.innerHeight - 48, ny)),
      })
    }

    const cleanup = () => {
      try {
        el.releasePointerCapture(pointerId)
      } catch {
        // ignore
      }
      orbDragRef.current = null
      orbListenersRef.current = null
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', cleanup)
    }
    orbListenersRef.current = { cleanup }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', cleanup)
  }, [orbPos])

  const handleOrbPointerUp = useCallback(() => {
    orbListenersRef.current?.cleanup()
  }, [])

  const handleOrbPointerCancel = useCallback(() => {
    orbListenersRef.current?.cleanup()
  }, [])

  const handleOrbClick = useCallback(() => {
    if (orbJustDraggedRef.current) {
      orbJustDraggedRef.current = false
      return
    }
    setOrbOpen((o) => !o)
  }, [])

  const handleOrbResizePointerDown = useCallback(
    (corner: ResizeCorner) => (e: React.PointerEvent) => {
      e.preventDefault()
      e.stopPropagation()
      const el = e.currentTarget as HTMLElement
      el.setPointerCapture(e.pointerId)
      orbResizeRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        startW: orbPanelSize.width,
        startH: orbPanelSize.height,
      }
      const dxMult = corner === 'se' || corner === 'ne' ? 1 : -1
      const dyMult = corner === 'se' || corner === 'sw' ? 1 : -1

      const onMove = (ev: PointerEvent) => {
        if (!orbResizeRef.current) return
        const dx = ev.clientX - orbResizeRef.current.startX
        const dy = ev.clientY - orbResizeRef.current.startY
        const dw = dx * dxMult
        const dh = dy * dyMult
        const w = Math.max(
          ORB_RESIZE_MIN.width,
          Math.min(ORB_RESIZE_MAX.width, orbResizeRef.current.startW + dw)
        )
        const h = Math.max(
          ORB_RESIZE_MIN.height,
          Math.min(ORB_RESIZE_MAX.height, orbResizeRef.current.startH + dh)
        )
        setOrbPanelSize({ width: w, height: h })
      }

      const onUp = () => {
        el.releasePointerCapture(e.pointerId)
        orbResizeRef.current = null
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', onUp)
      }

      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerup', onUp)
    },
    [orbPanelSize]
  )

  return {
    orbOpen,
    setOrbOpen,
    orbPos,
    orbPanelSize,
    orbSessionsPage,
    setOrbSessionsPage,
    orbTasksPage,
    setOrbTasksPage,
    orbSkillsPage,
    setOrbSkillsPage,
    orbWorkspacePage,
    setOrbWorkspacePage,
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
    handleOrbPointerDown,
    handleOrbPointerUp,
    handleOrbPointerCancel,
    handleOrbClick,
    handleOrbResizePointerDown,
  }
}
