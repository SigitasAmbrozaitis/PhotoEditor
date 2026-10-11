import { ArrowUp, Folder, HardDrive } from 'lucide-react'
import { useState } from 'react'
import { useDirListing } from '../../api/queries'
import { Button, Dialog, ErrorState, Loading } from '../../components/ui'

/** Browse the backend's folders (read-only listing) and pick one. Shows how many photos each folder holds. */
export function FolderBrowser({
  open,
  onOpenChange,
  initialPath,
  onChoose,
  title = 'Choose a photo folder',
  description = 'Photos are only read, never changed.',
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialPath: string | null
  onChoose: (path: string) => void
  title?: string
  description?: string
}) {
  const [path, setPath] = useState<string | null>(initialPath || null)
  const listing = useDirListing(path, open)
  const current = listing.data

  const choose = () => {
    if (current?.path) {
      onChoose(current.path)
      onOpenChange(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      width="max-w-xl"
      footer={
        <>
          <span className="mr-auto text-xs text-muted">
            {current?.path ? `${current.photo_count} photos in this folder` : 'Pick a drive'}
          </span>
          <Button onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="primary" disabled={!current?.path} onClick={choose}>
            Choose this folder
          </Button>
        </>
      }
    >
      <div className="flex items-center gap-2 pb-2">
        <Button
          size="sm"
          aria-label="Up one level"
          disabled={path === null}
          onClick={() => setPath(current?.parent ?? null)}
        >
          <ArrowUp className="size-4" aria-hidden />
        </Button>
        <span className="truncate font-mono text-xs text-fg" title={path ?? undefined}>
          {path ?? 'Drives'}
        </span>
      </div>
      {listing.isError ? (
        <div className="flex flex-col items-start gap-2">
          <ErrorState error={listing.error} />
          <Button size="sm" onClick={() => setPath(null)}>
            Show drives
          </Button>
        </div>
      ) : !current ? (
        <Loading label="Reading folder…" />
      ) : current.entries.length === 0 ? (
        <p className="py-6 text-center text-xs text-muted">No subfolders here.</p>
      ) : (
        <ul aria-label="Folders" className="flex flex-col">
          {current.entries.map((entry) => (
            <li key={entry.path}>
              <button
                type="button"
                onClick={() => setPath(entry.path)}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[13px] hover:bg-hover"
              >
                {current.path === null ? (
                  <HardDrive className="size-4 shrink-0 text-muted" aria-hidden />
                ) : (
                  <Folder className="size-4 shrink-0 text-muted" aria-hidden />
                )}
                <span className="flex-1 truncate">{entry.name}</span>
                {entry.photo_count !== null && entry.photo_count > 0 && (
                  <span className="text-[11px] text-accent">{entry.photo_count} photos</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Dialog>
  )
}
