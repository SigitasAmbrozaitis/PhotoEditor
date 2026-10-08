/** Minimal typed fetch wrapper for the backend API. */

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed with HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

type Query = Record<string, string | number | boolean | null | undefined>

export function buildUrl(path: string, query?: Query): string {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method,
    signal,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    let detail: unknown = undefined
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail
    } catch {
      // Non-JSON error body.
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string, query?: Query, signal?: AbortSignal) => request<T>('GET', buildUrl(path, query), undefined, signal),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}

// Image URLs (served as JPEG by the backend). `version` (Photo.image_version) changes whenever the photo renders
// differently, so the browser never shows a stale cached image after an edit.
export const imageUrls = {
  thumbnail: (photoId: string, version?: string) =>
    buildUrl(`/api/photos/${encodeURIComponent(photoId)}/thumbnail`, { v: version }),
  preview: (photoId: string, opts: { before?: boolean; size?: number; version?: string } = {}) =>
    buildUrl(`/api/photos/${encodeURIComponent(photoId)}/preview`, {
      before: opts.before ? true : undefined,
      size: opts.size,
      v: opts.before ? undefined : opts.version,
    }),
  /** The camera's own JPEG next to a RAW (for comparing with the default look). */
  sidecar: (photoId: string, size = 1600) =>
    buildUrl(`/api/photos/${encodeURIComponent(photoId)}/sidecar`, { size }),
}
