/** Render the real app (routes + providers) against a fake API. */
import { QueryClient } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import { AppRoutes, Providers } from '../App'
import type { Job, JobRequest } from '../api/types'
import * as fx from './fixtures'

export interface ApiCall {
  method: string
  path: string
  query: URLSearchParams
  body: unknown
}

type Handler = (call: ApiCall) => unknown

/** Default fake backend: answers every endpoint the UI uses from the fixtures. */
export function defaultHandlers(): Record<string, Handler> {
  const jobs: Job[] = [fx.makeJob()]
  return {
    'GET /api/health': () => ({ status: 'ok', version: '0.1.0' }),
    'GET /api/library': () => fx.library,
    'GET /api/photos': ({ query }) => {
      let items = [...fx.photos]
      const style = query.get('style_id')
      if (style) items = items.filter((p) => (style === 'none' ? !p.style_id : p.style_id === style))
      if (query.get('sort') === 'name' && query.get('order') === 'desc') items.reverse()
      return { items, total: items.length, offset: 0, limit: 500 }
    },
    'GET /api/photos/:id': ({ path }) => {
      const photo = fx.photos.find((p) => path.endsWith(`/${p.id}`))
      return photo ? fx.photoDetail(photo) : new Response(JSON.stringify({ detail: 'not found' }), { status: 404 })
    },
    'GET /api/styles': () => fx.styleSummaries,
    'GET /api/styles/:id': () => fx.warmFilm,
    'GET /api/export-presets': () => fx.presets,
    'GET /api/jobs': () => jobs,
    'GET /api/jobs/:id': ({ path }) => jobs.find((j) => path.endsWith(`/${j.id}`)) ?? jobs[0],
    'POST /api/jobs': ({ body }) => {
      const request = body as JobRequest
      const job = fx.makeJob({
        id: `j${String(jobs.length + 1).padStart(4, '0')}`,
        kind: request.kind,
        status: 'running',
        title: `New ${request.kind} job`,
        progress: 0,
        completed: 0,
        total: request.photo_ids.length,
        finished_at: null,
        items: request.photo_ids.map((id) => ({
          photo_id: id,
          filename: `${id}.RAF`,
          status: 'queued' as const,
          message: null,
          output_path: null,
        })),
      })
      jobs.unshift(job)
      return job
    },
    'POST /api/jobs/:id/cancel': ({ path }) => {
      const job = jobs.find((j) => path.includes(`/${j.id}/`)) ?? jobs[0]!
      job.status = 'cancelled'
      return job
    },
  }
}

function match(pattern: string, method: string, path: string): boolean {
  const [m, p] = pattern.split(' ') as [string, string]
  if (m !== method) return false
  const re = new RegExp(`^${p.replace(/:[a-z]+/g, '[^/]+')}$`)
  return re.test(path)
}

/** Install a fetch stub. Returns the list of calls made, for assertions. */
export function mockApi(overrides: Record<string, Handler> = {}): ApiCall[] {
  const handlers = { ...defaultHandlers(), ...overrides }
  // More specific (longer) patterns first so '/api/jobs/:id/cancel' beats '/api/jobs/:id'.
  const patterns = Object.keys(handlers).sort((a, b) => b.length - a.length)
  const calls: ApiCall[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), 'http://localhost')
      const method = (init?.method ?? 'GET').toUpperCase()
      const body = init?.body ? JSON.parse(String(init.body)) : undefined
      const call: ApiCall = { method, path: url.pathname, query: url.searchParams, body }
      calls.push(call)
      const pattern = patterns.find((p) => match(p, method, url.pathname))
      if (!pattern) return new Response(JSON.stringify({ detail: `no mock for ${method} ${url.pathname}` }), { status: 404 })
      const result = handlers[pattern]!(call)
      return result instanceof Response ? result : Response.json(result)
    }),
  )
  return calls
}

export function renderApp(route: string, { selection }: { selection?: string[] } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  if (selection) sessionStorage.setItem('photoedit.selection', JSON.stringify(selection))
  const user = userEvent.setup()
  const utils = render(
    <MemoryRouter initialEntries={[route]}>
      <Providers client={client}>
        <AppRoutes />
      </Providers>
    </MemoryRouter>,
  )
  return { user, client, ...utils }
}
