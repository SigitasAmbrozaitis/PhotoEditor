import { useEffect, useState } from 'react'
import { fetchHealth } from '../api/health'

export type BackendState =
  | { kind: 'checking' }
  | { kind: 'online'; version: string }
  | { kind: 'offline' }

export const HEALTH_POLL_MS = 5000

/** Polls /api/health so the UI notices when the backend goes down or comes back. */
export function useBackendHealth(pollMs: number = HEALTH_POLL_MS): BackendState {
  const [state, setState] = useState<BackendState>({ kind: 'checking' })

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()

    const check = async () => {
      try {
        const health = await fetchHealth(controller.signal)
        if (!cancelled) setState({ kind: 'online', version: health.version })
      } catch {
        if (!cancelled) setState({ kind: 'offline' })
      }
    }

    void check()
    const timer = window.setInterval(() => void check(), pollMs)
    return () => {
      cancelled = true
      controller.abort()
      window.clearInterval(timer)
    }
  }, [pollMs])

  return state
}
