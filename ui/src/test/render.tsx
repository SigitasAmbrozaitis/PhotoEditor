/** Render the real app (routes + providers) against a fake API. */
import { QueryClient } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import { AppRoutes, Providers } from '../App'
import type {
  ExportPreset,
  ExportRequest,
  ExportReview,
  Geometry,
  GeometryChange,
  Job,
  JobRequest,
  PresetUpdate,
  ReviewItem,
  ReviewItemUpdate,
  ReviewSettings,
  ReviewSubjectUpdate,
  Style,
  StyleUpdate,
  CropSuggestionRequest,
  SubjectBox,
  SubjectInfo,
} from '../api/types'
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
  let presets: ExportPreset[] = structuredClone(fx.presets)
  const destinations: string[] = []
  // Subjects set by hand, per photo id; the others are fx.detectedSubject.
  const manual = new Map<string, SubjectBox>()
  const detected = new Set<string>()
  const photoIdOf = (path: string) => path.split('/')[3]!
  const subjectOf = (id: string): SubjectInfo => {
    const box = manual.get(id)
    return box ? { ...fx.detectedSubject, source: 'manual', box, kind: null, score: null } : fx.detectedSubject
  }
  // One open review; decisions change it like the backend does (a fix approves).
  let review: ExportReview | null = fx.makeReview()
  let reviewSettings: ReviewSettings = {
    no_subject: true,
    uncertain: true,
    min_score: 0.5,
    ambiguous: true,
    ambiguity: 0.75,
    cut_off: true,
    zoom_limit: true,
  }
  const notFound = () => Response.json({ detail: 'review not found' }, { status: 404 })
  const changeItem = (path: string, change: (item: ReviewItem) => ReviewItem) => {
    if (!review || !path.includes(`/${review.id}/`)) return notFound()
    const photoId = path.split('/')[5]!
    const items = review.items.map((i) => (i.photo_id === photoId ? change(i) : i))
    review = { ...review, items, counts: fx.reviewCounts(items) }
    return review
  }
  const slug = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
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
        ...fx.noOutput,
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
    // Like core's apply_change, simplified: an angle shrinks the crop to the middle 80 %; an explicit crop that
    // reaches a straightened photo's corners is refused.
    'POST /api/photos/:id/geometry/preview': ({ body }) => {
      const { geometry, change } = body as { geometry: Geometry; change: Partial<GeometryChange> }
      if (change.reset) return fx.neutralAdjustments().geometry
      const next: Geometry = { ...geometry }
      for (const key of ['flip_horizontal', 'flip_vertical', 'rotate', 'angle', 'aspect'] as const) {
        if (key in change) (next as Record<string, unknown>)[key] = change[key]
      }
      if ('angle' in change && change.angle) next.crop = { left: 0.1, top: 0.1, right: 0.9, bottom: 0.9 }
      if (change.crop) {
        const c = change.crop
        if (next.angle && (c.left === 0 || c.top === 0 || c.right === 1 || c.bottom === 1)) {
          return Response.json({ detail: 'the crop reaches outside the photo (blank corners)' }, { status: 400 })
        }
        next.crop = c
      }
      return next
    },
    'GET /api/photos/:id/subject': ({ path }) => subjectOf(photoIdOf(path)),
    // Detected already, except p003 until it is asked to detect.
    'GET /api/photos/:id/analysis': ({ path, query }) => {
      const id = photoIdOf(path)
      if (id === 'p003' && query.get('detect') !== 'true' && !detected.has(id)) {
        return { ...fx.analysis, detected: false, source: 'none', kind: null, score: null, box: null, candidates: [], notes: ['Not detected yet.'] }
      }
      detected.add(id)
      const box = manual.get(id)
      return box ? { ...fx.analysis, source: 'manual', kind: null, score: null, box } : fx.analysis
    },
    'PUT /api/photos/:id/note': ({ path, body }) => {
      const photo = fx.photos.find((p) => path.includes(`/${p.id}/`))!
      const text = (body as { text: string | null }).text
      return { ...fx.photoDetail(photo), note: text ? { text, written_at: '2026-10-16T12:00:00Z' } : null }
    },
    'PUT /api/photos/:id/subject': ({ path, body }) => {
      const box = (body as { box: SubjectBox | null }).box
      if (box) manual.set(photoIdOf(path), box)
      else manual.delete(photoIdOf(path))
      return subjectOf(photoIdOf(path))
    },
    // A crop half the frame wide divided by the zoom, centered on the subject; zoom stops at 2.5×.
    'POST /api/photos/:id/suggest-crop': ({ path, body }) => {
      const request = body as CropSuggestionRequest
      const info = subjectOf(photoIdOf(path))
      const zoom = Math.min(request.zoom ?? 1, 2.5)
      const half = 0.25 / zoom
      const cx = Math.min(1 - half, Math.max(half, info.box ? (info.box.left + info.box.right) / 2 : 0.5))
      return {
        crop: { left: cx - half, top: 0, right: cx + half, bottom: 1 },
        aspect: request.aspect,
        placement: request.placement ?? 'centered',
        zoom,
        source: info.source,
        kind: info.kind,
        subject: info.box,
        warnings: (request.zoom ?? 1) > 2.5 ? ['zoom stopped at 2.50×, where the subject fills the crop'] : [],
      }
    },
    'GET /api/photos/:id/zoom/:level': ({ path }) => ({
      level: Number(path.split('/').at(-1)),
      state: 'ready',
      width: path.endsWith('/100') ? 1200 : 600,
      height: path.endsWith('/100') ? 800 : 400,
      tile_size: 512,
    }),
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
    'PUT /api/photos/:id/style': ({ path, body }) => {
      const photo = fx.photos.find((p) => path.includes(`/${p.id}/`))!
      return fx.photoDetail({ ...photo, style_id: (body as { style_id: string | null }).style_id })
    },
    'POST /api/styles/from-photo': ({ body }) => {
      const request = body as { name: string; photo_id: string }
      return { ...style, id: 'new-look', name: request.name, version: 1, test_photo_ids: [request.photo_id] }
    },
    'POST /api/styles/:id/from-photo': () => {
      style = { ...style, version: style.version + 1, change_note: 'updated from a photo' }
      return style
    },
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
    'GET /api/export-presets': () => presets,
    'POST /api/export-presets': ({ body }) => {
      const request = body as Pick<ExportPreset, 'name' | 'description' | 'target' | 'settings'>
      const preset: ExportPreset = { ...request, id: slug(request.name), builtin: false, version: 1, error: null }
      presets = [...presets, preset]
      return Response.json(preset, { status: 201 })
    },
    'POST /api/export-presets/:id/duplicate': ({ path, body }) => {
      const source = presets.find((p) => path.includes(`/${p.id}/`))!
      const name = (body as { name?: string }).name ?? `${source.name} copy`
      const copy: ExportPreset = { ...source, id: slug(name), name, builtin: false, version: 1 }
      presets = [...presets, copy]
      return Response.json(copy, { status: 201 })
    },
    'PUT /api/export-presets/:id': ({ path, body }) => {
      const { expected_version, ...changes } = body as PresetUpdate
      const current = presets.find((p) => path.endsWith(`/${p.id}`))!
      if (current.builtin) return Response.json({ detail: 'built-in' }, { status: 400 })
      if (expected_version !== current.version) return Response.json({ detail: 'conflict' }, { status: 409 })
      const updated = { ...current, ...changes, version: current.version + 1 } as ExportPreset
      presets = presets.map((p) => (p.id === updated.id ? updated : p))
      return updated
    },
    'DELETE /api/export-presets/:id': ({ path }) => {
      presets = presets.filter((p) => !path.endsWith(`/${p.id}`))
      return new Response(null, { status: 204 })
    },
    'GET /api/export/destinations': () => destinations,
    'POST /api/export/destination-check': ({ body }) => {
      const path = (body as { path: string }).path
      if (!/^([A-Za-z]:[\\/]|\/)/.test(path)) {
        return { path, exists: false, ok: false, reason: 'the destination must be a full folder path' }
      }
      if (fx.library.folder && path.startsWith(fx.library.folder)) {
        return { path, exists: true, ok: false, reason: `${path} is inside the photo folder ${fx.library.folder}` }
      }
      return { path, exists: false, ok: true, reason: null }
    },
    'POST /api/export/plan': ({ body }) => fx.exportPlan(body as ExportRequest),
    'POST /api/export/reveal': () => new Response(null, { status: 204 }),
    'GET /api/reviews': () =>
      review
        ? [
            {
              id: review.id,
              created_at: review.created_at,
              updated_at: review.updated_at,
              preset_id: review.preset_id,
              destination: review.destination,
              counts: review.counts,
            },
          ]
        : [],
    'GET /api/reviews/:id': ({ path }) => (review && path.endsWith(`/${review.id}`) ? review : notFound()),
    'DELETE /api/reviews/:id': () => {
      review = null
      return new Response(null, { status: 204 })
    },
    'PATCH /api/reviews/:id/items/:pid': ({ path, body }) => {
      const update = body as ReviewItemUpdate
      return changeItem(path, (item) => {
        let next = { ...item, revision: `${item.revision}+` }
        if ('zoom' in update) {
          const zoom = update.zoom ?? item.auto_zoom
          next = { ...next, zoom, zoom_override: update.zoom ?? null, approved: true }
          next.decode = zoom > item.limits.fast ? 'full' : 'half'
        }
        if ('position' in update) {
          const position = update.position ?? null
          const w = next.crop.right - next.crop.left
          const left = position ? Math.min(1 - w, Math.max(0, position.x - w / 2)) : item.crop.left
          next = { ...next, position, approved: true, crop: { ...next.crop, left, right: left + w } }
        }
        if (update.approved !== undefined && update.approved !== null) next = { ...next, approved: update.approved }
        return next
      })
    },
    'PUT /api/reviews/:id/items/:pid/subject': ({ path, body }) => {
      const update = body as ReviewSubjectUpdate
      return changeItem(path, (item) => {
        const chosen = update.candidate ?? null
        const box = chosen !== null ? item.candidates[chosen]!.box : (update.box ?? null)
        const manual = box !== null
        const zoomLimited = item.reasons.some((r) => r.code === 'zoom_limit')
        return {
          ...item,
          subject: manual ? 'manual' : item.candidates.length ? 'detected' : 'none',
          subject_box: box ?? item.candidates[0]?.box ?? null,
          candidates: item.candidates.map((c) => ({ ...c, chosen: chosen === null ? c.index === 0 : c.index === chosen })),
          reasons: manual ? item.reasons.filter((r) => r.code === 'zoom_limit') : item.reasons,
          status: manual && !zoomLimited ? 'ready' : item.status,
          approved: true,
          revision: `${item.revision}+`,
        }
      })
    },
    'POST /api/reviews/:id/export': ({ body }) => {
      if (!review) return notFound()
      const scope = (body as { scope?: string }).scope ?? 'approved'
      const chosen = review.items.filter(
        (i) => i.status !== 'unusable' && (scope === 'all' || i.status === 'ready' || i.approved),
      )
      const ids = new Set(chosen.map((i) => i.photo_id))
      const items = review.items.filter((i) => !ids.has(i.photo_id))
      review = { ...review, items, counts: fx.reviewCounts(items) }
      return Response.json(newJob('export', [...ids]), { status: 201 })
    },
    // The crop at each zoom step: a frame half the photo wide at 1×, shrinking around its center.
    'GET /api/reviews/:id/items/:pid/frames': ({ path }) => {
      const photoId = path.split('/')[5]!
      const item = review?.items.find((i) => i.photo_id === photoId)
      if (!item) return notFound()
      const cx = (item.crop.left + item.crop.right) / 2
      const steps = Math.round((item.limits.quality - 1) / 0.01)
      return {
        photo_id: photoId,
        frames: Array.from({ length: steps + 1 }, (_, i) => {
          const zoom = 1 + (item.limits.quality - 1) * (i / steps)
          const half = 0.25 / zoom
          return { zoom: Math.round(zoom * 10000) / 10000, crop: { left: cx - half, top: 0.5 - 0.5 / zoom, right: cx + half, bottom: 0.5 + 0.5 / zoom } }
        }),
      }
    },
    'GET /api/review-settings': () => reviewSettings,
    'PUT /api/review-settings': ({ body }) => {
      reviewSettings = body as ReviewSettings
      return reviewSettings
    },
    'GET /api/jobs': () => jobs,
    'GET /api/jobs/:id': ({ path }) => jobs.find((j) => path.endsWith(`/${j.id}`)) ?? jobs[0],
    'POST /api/jobs': ({ body }) => {
      const request = body as JobRequest
      if ('destination' in request && !destinations.includes(request.destination)) destinations.unshift(request.destination)
      const job = newJob(request.kind, request.photo_ids)
      if (request.kind === 'prepare_export') {
        // Prepared at once: the review the dialog opens is the fake one.
        Object.assign(job, { status: 'done', progress: 1, review_id: review?.id ?? 'abcdef123456' })
      }
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
