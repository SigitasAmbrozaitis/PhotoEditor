/** Render the real app (routes + providers) against a fake API. */
import { QueryClient } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import { AppRoutes, Providers } from '../App'
import type { Job, JobRequest, Style, StyleUpdate } from '../api/types'
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
  // One editable style, so saving, versions and conflicts behave like the real backend.
  let style: Style = structuredClone(fx.warmFilm)
  const newJob = (kind: Job['kind'], photoIds: string[]) => {
    const job = fx.makeJob({
      id: `j${String(jobs.length + 1).padStart(4, '0')}`,
      kind,
      status: 'running',
      title: `New ${kind} job`,
      progress: 0,
      completed: 0,
      total: photoIds.length,
      finished_at: null,
      items: photoIds.map((id) => ({
        photo_id: id,
        filename: `${id}.RAF`,
        status: 'queued' as const,
        message: null,
        output_path: null,
      })),
    })
    jobs.unshift(job)
    return job
  }
  return {
    'GET /api/health': () => ({ status: 'ok', version: '0.1.0' }),
    'GET /api/library': () => fx.library,
    'GET /api/library/folders': () => fx.folders,
    'GET /api/fs/dirs': ({ query }) => fx.dirListing(query.get('path')),
    'POST /api/library/import': ({ body }) => {
      const job = fx.makeImportJob({ status: 'running', completed: 0, progress: 0, finished_at: null, summary: null })
      job.folder = (body as { folder: string }).folder
      jobs.unshift(job)
      return job
    },
    'PUT /api/library/current': ({ body }) => ({ ...fx.library, folder: (body as { folder: string }).folder }),
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
    'GET /api/engine': () => fx.engine,
    'PUT /api/photos/:id/edit': ({ path, body }) => {
      const photo = fx.photos.find((p) => path.includes(`/${p.id}/`))!
      const detail = fx.photoDetail(photo)
      return {
        ...detail,
        photo: { ...detail.photo, image_version: `${photo.image_version}-edited` },
        edit: { ...detail.edit, adjustments: body, revision: 'r-edited' },
      }
    },
    'DELETE /api/photos/:id/edit': ({ path }) => {
      const photo = fx.photos.find((p) => path.includes(`/${p.id}/`))!
      const detail = fx.photoDetail({ ...photo, style_id: null, has_overrides: false })
      return { ...detail, edit: { ...detail.edit, adjustments: fx.neutralAdjustments(), overridden: [] } }
    },
    'GET /api/styles': () => fx.styleSummaries,
    'GET /api/styles/:id': () => style,
    'PUT /api/styles/:id': ({ body }) => {
      const { expected_version, change_note, ...changes } = body as StyleUpdate
      if (expected_version !== style.version) {
        return Response.json({ detail: `style is at version ${style.version}` }, { status: 409 })
      }
      const values = (changes.values as Record<string, unknown> | undefined) ?? style.values
      style = { ...style, ...changes, values, changed_parameters: values, version: style.version + 1, change_note } as Style
      return style
    },
    'POST /api/styles/:id/duplicate': () => ({ ...style, id: 'warm-film-copy', name: 'Warm Film (copy)', version: 1 }),
    'DELETE /api/styles/:id': () => ({ id: style.id, photos: style.photo_count }),
    'GET /api/styles/:id/history': () => fx.styleHistory,
    'GET /api/styles/:id/diff': () => fx.styleDiff,
    'POST /api/styles/:id/revert': ({ body }) => {
      style = { ...style, version: style.version + 1, change_note: `reverted to version ${(body as { version: number }).version}` }
      return style
    },
    'POST /api/styles/:id/report': () => fx.styleReport,
    'POST /api/styles/:id/samples': ({ body }) => newJob('render', (body as { photo_ids: string[] }).photo_ids),
    'GET /api/export-presets': () => fx.presets,
    'GET /api/jobs': () => jobs,
    'GET /api/jobs/:id': ({ path }) => jobs.find((j) => path.endsWith(`/${j.id}`)) ?? jobs[0],
    'POST /api/jobs': ({ body }) => {
      const request = body as JobRequest
      return newJob(request.kind, request.photo_ids)
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
