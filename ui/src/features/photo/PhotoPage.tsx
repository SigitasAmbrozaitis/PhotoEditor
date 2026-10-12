import { ArrowLeft, Camera, ChevronLeft, ChevronRight, Columns2, Crop, Download, Eye, EyeOff, Grid3x3 } from 'lucide-react'
import { Tabs } from 'radix-ui'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { imageUrls } from '../../api/client'
import { usePhotoDetail, usePhotos, useStyles } from '../../api/queries'
import type { Geometry, Photo, ZoomLevel } from '../../api/types'
import { Button, ErrorState, Loading, Stars } from '../../components/ui'
import { useGrid } from '../../hooks/useGrid'
import { cn } from '../../lib/cn'
import { useSelection } from '../../state/selection'
import { ExportDialog } from '../export/ExportDialog'
import { AdjustmentPanel } from './AdjustmentPanel'
import { CropTool } from './CropTool'
import { withValue, type EditSession } from './editSession'
import { PhotoViewer, type ViewMode } from './PhotoViewer'
import { ZoomView } from './ZoomView'
import type { Point } from './zoomMath'

function formatBytes(bytes: number): string {
  return `${(bytes / 1_000_000).toFixed(1)} MB`
}

function InfoPanel({ photo, styleName }: { photo: Photo; styleName?: string }) {
  const cropped = photo.edited_width !== photo.width || photo.edited_height !== photo.height
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
    ...(cropped ? [['Cropped', `${photo.edited_width} × ${photo.edited_height}`] as [string, ReactNode]] : []),
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

type Zoom = 'fit' | ZoomLevel

const ZOOMS: { level: Zoom; label: string; title: string }[] = [
  { level: 'fit', label: 'Fit', title: 'The whole photo (Z toggles)' },
  { level: 50, label: '50%', title: 'Half size' },
  { level: 100, label: '100%', title: '1:1, where sharpening can be judged (Z)' },
]

const CENTER: Point = { x: 0.5, y: 0.5 }

export function PhotoPage() {
  const { photoId = '' } = useParams()
  const navigate = useNavigate()
  const selection = useSelection()
  const detail = usePhotoDetail(photoId)
  const list = usePhotos({ sort: 'date', order: 'asc' })
  const styles = useStyles()
  const [mode, setMode] = useState<ViewMode>('after')
  // The open photo's edit session lives in its adjustment panel; the crop tool saves through it too.
  const session = useRef<EditSession | null>(null)
  // Both belong to the photo they were opened on: another photo starts uncropped and fitted.
  const [crop, setCrop] = useState<{ photoId: string; geometry: Geometry } | null>(null)
  const [zoomState, setZoomState] = useState<{ photoId: string; level: Zoom; focus: Point } | null>(null)
  const cropping = crop?.photoId === photoId
  const setCropping = (on: boolean) => {
    const geometry = session.current?.params.geometry ?? detail.data?.edit.adjustments.geometry
    setCrop(on && geometry ? { photoId, geometry } : null)
  }
  const zoom = zoomState?.photoId === photoId ? zoomState : { level: 'fit' as Zoom, focus: CENTER }
  const setZoom = (next: { level: Zoom; focus: Point }) => setZoomState({ photoId, ...next })
  const [exporting, setExporting] = useState(false)

  const photos = useMemo(() => list.data?.items ?? [], [list.data])
  const index = photos.findIndex((p) => p.id === photoId)
  const prev = index > 0 ? photos[index - 1] : undefined
  const next = index >= 0 && index < photos.length - 1 ? photos[index + 1] : undefined
  const styleName = styles.data?.find((s) => s.id === detail.data?.photo.style_id)?.name
  const canZoom = mode !== 'camera' && !cropping
  // The crop tool handles G itself while it is open.
  const [grid, toggleGrid] = useGrid({ key: !cropping })

  useEffect(() => {
    // Keep the shown photo selected so "Apply style…" / "Export…" act on it. Runs only when the photo changes.
    if (photoId && !selection.has(photoId)) selection.selectOnly(photoId)
  }, [photoId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Keys a control already handled (a focused slider's arrows, a curve point) or typed into a field are
      // not page shortcuts: otherwise ←/→ on a slider would switch photos. The crop tool has its own keys.
      if (e.defaultPrevented || cropping) return
      const target = e.target as HTMLElement | null
      if (target?.closest('input, select, textarea, [contenteditable="true"], [role="slider"]')) return
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const key = e.key.toLowerCase()
      if (e.key === 'ArrowLeft' && prev) void navigate(`/library/${prev.id}`)
      else if (e.key === 'ArrowRight' && next) void navigate(`/library/${next.id}`)
      else if (e.key === 'Escape') {
        if (zoom.level !== 'fit') setZoom({ ...zoom, level: 'fit' })
        else void navigate('/library')
      } else if (e.key === '\\') setMode((m) => (m === 'before' ? 'after' : 'before'))
      else if (key === 'r') {
        setZoom({ ...zoom, level: 'fit' })
        setCropping(true)
      } else if (key === 'z' && canZoom) setZoom({ level: zoom.level === 'fit' ? 100 : 'fit', focus: CENTER })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (detail.isError) return <ErrorState error={detail.error} />
  if (!detail.data) return <Loading label="Loading photo…" />
  const { photo, edit } = detail.data
  const zoomLevel = canZoom ? zoom.level : 'fit'

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
              disabled={cropping}
              onClick={() => setMode(m)}
              className={cn(
                'flex items-center gap-1 px-2 py-1 text-xs disabled:opacity-50',
                mode === m ? 'bg-raised text-strong' : 'text-muted hover:bg-hover',
              )}
            >
              <Icon className="size-3.5" aria-hidden /> {label}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Zoom" className="flex rounded border border-line">
          {ZOOMS.map(({ level, label, title }) => (
            <button
              key={level}
              type="button"
              aria-pressed={zoomLevel === level}
              disabled={!canZoom}
              title={title}
              onClick={() => setZoom({ level, focus: zoom.level === 'fit' ? CENTER : zoom.focus })}
              className={cn(
                'px-2 py-1 text-xs disabled:opacity-50',
                zoomLevel === level ? 'bg-raised text-strong' : 'text-muted hover:bg-hover',
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <Button
          size="sm"
          aria-pressed={cropping}
          variant={cropping ? 'primary' : 'secondary'}
          title="Crop, straighten, rotate and flip (R)"
          onClick={() => {
            setZoom({ ...zoom, level: 'fit' })
            setCropping(!cropping)
          }}
        >
          <Crop className="size-3.5" aria-hidden /> Crop
        </Button>
        <Button
          size="sm"
          variant={grid ? 'primary' : 'secondary'}
          aria-pressed={grid}
          title="3×3 grid to compose by (G)"
          onClick={toggleGrid}
        >
          <Grid3x3 className="size-3.5" aria-hidden /> Grid
        </Button>
        <Button size="sm" onClick={() => setExporting(true)}>
          <Download className="size-3.5" aria-hidden /> Export…
        </Button>
        {exporting && <ExportDialog open onOpenChange={setExporting} photoIds={[photo.id]} />}
      </div>

      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 p-3">
            {cropping && crop ? (
              <CropTool
                photo={photo}
                geometry={crop.geometry}
                onCancel={() => setCropping(false)}
                onDone={(geometry) => {
                  const current = session.current
                  current?.commit(withValue(current.params, 'geometry', geometry))
                  setCropping(false)
                }}
              />
            ) : zoomLevel !== 'fit' ? (
              <ZoomView
                key={`${photo.id}-${zoomLevel}`}
                photo={photo}
                level={zoomLevel}
                mode={mode}
                focus={zoom.focus}
                onExit={() => setZoom({ ...zoom, level: 'fit' })}
              />
            ) : (
              <PhotoViewer
                photo={photo}
                mode={mode}
                grid={grid}
                onZoomAt={(point) => setZoom({ level: 100, focus: point })}
              />
            )}
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
                sessionRef={session}
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
