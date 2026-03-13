/**
 * Application constants.
 * Centralized configuration to avoid magic strings.
 */

export const API_BASE = import.meta.env.VITE_API_URL || ''
export const SESSION_STORAGE_KEY = 'sophon_current_session'
export const GEN_UI_PREFIX = 'sophon_gen_ui:'

export const ORB_PAGE_SIZE = 5
export const ORB_TASK_PAGE_SIZE = 10
export const ORB_RESIZE_MIN = { width: 200, height: 200 }
export const ORB_RESIZE_MAX = { width: 500, height: 600 }

export const LINE_COLORS = [
  '#3b82f6',
  '#22c55e',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#06b6d4',
]

export const SESSION_ID_PREFIX = 'web-'
export const SESSION_ID_DISPLAY_LEN = 12

/** Emotion label -> orb ring color */
export const EMOTION_RING_COLORS: Record<string, string> = {
  satisfied: '#22c55e',
  relieved: '#22c55e',
  amused: '#22c55e',
  neutral: '#94a3b8',
  frustrated: '#f97316',
  disappointed: '#ef4444',
  anxious: '#eab308',
  confused: '#f59e0b',
}
export const EMOTION_RING_DEFAULT = '#94a3b8'
