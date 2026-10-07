/** TanStack Query hooks for every API resource. Components never call fetch directly. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  ExportPreset,
  Job,
  JobRequest,
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
const isActive = (job: Job) => job.status === 'queued' || job.status === 'running'

export function useLibrary() {
  return useQuery({ queryKey: queryKeys.library, queryFn: () => api.get<LibraryInfo>('/api/library') })
}

export function usePhotos(q: PhotoQuery = {}) {
  return useQuery({
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
