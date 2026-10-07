import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

function mockFetch(impl: () => Promise<Response>) {
  const fn = vi.fn(impl)
  vi.stubGlobal('fetch', fn)
  return fn
}

describe('App shell', () => {
  it('shows the product name', async () => {
    mockFetch(async () => Response.json({ status: 'ok', version: '0.1.0' }))
    render(<App />)
    expect(screen.getByRole('heading', { name: 'PhotoEditor' })).toBeInTheDocument()
    await screen.findByText('backend v0.1.0')
  })

  it('shows the backend version when the backend is online', async () => {
    const fetchMock = mockFetch(async () => Response.json({ status: 'ok', version: '1.2.3' }))
    render(<App />)
    expect(await screen.findByText('backend v1.2.3')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('shows an offline badge when the backend is unreachable', async () => {
    mockFetch(async () => {
      throw new TypeError('Failed to fetch')
    })
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('backend offline')
  })

  it('shows an offline badge when the backend returns an error', async () => {
    mockFetch(async () => new Response('boom', { status: 500 }))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('backend offline')
  })
})
