import { ArrowLeft, Camera, ChevronLeft, ChevronRight, Columns2, Crop, Download, Eye, EyeOff } from 'lucide-react'
import { Tabs } from 'radix-ui'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { imageUrls } from '../../api/client'
import { usePhotoDetail, usePhotos, useStyles } from '../../api/queries'
import type { Photo } from '../../api/types'
import { Button, ErrorState, Loading, Stars } from '../../components/ui'
import { cn } from '../../lib/cn'
import { useSelection } from '../../state/selection'
import { ExportDialog } from '../export/ExportDialog'
import { AdjustmentPanel } from './AdjustmentPanel'
import { PhotoViewer, type ViewMode } from './PhotoViewer'

function formatBytes(bytes: number): string {
  return `${(bytes / 1_000_000).toFixed(1)} MB`
}

function InfoPanel({ photo, styleName }: { photo: Photo; styleName?: string }) {
  const rows: [string, ReactNode][] = [
    ['File', <span key="v" className="font-mono">{photo.filename}</span>],
    ['Folder', <span key="v" className="break-all">{photo.folder}</span>],
    [
      'Camera JPEG',
      photo.sidecar_jpeg ? (
        <span key="v" className="font-mono" title={photo.sidecar_jpeg}>
          {photo.sidecar_jpeg.split('/').pop()}
        </span>
      ) : (
        '—'
      ),
    ],
    ['Captured', photo.captured_at ? new Date(photo.captured_at).toLocaleString() : '—'],
    ['Camera', photo.camera ?? '—'],
    ['Lens', photo.lens ?? '—'],
    ['Focal length', photo.focal_length ? `${photo.focal_length} mm` : '—'],
    ['Aperture', photo.aperture ? `f/${photo.aperture}` : '—'],
    ['Shutter', photo.shutter ? `${photo.shutter} s` : '—'],
    ['ISO', photo.iso ?? '—'],
    ['Dimensions', `${photo.width} × ${photo.height}`],
    ['File size', formatBytes(photo.file_size)],
    ['Rating', <Stars key="v" rating={photo.rating} />],
    ['Style', styleName ?? 'No style'],
  ]
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 p-3 text-xs">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted">{label}</dt>
          <dd className="text-fg">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Filmstrip({ photos, currentId }: { photos: Photo[]; currentId: string }) {
  return (
    <nav aria-label="Filmstrip" className="flex h-24 shrink-0 gap-1.5 overflow-x-auto border-t border-line bg-panel p-2">
      {photos.map((p) => (
        <Link
          key={p.id}
          to={`/library/${p.id}`}
          aria-current={p.id === currentId ? 'page' : undefined}
          aria-label={p.filename}
          className={cn(
            'checker flex aspect-square h-full shrink-0 items-center justify-center overflow-hidden rounded border',
            p.id === currentId ? 'border-accent ring-2 ring-accent' : 'border-line opacity-70 hover:opacity-100',
          )}
        >
          <img src={imageUrls.thumbnail(p.id, p.image_version)} alt="" loading="lazy" className="max-h-full max-w-full object-contain" />
        </Link>
      ))}
    </nav>
  )
}

const MODES: { mode: ViewMode; label: string; icon: typeof Eye }[] = [
  { mode: 'after', label: 'After', icon: Eye },
  { mode: 'before', label: 'Before', icon: EyeOff },
  { mode: 'split', label: 'Split', icon: Columns2 },
  { mode: 'camera', label: 'Camera JPEG', icon: Camera },
]

export function PhotoPage() {
  const { photoId = '' } = useParams()
  const navigate = useNavigate()
  const selection = useSelection()
  const detail = usePhotoDetail(photoId)
  const list = usePhotos({ sort: 'date', order: 'asc' })
  const styles = useStyles()
  const [mode, setMode] = useState<ViewMode>('after')
  const [showCrop, setShowCrop] = useState(false)
  const [exporting, setExporting] = useState(false)

  const photos = useMemo(() => list.data?.items ?? [], [list.data])
  const index = photos.findIndex((p) => p.id === photoId)
  const prev = index > 0 ? photos[index - 1] : undefined
  const next = index >= 0 && index < photos.length - 1 ? photos[index + 1] : undefined
  const styleName = styles.data?.find((s) => s.id === detail.data?.photo.style_id)?.name

  useEffect(() => {
    // Keep the shown photo selected so "Apply style…" / "Export…" act on it. Runs only when the photo changes.
    if (photoId && !selection.has(photoId)) selection.selectOnly(photoId)
  }, [photoId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Keys a control already handled (a focused slider's arrows, a curve point) or typed into a field are
      // not page shortcuts: otherwise ←/→ on a slider would switch photos.
      if (e.defaultPrevented) return
      const target = e.target as HTMLElement | null
      if (target?.closest('input, select, textarea, [contenteditable="true"], [role="slider"]')) return
      if (e.key === 'ArrowLeft' && prev) void navigate(`/library/${prev.id}`)
      else if (e.key === 'ArrowRight' && next) void navigate(`/library/${next.id}`)
      else if (e.key === 'Escape') void navigate('/library')
      else if (e.key === '\\') setMode((m) => (m === 'before' ? 'after' : 'before'))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, prev, next])

  if (detail.isError) return <ErrorState error={detail.error} />
  if (!detail.data) return <Loading label="Loading photo…" />
  const { photo, edit } = detail.data

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-panel px-3 py-1.5">
        <Button variant="ghost" size="sm" onClick={() => void navigate('/library')}>
          <ArrowLeft className="size-4" aria-hidden /> Library
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Previous photo"
          disabled={!prev}
          onClick={() => prev && void navigate(`/library/${prev.id}`)}
        >
          <ChevronLeft className="size-4" aria-hidden />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Next photo"
          disabled={!next}
          onClick={() => next && void navigate(`/library/${next.id}`)}
        >
          <ChevronRight className="size-4" aria-hidden />
        </Button>
        <h1 className="font-mono text-sm text-strong">{photo.filename}</h1>
        <span className="text-xs text-muted">
          {index >= 0 ? `${index + 1} / ${photos.length}` : ''}
        </span>
        <div className="flex-1" />
        <div role="group" aria-label="View mode" className="flex rounded border border-line">
          {MODES.filter((m) => m.mode !== 'camera' || photo.sidecar_jpeg).map(({ mode: m, label, icon: Icon }) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => setMode(m)}
              className={cn(
                'flex items-center gap-1 px-2 py-1 text-xs',
                mode === m ? 'bg-raised text-strong' : 'text-muted hover:bg-hover',
              )}
            >
              <Icon className="size-3.5" aria-hidden /> {label}
            </button>
          ))}
        </div>
        <Button size="sm" aria-pressed={showCrop} variant={showCrop ? 'primary' : 'secondary'} onClick={() => setShowCrop((v) => !v)}>
          <Crop className="size-3.5" aria-hidden /> Crop
        </Button>
        <Button size="sm" onClick={() => setExporting(true)}>
          <Download className="size-3.5" aria-hidden /> Export…
        </Button>
        {exporting && <ExportDialog open onOpenChange={setExporting} photoIds={[photo.id]} />}
      </div>

      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 p-3">
            <PhotoViewer photo={photo} mode={mode} crop={showCrop ? edit.adjustments.geometry.crop : null} />
          </div>
          <Filmstrip photos={photos} currentId={photo.id} />
        </div>

        <aside className="flex w-80 shrink-0 flex-col border-l border-line bg-panel" aria-label="Photo details">
          <Tabs.Root defaultValue="adjust" className="flex min-h-0 flex-1 flex-col">
            <Tabs.List className="flex border-b border-line" aria-label="Panel">
              {[
                ['adjust', 'Adjust'],
                ['info', 'Info'],
              ].map(([value, label]) => (
                <Tabs.Trigger
                  key={value}
                  value={value!}
                  className="flex-1 py-2 text-xs text-muted data-[state=active]:border-b-2 data-[state=active]:border-accent data-[state=active]:text-strong"
                >
                  {label}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
            <Tabs.Content value="adjust" className="min-h-0 flex-1 overflow-y-auto">
              <AdjustmentPanel
                // A new style (or a new version of it) changes every value: start a fresh edit session.
                key={`${photo.id}-${edit.style_id ?? ''}-${edit.style_version ?? ''}`}
                detail={detail.data}
              />
            </Tabs.Content>
            <Tabs.Content value="info" className="min-h-0 flex-1 overflow-y-auto">
              <InfoPanel photo={photo} styleName={styleName} />
            </Tabs.Content>
          </Tabs.Root>
        </aside>
      </div>
    </div>
  )
}
