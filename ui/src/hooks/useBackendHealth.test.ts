import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useBackendHealth } from './useBackendHealth'

describe('useBackendHealth', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts in the checking state', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})))
    const { result } = renderHook(() => useBackendHealth(1000))
    expect(result.current).toEqual({ kind: 'checking' })
  })

  it('goes offline when the backend stops, and back online when it returns', async () => {
    let up = true
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        if (!up) throw new TypeError('Failed to fetch')
        return Response.json({ status: 'ok', version: '0.1.0' })
      }),
    )
    const { result } = renderHook(() => useBackendHealth(1000))
    await waitFor(() => expect(result.current).toEqual({ kind: 'online', version: '0.1.0' }))

    up = false
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    await waitFor(() => expect(result.current).toEqual({ kind: 'offline' }))

    up = true
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    await waitFor(() => expect(result.current).toEqual({ kind: 'online', version: '0.1.0' }))
  })

  it('stops polling after unmount', async () => {
    const fetchMock = vi.fn(async () => Response.json({ status: 'ok', version: '0.1.0' }))
    vi.stubGlobal('fetch', fetchMock)
    const { unmount } = renderHook(() => useBackendHealth(1000))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    unmount()
    await vi.advanceTimersByTimeAsync(5000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
