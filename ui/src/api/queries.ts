/** TanStack Query hooks for every API resource. Components never call fetch directly. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { api } from './client'
import type {
  AdjustmentParams,
  DirListing,
  EngineInfo,
  ExportPreset,
  ImportRequest,
  Job,
  JobRequest,
  LibraryFolder,
  LibraryInfo,
  PhotoDetail,
  PhotoPage,
  PhotoSort,
  SortOrder,
  ConsistencyReport,
  Style,
  StyleCreate,
  StyleDeleted,
  StyleDiff,
  StyleFromPhoto,
  StyleSummary,
  StyleUpdate,
  StyleUpdateFromPhoto,
  StyleVersionInfo,
} from './types'

export interface PhotoQuery {
  styleId?: string
  minRating?: number
  sort?: PhotoSort
  order?: SortOrder
  offset?: number
  limit?: number
}

export const queryKeys = {
  engine: ['engine'] as const,
  library: ['library'] as const,
  folders: ['library', 'folders'] as const,
  dirs: (path: string | null) => ['dirs', path] as const,
  photos: (q: PhotoQuery) => ['photos', q] as const,
  photo: (id: string) => ['photo', id] as const,
  styles: ['styles'] as const,
  style: (id: string) => ['style', id] as const,
  styleHistory: (id: string) => ['style', id, 'history'] as const,
  styleDiff: (id: string, a: number, b: number) => ['style', id, 'diff', a, b] as const,
  presets: ['presets'] as const,
  jobs: ['jobs'] as const,
  job: (id: string) => ['job', id] as const,
}

/** Poll quickly while something is running, otherwise not at all. */
export const JOB_POLL_MS = 500
export const isActive = (job: Job) => job.status === 'queued' || job.status === 'running'
/** While an import runs, the grid refreshes this often so thumbnails fill in as they arrive. */
export const IMPORT_REFRESH_MS = 1000

export function useLibrary() {
  return useQuery({ queryKey: queryKeys.library, queryFn: () => api.get<LibraryInfo>('/api/library') })
}

export function useLibraryFolders() {
  return useQuery({ queryKey: queryKeys.folders, queryFn: () => api.get<LibraryFolder[]>('/api/library/folders') })
}

/** Folder browser listing; `null` lists the drives. */
export function useDirListing(path: string | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.dirs(path),
    queryFn: () => api.get<DirListing>('/api/fs/dirs', { path: path ?? undefined }),
    enabled,
    staleTime: 0,
  })
}

/** Refresh everything that shows library contents (after an import, or when switching folders). */
function invalidateLibrary(client: ReturnType<typeof useQueryClient>) {
  void client.invalidateQueries({ queryKey: queryKeys.library })
  void client.invalidateQueries({ queryKey: ['photos'] })
  void client.invalidateQueries({ queryKey: ['photo'] })
}

export function useImportFolder() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (request: ImportRequest) => api.post<Job>('/api/library/import', request),
    onSuccess: (job) => {
      client.setQueryData(queryKeys.job(job.id), job)
      void client.invalidateQueries({ queryKey: queryKeys.jobs })
      invalidateLibrary(client)
    },
  })
}

export function useOpenFolder() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (folder: string) => api.put<LibraryInfo>('/api/library/current', { folder }),
    onSuccess: (info) => {
      client.setQueryData(queryKeys.library, info)
      invalidateLibrary(client)
    },
  })
}

/** The newest import job, and whether it is still running. Polls via useJobs while one is active. */
export function useLatestImport() {
  const jobs = useJobs()
  const latest = jobs.data?.find((j) => j.kind === 'import')
  return { job: latest, running: latest ? isActive(latest) : false }
}

export function usePhotos(q: PhotoQuery = {}, { refetchInterval }: { refetchInterval?: number | false } = {}) {
  return useQuery({
    refetchInterval,
    queryKey: queryKeys.photos(q),
    queryFn: ({ signal }) =>
      api.get<PhotoPage>(
        '/api/photos',
        {
          style_id: q.styleId,
          min_rating: q.minRating || undefined,
          sort: q.sort,
          order: q.order,
          offset: q.offset,
          limit: q.limit ?? 500,
        },
        signal,
      ),
    placeholderData: (previous) => previous,
  })
}

export function usePhotoDetail(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.photo(id ?? ''),
    queryFn: () => api.get<PhotoDetail>(`/api/photos/${encodeURIComponent(id ?? '')}`),
    enabled: Boolean(id),
  })
}

/** What the render engine supports (e.g. which parameters arrive in later phases). Never changes at runtime. */
export function useEngine() {
  return useQuery({ queryKey: queryKeys.engine, queryFn: () => api.get<EngineInfo>('/api/engine'), staleTime: Infinity })
}

function storeDetail(client: ReturnType<typeof useQueryClient>, detail: PhotoDetail) {
  client.setQueryData(queryKeys.photo(detail.photo.id), detail)
  // Grid thumbnails and the "edited" marker come from the list: refresh it.
  void client.invalidateQueries({ queryKey: ['photos'] })
}

/** Save a photo's full adjustments; the response is the updated detail (new image version for the preview). */
export function useSaveEdit(photoId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (params: AdjustmentParams) =>
      api.put<PhotoDetail>(`/api/photos/${encodeURIComponent(photoId)}/edit`, params),
    onSuccess: (detail) => storeDetail(client, detail),
  })
}

export function useResetEdit(photoId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api.delete<PhotoDetail>(`/api/photos/${encodeURIComponent(photoId)}/edit`),
    onSuccess: (detail) => storeDetail(client, detail),
  })
}

export function useStyles() {
  return useQuery({ queryKey: queryKeys.styles, queryFn: () => api.get<StyleSummary[]>('/api/styles') })
}

export function useStyle(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.style(id ?? ''),
    queryFn: () => api.get<Style>(`/api/styles/${encodeURIComponent(id ?? '')}`),
    enabled: Boolean(id),
  })
}

const styleUrl = (id: string) => `/api/styles/${encodeURIComponent(id)}`

/** A style changed: its views, the list, and every photo (their look and style follow the style). */
function styleChanged(client: ReturnType<typeof useQueryClient>, style?: Style) {
  if (style) client.setQueryData(queryKeys.style(style.id), style)
  void client.invalidateQueries({ queryKey: queryKeys.styles })
  void client.invalidateQueries({ queryKey: ['style'] })
  void client.invalidateQueries({ queryKey: ['photos'] })
  void client.invalidateQueries({ queryKey: ['photo'] })
  void client.invalidateQueries({ queryKey: queryKeys.jobs })
}

export function useCreateStyle() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (request: StyleCreate) => api.post<Style>('/api/styles', request),
    onSuccess: (style) => styleChanged(client, style),
  })
}

export function useCreateStyleFromPhoto() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (request: StyleFromPhoto) => api.post<Style>('/api/styles/from-photo', request),
    onSuccess: (style) => styleChanged(client, style),
  })
}

/** Save a change to a style. A 409 means someone else saved first (reload, then redo the change). */
export function useUpdateStyle(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (update: StyleUpdate) => api.put<Style>(styleUrl(id), update),
    onSuccess: (style) => styleChanged(client, style),
  })
}

export function useUpdateStyleFromPhoto(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (request: StyleUpdateFromPhoto) => api.post<Style>(`${styleUrl(id)}/from-photo`, request),
    onSuccess: (style) => styleChanged(client, style),
  })
}

export function useDuplicateStyle(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (name?: string) => api.post<Style>(`${styleUrl(id)}/duplicate`, { name: name ?? null }),
    onSuccess: (style) => styleChanged(client, style),
  })
}

export function useDeleteStyle(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api.delete<StyleDeleted>(styleUrl(id)),
    onSuccess: () => {
      client.removeQueries({ queryKey: queryKeys.style(id) })
      styleChanged(client)
    },
  })
}

export function useRevertStyle(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (request: { version: number; expected_version: number }) =>
      api.post<Style>(`${styleUrl(id)}/revert`, request),
    onSuccess: (style) => styleChanged(client, style),
  })
}

export function useStyleHistory(id: string) {
  return useQuery({
    queryKey: queryKeys.styleHistory(id),
    queryFn: () => api.get<StyleVersionInfo[]>(`${styleUrl(id)}/history`),
  })
}

export function useStyleDiff(id: string, a: number | undefined, b: number | undefined) {
  return useQuery({
    queryKey: queryKeys.styleDiff(id, a ?? 0, b ?? 0),
    queryFn: () => api.get<StyleDiff>(`${styleUrl(id)}/diff`, { a, b }),
    enabled: a !== undefined && b !== undefined && a !== b,
  })
}

/** The consistency report (a POST, because measuring may take a moment; run on demand). */
export function useStyleReport(id: string) {
  return useMutation({
    mutationFn: (photoIds?: string[]) =>
      api.post<ConsistencyReport>(`${styleUrl(id)}/report`, { photo_ids: photoIds ?? null }),
  })
}

export function useRenderSamples(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (photoIds: string[]) => api.post<Job>(`${styleUrl(id)}/samples`, { photo_ids: photoIds }),
    onSuccess: (job) => {
      client.setQueryData(queryKeys.job(job.id), job)
      void client.invalidateQueries({ queryKey: queryKeys.jobs })
    },
  })
}

/** Give one photo a style right away (null removes it). */
export function useSetPhotoStyle(photoId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (styleId: string | null) =>
      api.put<PhotoDetail>(`/api/photos/${encodeURIComponent(photoId)}/style`, { style_id: styleId }),
    onSuccess: (detail) => {
      storeDetail(client, detail)
      void client.invalidateQueries({ queryKey: queryKeys.styles })
      void client.invalidateQueries({ queryKey: queryKeys.jobs })
    },
  })
}

export function usePresets() {
  return useQuery({ queryKey: queryKeys.presets, queryFn: () => api.get<ExportPreset[]>('/api/export-presets') })
}

export function useJobs() {
  return useQuery({
    queryKey: queryKeys.jobs,
    queryFn: () => api.get<Job[]>('/api/jobs'),
    refetchInterval: (query) => (query.state.data?.some(isActive) ? JOB_POLL_MS : false),
  })
}

export function useJob(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.job(id ?? ''),
    queryFn: () => api.get<Job>(`/api/jobs/${encodeURIComponent(id ?? '')}`),
    enabled: Boolean(id),
    refetchInterval: (query) => (query.state.data && isActive(query.state.data) ? JOB_POLL_MS : false),
  })
}

export function useCreateJob() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (request: JobRequest) => api.post<Job>('/api/jobs', request),
    onSuccess: (job) => {
      client.setQueryData(queryKeys.job(job.id), job)
      void client.invalidateQueries({ queryKey: queryKeys.jobs })
    },
  })
}

/** Jobs that change photos' edits; when one finishes, everything showing photos or styles refreshes. */
const EDITING_JOBS = new Set<Job['kind']>(['apply_style', 'apply_and_export'])

/** Mounted once (in the layout): refresh photos and styles when an apply job finishes, wherever it started. */
export function useRefreshAfterJobs() {
  const client = useQueryClient()
  const jobs = useJobs()
  const running = useRef(new Set<string>())
  useEffect(() => {
    let finished = false
    for (const job of jobs.data ?? []) {
      if (!EDITING_JOBS.has(job.kind)) continue
      if (isActive(job)) running.current.add(job.id)
      else if (running.current.delete(job.id)) finished = true
    }
    if (finished) {
      void client.invalidateQueries({ queryKey: ['photos'] })
      void client.invalidateQueries({ queryKey: ['photo'] })
      void client.invalidateQueries({ queryKey: queryKeys.styles })
      void client.invalidateQueries({ queryKey: ['style'] })
    }
  }, [jobs.data, client])
}

export function useCancelJob() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post<Job>(`/api/jobs/${encodeURIComponent(id)}/cancel`),
    onSuccess: (job) => {
      client.setQueryData(queryKeys.job(job.id), job)
      void client.invalidateQueries({ queryKey: queryKeys.jobs })
    },
  })
}
