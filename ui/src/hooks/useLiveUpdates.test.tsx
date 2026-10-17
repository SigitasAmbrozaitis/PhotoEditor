import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChangeEvent } from '../api/types'
import * as fx from '../test/fixtures'
import { mockApi, renderApp } from '../test/render'
import { FLUSH_MS, RECONNECT_MS, useLiveUpdates } from './useLiveUpdates'

/** Just enough of EventSource: tests open, send and fail streams by hand. */
class FakeEventSource {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSED = 2
  static instances: FakeEventSource[] = []
  readyState = FakeEventSource.CONNECTING
  private listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>()

  readonly url: string

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
  }

  close() {
    this.readyState = FakeEventSource.CLOSED
  }

  emit(type: 'open' | 'error' | 'change', data = '') {
    if (type === 'open') this.readyState = FakeEventSource.OPEN
    for (const listener of this.listeners.get(type) ?? []) listener(new MessageEvent(type, { data }))
  }

  send(event: Partial<ChangeEvent> & Pick<ChangeEvent, 'kind'>) {
    this.emit('change', JSON.stringify({ seq: 1, ids: [], origin: 'ui', summary: null, ...event }))
  }
}

const latest = () => FakeEventSource.instances.at(-1)!

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterEach(() => {
  vi.useRealTimers()
})

function setup() {
  const client = new QueryClient()
  const invalidate = vi.spyOn(client, 'invalidateQueries').mockResolvedValue()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const hook = renderHook(() => useLiveUpdates(), { wrapper })
  const keys = () => invalidate.mock.calls.map(([filters]) => filters?.queryKey)
  return { ...hook, invalidate, keys }
}

describe('useLiveUpdates', () => {
  it('refetches what changed, once per burst, and reports only what Claude did', () => {
    vi.useFakeTimers()
    const { result, keys } = setup()
    expect(latest().url).toBe('/api/events')
    act(() => {
      latest().emit('open')
      latest().send({ kind: 'photo_edit', ids: ['p1'], origin: 'ui' })
      latest().send({ kind: 'photo_edit', ids: ['p1'], origin: 'ui' })
    })
    expect(keys()).toEqual([])
    act(() => vi.advanceTimersByTime(FLUSH_MS))
    expect(keys()).toContainEqual(['photo', 'p1'])
    expect(keys().filter((k) => k?.[0] === 'photos')).toHaveLength(1)
    expect(result.current).toBeNull() // the user's own change: no toast
    act(() => {
      latest().send({ kind: 'style', ids: ['warm'], origin: 'ai' })
      vi.advanceTimersByTime(FLUSH_MS)
    })
    expect(result.current).toMatchObject({ styles: ['warm'] })
  })

  it('reconnects after the stream closes and then refetches everything it may have missed', () => {
    vi.useFakeTimers()
    const { invalidate } = setup()
    const first = latest()
    act(() => {
      first.emit('open')
      first.readyState = FakeEventSource.CLOSED
      first.emit('error')
    })
    expect(FakeEventSource.instances).toHaveLength(1)
    act(() => vi.advanceTimersByTime(RECONNECT_MS[0]!))
    expect(FakeEventSource.instances).toHaveLength(2)
    act(() => latest().emit('open'))
    expect(invalidate).toHaveBeenCalledWith()
  })

  it('does nothing without EventSource', () => {
    vi.stubGlobal('EventSource', undefined)
    const { result } = setup()
    expect(result.current).toBeNull()
  })

  it("shows a toast for Claude's changes in the app, with a link", async () => {
    mockApi()
    const { client } = renderApp('/library')
    const photo = fx.photos[0]!
    // The name comes from the photo list the Library has loaded.
    await waitFor(() => expect(client.getQueriesData({ queryKey: ['photos'] }).some(([, data]) => data)).toBe(true))
    act(() => {
      latest().emit('open')
      latest().send({ kind: 'photo_edit', ids: [photo.id], origin: 'ai' })
    })
    const toast = await screen.findByText(`Claude edited ${photo.filename}`)
    const root = toast.closest('li')!
    expect(within(root).getByRole('link', { name: 'Show' })).toHaveAttribute('href', `/library/${photo.id}`)
  })
})
