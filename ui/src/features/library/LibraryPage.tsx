import { useQueryClient } from '@tanstack/react-query'
import { ArrowDownWideNarrow, ArrowUpNarrowWide, Download, Wand2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { imageUrls } from '../../api/client'
import {
  IMPORT_REFRESH_MS,
  queryKeys,
  useLatestImport,
  useLibrary,
  usePhotos,
  useStyles,
  type PhotoQuery,
} from '../../api/queries'
import type { Photo, PhotoSort } from '../../api/types'
import { Button, Chip, EmptyState, ErrorState, Field, Loading, PageHeader, Select, Stars } from '../../components/ui'
import { cn } from '../../lib/cn'
import { useSelection } from '../../state/selection'
import { ExportDialog } from '../export/ExportDialog'
import { ProcessWizard } from '../process/ProcessWizard'
import { FolderBar, ImportStatus } from './FolderBar'

function PhotoTile({
  photo,
  selected,
  styleName,
  onClick,
  onOpen,
  onKeyDown,
}: {
  photo: Photo
  selected: boolean
  styleName?: string
  onClick: (e: MouseEvent) => void
  onOpen: () => void
  onKeyDown: (e: KeyboardEvent) => void
}) {
  return (
    <div
      role="option"
      aria-selected={selected}
      aria-label={photo.filename}
      tabIndex={0}
      onClick={onClick}
      onDoubleClick={onOpen}
      onKeyDown={onKeyDown}
      className={cn(
        'group relative cursor-default overflow-hidden rounded border bg-panel outline-none select-none',
        selected ? 'border-accent ring-2 ring-accent' : 'border-line hover:border-muted',
        'focus-visible:ring-2 focus-visible:ring-accent-strong',
      )}
    >
      <div className="checker flex aspect-square items-center justify-center">
        <img
          src={imageUrls.thumbnail(photo.id, photo.image_version)}
          alt=""
          loading="lazy"
          draggable={false}
          className="max-h-full max-w-full object-contain"
        />
      </div>
      <div className="flex items-center justify-between gap-1 px-2 py-1.5">
        <span className="truncate font-mono text-[11px] text-fg">{photo.filename}</span>
        <Stars rating={photo.rating} />
      </div>
      {styleName && (
        <Chip tone="overlay" className="absolute top-1.5 left-1.5">
          {styleName}
          {photo.has_overrides ? ' *' : ''}
        </Chip>
      )}
    </div>
  )
}

export function LibraryPage() {
  const navigate = useNavigate()
  const selection = useSelection()
  const client = useQueryClient()
  const library = useLibrary()
  const styles = useStyles()
  const importing = useLatestImport().running
  // "Show photos" on a style opens the Library filtered to it (?style=<id>).
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState<PhotoQuery>(() => ({
    sort: 'date',
    order: 'asc',
    styleId: searchParams.get('style') ?? undefined,
  }))
  const photos = usePhotos(query, { refetchInterval: importing ? IMPORT_REFRESH_MS : false })
  const noFolder = library.data !== undefined && library.data.folder === null

  // While importing, the grid polls; when the import ends, refresh once more so counts and the last photos show.
  const wasImporting = useRef(importing)
  useEffect(() => {
    if (wasImporting.current !== importing) {
      void client.invalidateQueries({ queryKey: queryKeys.library })
      void client.invalidateQueries({ queryKey: queryKeys.folders })
      if (!importing) void client.invalidateQueries({ queryKey: ['photos'] })
    }
    wasImporting.current = importing
  }, [importing, client])
  const [dialog, setDialog] = useState<'apply' | 'export' | null>(null)

  const items = useMemo(() => photos.data?.items ?? [], [photos.data])
  const orderedIds = useMemo(() => items.map((p) => p.id), [items])
  const styleNames = useMemo(() => new Map(styles.data?.map((s) => [s.id, s.name])), [styles.data])
  const count = selection.ids.length

  const handleClick = (e: MouseEvent, id: string) => {
    if (e.shiftKey) selection.selectRange(orderedIds, id)
    else if (e.ctrlKey || e.metaKey) selection.toggle(id)
    else selection.selectOnly(id)
  }

  const handleKey = (e: KeyboardEvent, id: string) => {
    if (e.key === 'Enter') void navigate(`/library/${id}`)
    else if (e.key === ' ') {
      e.preventDefault()
      selection.toggle(id)
    }
  }

  const handleGridKey = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
      e.preventDefault()
      selection.selectAll(orderedIds)
    } else if (e.key === 'Escape') {
      selection.clear()
    }
  }

  return (
    <>
      <PageHeader
        title="Library"
        subtitle={
          !library.data
            ? 'Loading library…'
            : noFolder
              ? 'No folder open'
              : `${library.data.photo_count} photos · ${count} selected`
        }
        actions={
          <>
            <Button variant="primary" disabled={count === 0} onClick={() => setDialog('apply')}>
              <Wand2 className="size-4" aria-hidden /> Apply style…
            </Button>
            <Button disabled={count === 0} onClick={() => setDialog('export')}>
              <Download className="size-4" aria-hidden /> Export…
            </Button>
          </>
        }
      />

      <div className="flex flex-wrap items-end gap-3 border-b border-line bg-panel/60 px-4 py-2">
        <FolderBar library={library.data} />
        <Field label="Sort by">
          <Select
            value={query.sort}
            onChange={(e) => setQuery((q) => ({ ...q, sort: e.target.value as PhotoSort }))}
            aria-label="Sort by"
          >
            <option value="date">Capture date</option>
            <option value="name">File name</option>
            <option value="rating">Rating</option>
          </Select>
        </Field>
        <Button
          aria-label={query.order === 'asc' ? 'Ascending' : 'Descending'}
          title={query.order === 'asc' ? 'Ascending' : 'Descending'}
          onClick={() => setQuery((q) => ({ ...q, order: q.order === 'asc' ? 'desc' : 'asc' }))}
        >
          {query.order === 'asc' ? (
            <ArrowUpNarrowWide className="size-4" aria-hidden />
          ) : (
            <ArrowDownWideNarrow className="size-4" aria-hidden />
          )}
        </Button>
        <Field label="Style">
          <Select
            value={query.styleId ?? ''}
            onChange={(e) => setQuery((q) => ({ ...q, styleId: e.target.value || undefined }))}
            aria-label="Filter by style"
          >
            <option value="">All photos</option>
            <option value="none">No style</option>
            {styles.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Rating">
          <Select
            value={query.minRating ?? 0}
            onChange={(e) => setQuery((q) => ({ ...q, minRating: Number(e.target.value) }))}
            aria-label="Minimum rating"
          >
            <option value={0}>Any</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {'★'.repeat(n)} or more
              </option>
            ))}
          </Select>
        </Field>
        <div className="flex gap-1 pb-0.5">
          <Button size="sm" variant="ghost" onClick={() => selection.selectAll(orderedIds)}>
            Select all
          </Button>
          <Button size="sm" variant="ghost" disabled={count === 0} onClick={selection.clear}>
            Clear
          </Button>
        </div>
      </div>

      <ImportStatus />

      <div className="min-h-0 flex-1 overflow-y-auto p-4" onKeyDown={handleGridKey}>
        {photos.isError ? (
          <ErrorState error={photos.error} />
        ) : photos.isLoading ? (
          <Loading label="Loading photos…" />
        ) : noFolder ? (
          <EmptyState title="Open a folder">
            <p className="max-w-md text-xs">
              Type or paste a folder path above, or use Browse…, then press Open. Photos are only read, never
              changed: RAW + JPEG pairs show as one photo.
            </p>
          </EmptyState>
        ) : items.length === 0 ? (
          <EmptyState title={importing ? 'Importing…' : 'No photos match these filters.'} />
        ) : (
          <div
            role="listbox"
            aria-label="Photos"
            aria-multiselectable
            className="grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-3"
          >
            {items.map((photo) => (
              <PhotoTile
                key={photo.id}
                photo={photo}
                selected={selection.has(photo.id)}
                styleName={photo.style_id ? styleNames.get(photo.style_id) : undefined}
                onClick={(e) => handleClick(e, photo.id)}
                onOpen={() => void navigate(`/library/${photo.id}`)}
                onKeyDown={(e) => handleKey(e, photo.id)}
              />
            ))}
          </div>
        )}
        <p className="pt-4 text-center text-[11px] text-muted">
          Click to select · Ctrl+click to add · Shift+click for a range · Double-click or Enter to open · Ctrl+A
          selects all
        </p>
      </div>

      {dialog === 'apply' && (
        <ProcessWizard open onOpenChange={(o) => !o && setDialog(null)} photoIds={selection.ids} />
      )}
      {dialog === 'export' && (
        <ExportDialog open onOpenChange={(o) => !o && setDialog(null)} photoIds={selection.ids} />
      )}
    </>
  )
}
