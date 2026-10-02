import { invoke, isTauri } from '@tauri-apps/api/core'
import { useCallback, useEffect, useRef, useState } from 'react'

export type DownloadStatus = 'active' | 'waiting' | 'paused' | 'error' | 'complete' | 'removed'

export interface Download {
  gid: string
  status: DownloadStatus
  name: string
  total: number
  completed: number
  speed: number
  progress: number
  error: string
  errorCode: string
  path: string
  speedLimit: number
}

export interface Pending {
  id: string
  url: string
  name: string
  size: number
}

export interface Settings {
  intercept_enabled: boolean
  auto_start: boolean
  intercept_all: boolean
  extensions: string[]
  connections: number
  download_limit_bps: number
  clipboard_enabled: boolean
  disk_guard_enabled: boolean
  disk_reserve_mb: number
  start_with_windows: boolean
  minimize_to_tray: boolean
  auto_update_check: boolean
}

export interface UpdateInfo {
  current: string
  supported: boolean
  status: 'idle' | 'checking' | 'downloading' | 'verifying' | 'installing' | 'error'
  available: boolean
  version: string
  notes: string
  page_url: string
  progress: number
  error: string
  checked_at: number
}

export interface Disk {
  available: boolean
  path?: string
  free?: number
  shortfall?: number
  guardTripped?: boolean
}

export interface Snapshot {
  items: Download[]
  pending: Pending[]
  global: { downloadSpeed: number; numActive: number }
  disk: Disk
  settings: Settings
  update: UpdateInfo
}

interface BridgeInfo {
  baseUrl: string
  token: string
}

/** Mirrors TRANSIENT_ERROR_CODES in server/app.py: the bridge re-queues these. */
const TRANSIENT_ERROR_CODES = new Set(['1', '2', '6', '19', '29'])

export function isReconnecting(d: Download): boolean {
  return d.status === 'error' && TRANSIENT_ERROR_CODES.has(d.errorCode)
}

async function locateBridge(): Promise<BridgeInfo> {
  if (isTauri()) return invoke<BridgeInfo>('bridge_info')
  // Plain browser during development: point Vite at a running bridge.
  const baseUrl = import.meta.env.VITE_BRIDGE_URL
  const token = import.meta.env.VITE_BRIDGE_TOKEN
  if (!baseUrl || !token) throw new Error('Set VITE_BRIDGE_URL and VITE_BRIDGE_TOKEN')
  return { baseUrl, token }
}

export type Connection = 'connecting' | 'online' | 'offline'

export type Api = <T = unknown>(path: string, init?: { method?: string; body?: unknown }) => Promise<T>

/**
 * Connects to the bridge, keeps the live snapshot from its WebSocket and
 * exposes an authenticated `api` for actions. Reconnects on its own.
 */
export function useBridge() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [connection, setConnection] = useState<Connection>('connecting')
  const info = useRef<BridgeInfo | null>(null)
  const saving = useRef(0)

  useEffect(() => {
    let socket: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout> | undefined
    let stopped = false

    const connect = async () => {
      try {
        const found = await locateBridge()
        info.current = found
        const ws = new WebSocket(
          `${found.baseUrl.replace(/^http/, 'ws')}/ws?token=${encodeURIComponent(found.token)}`,
        )
        socket = ws
        ws.onopen = () => setConnection('online')
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data)
          if (data.type !== 'downloads') return
          const next = data as Snapshot
          setSnapshot((prev) => (saving.current && prev ? { ...next, settings: prev.settings } : next))
        }
        ws.onclose = () => {
          if (stopped) return
          setConnection('offline')
          retry = setTimeout(connect, 1000)
        }
      } catch {
        if (stopped) return
        setConnection('offline')
        retry = setTimeout(connect, 1000)
      }
    }

    connect()
    return () => {
      stopped = true
      clearTimeout(retry)
      socket?.close()
    }
  }, [])

  const api: Api = useCallback(async (path, init = {}) => {
    const bridge = info.current
    if (!bridge) throw new Error('bridge not connected')
    const response = await fetch(`${bridge.baseUrl}${path}`, {
      method: init.method ?? 'GET',
      headers: {
        Authorization: `Bearer ${bridge.token}`,
        ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    })
    if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
    return response.json()
  }, [])

  /**
   * Settings change on screen immediately instead of waiting for the next
   * once-a-second broadcast. While a save is in flight, broadcasts keep the
   * local settings so a tick sent just before the save can't flip them back.
   */
  const updateSettings = useCallback(
    async (patch: Partial<Settings>) => {
      saving.current += 1
      setSnapshot((s) => (s ? { ...s, settings: { ...s.settings, ...patch } } : s))
      try {
        const saved = await api<Settings>('/api/settings', { method: 'PUT', body: patch })
        setSnapshot((s) => (s ? { ...s, settings: saved } : s))
      } finally {
        saving.current -= 1
      }
    },
    [api],
  )

  return { snapshot, connection, api, updateSettings }
}
