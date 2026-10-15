/** TanStack Query hooks for every API resource. Components never call fetch directly. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { api } from './client'
import type {
  AdjustmentParams,
  DestinationCheck,
  DirListing,
  EngineInfo,
  ExportPlan,
  ExportPreset,
  ExportReview,
  ExportRequest,
  Geometry,
  GeometryChange,
  ImportRequest,
  Job,
  JobRequest,
  LibraryFolder,
  LibraryInfo,
  PhotoDetail,
  PhotoPage,
  PhotoSort,
  PresetCreate,
  PresetUpdate,
  ReviewExportScope,
  ReviewItemUpdate,
  ReviewSettings,
  ReviewSubjectUpdate,
  ReviewSummary,
  SortOrder,
  ConsistencyReport,
  CropSuggestion,
  CropSuggestionRequest,
  Style,
  StyleCreate,
  StyleDeleted,
  StyleDiff,
  StyleFromPhoto,
  StyleSummary,
  StyleUpdate,
  StyleUpdateFromPhoto,
  StyleVersionInfo,
  ReviewFrames,
  SubjectAnalysis,
  SubjectBox,
  SubjectInfo,
  ZoomInfo,
  ZoomLevel,
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
  subject: (id: string) => ['subject', id] as const,
  analysis: (id: string) => ['analysis', id] as const,
  styles: ['styles'] as const,
  style: (id: string) => ['style', id] as const,
  styleHistory: (id: string) => ['style', id, 'history'] as const,
  styleDiff: (id: string, a: number, b: number) => ['style', id, 'diff', a, b] as const,
  presets: ['presets'] as const,
  destinations: ['export', 'destinations'] as const,
  destinationCheck: (path: string) => ['export', 'destination-check', path] as const,
  exportPlan: (request: ExportRequest | null) => ['export', 'plan', request] as const,
  jobs: ['jobs'] as const,
  job: (id: string) => ['job', id] as const,
  reviews: ['reviews'] as const,
  review: (id: string) => ['review', id] as const,
  reviewSettings: ['review-settings'] as const,
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

/** The geometry a change would give from `geometry` (the crop tool's draft); core constrains it, nothing is saved. */
export function previewGeometry(photoId: string, geometry: Geometry, change: Partial<GeometryChange>): Promise<Geometry> {
  return api.post<Geometry>(`/api/photos/${encodeURIComponent(photoId)}/geometry/preview`, { geometry, change })
}

/** The photo's main subject (the hand-set box, else the detected one; the first detection takes a few
 * seconds). Only asked for when `enabled`. */
export function useSubject(photoId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.subject(photoId),
    queryFn: () => api.get<SubjectInfo>(`/api/photos/${encodeURIComponent(photoId)}/subject`),
    enabled,
    staleTime: Infinity, // changes only through useSetSubject or a detection job
  })
}

/** Set the subject by hand (upright photo coordinates), or `null` to use the detected one. */
export function useSetSubject(photoId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (box: SubjectBox | null) =>
      api.put<SubjectInfo>(`/api/photos/${encodeURIComponent(photoId)}/subject`, { box }),
    onSuccess: (info) => {
      client.setQueryData(queryKeys.subject(photoId), info)
      void client.invalidateQueries({ queryKey: ['export', 'plan'] })
      void client.invalidateQueries({ queryKey: queryKeys.analysis(photoId) })
    },
  })
}

/** What detection found in the photo, normalized to the edited photo (the AI Analysis tab). Never detects. */
export function useAnalysis(photoId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.analysis(photoId),
    queryFn: () => api.get<SubjectAnalysis>(`/api/photos/${encodeURIComponent(photoId)}/analysis`),
    enabled,
  })
}

/** Run detection for one photo now (a few seconds the first time) and show the result. */
export function useDetectNow(photoId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api.get<SubjectAnalysis>(`/api/photos/${encodeURIComponent(photoId)}/analysis`, { detect: true }),
    onSuccess: (analysis) => {
      client.setQueryData(queryKeys.analysis(photoId), analysis)
      void client.invalidateQueries({ queryKey: queryKeys.subject(photoId) })
    },
  })
}

/** A crop framing the subject in the crop tool's draft geometry; nothing is saved. */
export function suggestCrop(photoId: string, request: CropSuggestionRequest): Promise<CropSuggestion> {
  return api.post<CropSuggestion>(`/api/photos/${encodeURIComponent(photoId)}/suggest-crop`, request)
}

export const ZOOM_POLL_MS = 500

/** The zoom view at `level` (null = not zoomed). Asking starts the decode; polls until it is ready. */
export function useZoomInfo(photoId: string, level: ZoomLevel | null, version: string) {
  return useQuery({
    queryKey: ['zoom', photoId, level, version],
    queryFn: () => api.get<ZoomInfo>(`/api/photos/${encodeURIComponent(photoId)}/zoom/${level}`),
    enabled: level !== null,
    refetchInterval: (query) => (query.state.data?.state === 'decoding' ? ZOOM_POLL_MS : false),
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

function usePresetMutation<V>(fn: (vars: V) => Promise<ExportPreset>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (preset) => {
      // In the list at once, so a dialog can select the new preset before the list is fetched again.
      client.setQueryData<ExportPreset[]>(queryKeys.presets, (list) =>
        list ? [...list.filter((p) => p.id !== preset.id), preset] : list,
      )
      void client.invalidateQueries({ queryKey: queryKeys.presets })
    },
  })
}

export function useCreatePreset() {
  return usePresetMutation((request: PresetCreate) => api.post<ExportPreset>('/api/export-presets', request))
}

export function useUpdatePreset(id: string) {
  return usePresetMutation((update: PresetUpdate) =>
    api.put<ExportPreset>(`/api/export-presets/${encodeURIComponent(id)}`, update),
  )
}

export function useDuplicatePreset() {
  return usePresetMutation(({ id, name }: { id: string; name?: string }) =>
    api.post<ExportPreset>(`/api/export-presets/${encodeURIComponent(id)}/duplicate`, name ? { name } : {}),
  )
}

export function useDeletePreset() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/api/export-presets/${encodeURIComponent(id)}`),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.presets }),
  })
}

/** Recently used export folders, newest first. */
export function useExportDestinations() {
  return useQuery({ queryKey: queryKeys.destinations, queryFn: () => api.get<string[]>('/api/export/destinations') })
}

/** Whether a folder can take exports (`path` should be debounced by the caller). */
export function useDestinationCheck(path: string) {
  return useQuery({
    queryKey: queryKeys.destinationCheck(path),
    queryFn: () => api.post<DestinationCheck>('/api/export/destination-check', { path }),
    enabled: path.trim() !== '',
    staleTime: 0,
  })
}

/** What an export would write (a dry run); `null` = nothing to plan yet. */
export function useExportPlan(request: ExportRequest | null) {
  return useQuery({
    queryKey: queryKeys.exportPlan(request),
    queryFn: () => api.post<ExportPlan>('/api/export/plan', request),
    enabled: request !== null,
    staleTime: 0,
    retry: false,
  })
}

/** Ask the backend to show an exported file in Explorer. */
export function useRevealFile() {
  return useMutation({ mutationFn: (path: string) => api.post<void>('/api/export/reveal', { path }) })
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
      void client.invalidateQueries({ queryKey: queryKeys.destinations })
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
    for (const job of jobs.data ?? []) {
      if (job.kind !== 'detect_subjects') continue
      if (isActive(job)) running.current.add(job.id)
      else if (running.current.delete(job.id)) {
        void client.invalidateQueries({ queryKey: ['subject'] })
        void client.invalidateQueries({ queryKey: ['export', 'plan'] })
      }
    }
    // A review changes when its export writes photos (they leave it) or a Prepare creates one.
    for (const job of jobs.data ?? []) {
      if (job.kind !== 'export' && job.kind !== 'prepare_export') continue
      if (isActive(job)) running.current.add(job.id)
      else if (running.current.delete(job.id)) {
        void client.invalidateQueries({ queryKey: queryKeys.reviews })
        void client.invalidateQueries({ queryKey: ['review'] })
      }
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

// ----------------------------------------------------------------- pre-export reviews (Phase 6c)

export function useReviews() {
  return useQuery({ queryKey: queryKeys.reviews, queryFn: () => api.get<ReviewSummary[]>('/api/reviews') })
}

export function useReview(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.review(id ?? ''),
    queryFn: () => api.get<ExportReview>(`/api/reviews/${encodeURIComponent(id ?? '')}`),
    enabled: Boolean(id),
  })
}

/** A decision changes the whole review (counts, maybe the photo's status): the answer replaces it. */
function useReviewMutation<T>(
  reviewId: string,
  send: (body: T) => Promise<ExportReview>,
  after?: (body: T) => void,
) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: send,
    onSuccess: (review, body) => {
      client.setQueryData(queryKeys.review(reviewId), review)
      void client.invalidateQueries({ queryKey: queryKeys.reviews })
      after?.(body)
    },
  })
}

export function useUpdateReviewItem(reviewId: string) {
  return useReviewMutation(reviewId, ({ photoId, update }: { photoId: string; update: ReviewItemUpdate }) =>
    api.patch<ExportReview>(
      `/api/reviews/${encodeURIComponent(reviewId)}/items/${encodeURIComponent(photoId)}`,
      update,
    ),
  )
}

export function useSetReviewSubject(reviewId: string) {
  const client = useQueryClient()
  return useReviewMutation(
    reviewId,
    ({ photoId, update }: { photoId: string; update: ReviewSubjectUpdate }) =>
      api.put<ExportReview>(
        `/api/reviews/${encodeURIComponent(reviewId)}/items/${encodeURIComponent(photoId)}/subject`,
        update,
      ),
    // The subject is saved to the photo's edit: the crop tool's view of it is stale now.
    ({ photoId }) => void client.invalidateQueries({ queryKey: queryKeys.subject(photoId) }),
  )
}

/** The export's crop at each zoom step for one photo (refetched when its framing changes). */
export function useReviewFrames(reviewId: string, photoId: string, revision: string, enabled: boolean) {
  return useQuery({
    queryKey: ['review', reviewId, 'frames', photoId, revision] as const,
    queryFn: () =>
      api.get<ReviewFrames>(
        `/api/reviews/${encodeURIComponent(reviewId)}/items/${encodeURIComponent(photoId)}/frames`,
      ),
    enabled,
    staleTime: Infinity,
  })
}

export function useExportReview(reviewId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (scope: ReviewExportScope) =>
      api.post<Job>(`/api/reviews/${encodeURIComponent(reviewId)}/export`, { scope }),
    onSuccess: (job) => {
      client.setQueryData(queryKeys.job(job.id), job)
      void client.invalidateQueries({ queryKey: queryKeys.jobs })
    },
  })
}

export function useDiscardReview() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/api/reviews/${encodeURIComponent(id)}`),
    onSuccess: (_, id) => {
      client.removeQueries({ queryKey: queryKeys.review(id) })
      void client.invalidateQueries({ queryKey: queryKeys.reviews })
    },
  })
}

export function useReviewSettings() {
  return useQuery({
    queryKey: queryKeys.reviewSettings,
    queryFn: () => api.get<ReviewSettings>('/api/review-settings'),
  })
}

export function useSaveReviewSettings() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (settings: ReviewSettings) => api.put<ReviewSettings>('/api/review-settings', settings),
    onSuccess: (settings) => {
      client.setQueryData(queryKeys.reviewSettings, settings)
      // Open reviews are sorted again by the new rules.
      void client.invalidateQueries({ queryKey: ['review'] })
      void client.invalidateQueries({ queryKey: queryKeys.reviews })
    },
  })
}
