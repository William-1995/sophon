/**
 * Left sidebar: sessions, tasks, skills, workspace (replaces floating orb).
 */

import { useState, useCallback } from 'react'
import { ORB_PAGE_SIZE, ORB_TASK_PAGE_SIZE } from '../constants'
import type { TreeRoot, Skill } from '../types'

interface UseAppSidebarOptions {
  treeRoots: TreeRoot[]
  skills: Skill[]
  workspaceFiles: string[]
}

export function useAppSidebar(options: UseAppSidebarOptions) {
  const { treeRoots, skills, workspaceFiles } = options

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [sidebarSessionsPage, setSidebarSessionsPage] = useState(0)
  const [sidebarTasksPage, setSidebarTasksPage] = useState(0)
  const [sidebarSkillsPage, setSidebarSkillsPage] = useState(0)
  const [sidebarWorkspacePage, setSidebarWorkspacePage] = useState(0)

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

  const safeSessionsPage = Math.min(
    sidebarSessionsPage,
    Math.max(0, sessionsPageCount - 1)
  )
  const safeTasksPage = Math.min(sidebarTasksPage, Math.max(0, tasksPageCount - 1))
  const safeSkillsPage = Math.min(sidebarSkillsPage, Math.max(0, skillsPageCount - 1))
  const safeWorkspacePage = Math.min(
    sidebarWorkspacePage,
    Math.max(0, workspacePageCount - 1)
  )

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

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((c) => !c)
  }, [])

  return {
    sidebarCollapsed,
    setSidebarCollapsed,
    toggleSidebar,
    sidebarSessionsPage,
    setSidebarSessionsPage,
    sidebarTasksPage,
    setSidebarTasksPage,
    sidebarSkillsPage,
    setSidebarSkillsPage,
    sidebarWorkspacePage,
    setSidebarWorkspacePage,
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
  }
}
