/** TanStack Query hooks for every API resource. Components never call fetch directly. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  DirListing,
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
  Style,
  StyleSummary,
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
  library: ['library'] as const,
  folders: ['library', 'folders'] as const,
  dirs: (path: string | null) => ['dirs', path] as const,
  photos: (q: PhotoQuery) => ['photos', q] as const,
  photo: (id: string) => ['photo', id] as const,
  styles: ['styles'] as const,
  style: (id: string) => ['style', id] as const,
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
