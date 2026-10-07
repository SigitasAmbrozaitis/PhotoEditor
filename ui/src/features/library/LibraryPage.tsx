import { ArrowDownWideNarrow, ArrowUpNarrowWide, Download, FolderOpen, Wand2 } from 'lucide-react'
import { useMemo, useState, type KeyboardEvent, type MouseEvent } from 'react'
import { useNavigate } from 'react-router'
import { imageUrls } from '../../api/client'
import { useLibrary, usePhotos, useStyles, type PhotoQuery } from '../../api/queries'
import type { Photo, PhotoSort } from '../../api/types'
import { Button, Chip, EmptyState, ErrorState, Field, Loading, PageHeader, Select, Stars, TextInput, Tooltip } from '../../components/ui'
import { cn } from '../../lib/cn'
import { useSelection } from '../../state/selection'
import { ExportDialog } from '../export/ExportDialog'
import { ProcessWizard } from '../process/ProcessWizard'

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
          src={imageUrls.thumbnail(photo.id)}
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
  const library = useLibrary()
  const styles = useStyles()
  const [query, setQuery] = useState<PhotoQuery>({ sort: 'date', order: 'asc' })
  const photos = usePhotos(query)
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
          library.data ? `${library.data.photo_count} photos · ${count} selected` : 'Loading library…'
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
        <Field label="Folder" className="min-w-64 flex-1">
          <div className="flex gap-2">
            <TextInput readOnly value={library.data?.folder ?? ''} className="flex-1" aria-label="Photo folder" />
            <Tooltip content="Opening other folders arrives in Phase 2 (real import).">
              <span>
                <Button disabled>
                  <FolderOpen className="size-4" aria-hidden /> Change…
                </Button>
              </span>
            </Tooltip>
          </div>
        </Field>
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

      <div className="min-h-0 flex-1 overflow-y-auto p-4" onKeyDown={handleGridKey}>
        {photos.isError ? (
          <ErrorState error={photos.error} />
        ) : photos.isLoading ? (
          <Loading label="Loading photos…" />
        ) : items.length === 0 ? (
          <EmptyState title="No photos match these filters." />
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
