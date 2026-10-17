import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import type { ChangeEvent } from '../api/types'
import { addActivity, invalidationsFor, uniqueKeys, type Activity } from './liveUpdates'

export const EVENTS_URL = '/api/events'
/** Events are gathered this long, so a burst (a style applied to 100 photos) refetches each query once. */
export const FLUSH_MS = 150
/** Waits before reconnecting after the stream closed for good (the browser retries dropped ones itself). */
export const RECONNECT_MS = [1000, 2000, 5000, 10_000, 30_000]

/** Follows the server's change events (P7.16): refetches what changed, whoever changed it, and returns what
 * Claude changed lately for the activity toast. Without EventSource (old browsers, tests) it does nothing. */
export function useLiveUpdates(): Activity | null {
  const client = useQueryClient()
  const [activity, setActivity] = useState<Activity | null>(null)

  useEffect(() => {
    if (typeof EventSource === 'undefined') return
    let source: EventSource | null = null
    let attempt = 0
    let missedEvents = false
    let flushTimer: number | undefined
    let retryTimer: number | undefined
    const pending: ChangeEvent[] = []

    const flush = () => {
      flushTimer = undefined
      const events = pending.splice(0)
      for (const queryKey of uniqueKeys(events.flatMap(invalidationsFor))) {
        void client.invalidateQueries({ queryKey })
      }
      setActivity((previous) => addActivity(previous, events, Date.now()))
    }

    const connect = () => {
      source = new EventSource(EVENTS_URL)
      source.addEventListener('open', () => {
        attempt = 0
        // Whatever changed while we weren't listening: refetch it all.
        if (missedEvents) void client.invalidateQueries()
        missedEvents = false
      })
      source.addEventListener('change', (message: MessageEvent<string>) => {
        pending.push(JSON.parse(message.data) as ChangeEvent)
        flushTimer ??= window.setTimeout(flush, FLUSH_MS)
      })
      source.addEventListener('error', () => {
        missedEvents = true
        if (source?.readyState !== EventSource.CLOSED) return
        source.close()
        retryTimer = window.setTimeout(connect, RECONNECT_MS[Math.min(attempt++, RECONNECT_MS.length - 1)])
      })
    }

    connect()
    return () => {
      source?.close()
      window.clearTimeout(flushTimer)
      window.clearTimeout(retryTimer)
    }
  }, [client])

  return activity
}
