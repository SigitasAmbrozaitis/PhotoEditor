import { FolderOpen, FolderSearch } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useImportFolder, useLatestImport, useLibraryFolders, useOpenFolder } from '../../api/queries'
import type { LibraryInfo } from '../../api/types'
import { Button, Field, ProgressBar, Select, Switch, TextInput } from '../../components/ui'
import { FolderBrowser } from './FolderBrowser'

/** Open a folder: type/paste a path or browse, then Open imports it (read-only, incremental). */
export function FolderBar({ library }: { library: LibraryInfo | undefined }) {
  const folders = useLibraryFolders()
  const importFolder = useImportFolder()
  const openFolder = useOpenFolder()
  const shown = library?.folder ?? library?.suggested_folder ?? ''
  const shownSubfolders = library?.include_subfolders ?? false
  const [path, setPath] = useState(shown)
  const [subfolders, setSubfolders] = useState(shownSubfolders)
  const [browsing, setBrowsing] = useState(false)

  // Follow the backend's current folder (or its suggestion) whenever it changes; the user's edits stay until then.
  const [synced, setSynced] = useState({ shown, shownSubfolders })
  if (synced.shown !== shown || synced.shownSubfolders !== shownSubfolders) {
    setSynced({ shown, shownSubfolders })
    setPath(shown)
    setSubfolders(shownSubfolders)
  }

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (path.trim()) importFolder.mutate({ folder: path.trim(), include_subfolders: subfolders })
  }

  const recent = (folders.data ?? []).filter((f) => f.path !== library?.folder)

  return (
    <form onSubmit={submit} className="flex min-w-64 flex-1 flex-wrap items-end gap-2">
      <Field label="Folder" className="min-w-64 flex-1">
        <TextInput
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="C:\Users\you\Pictures\…"
          aria-label="Photo folder"
          spellCheck={false}
        />
      </Field>
      <Button type="button" onClick={() => setBrowsing(true)}>
        <FolderSearch className="size-4" aria-hidden /> Browse…
      </Button>
      {recent.length > 0 && (
        <Field label="Recent">
          <Select
            value=""
            onChange={(e) => e.target.value && openFolder.mutate(e.target.value)}
            aria-label="Recent folders"
            className="max-w-48"
          >
            <option value="">Switch to…</option>
            {recent.map((f) => (
              <option key={f.path} value={f.path}>
                {f.path} ({f.photo_count})
              </option>
            ))}
          </Select>
        </Field>
      )}
      <div className="pb-1.5">
        <Switch checked={subfolders} onCheckedChange={setSubfolders} label="Include subfolders" />
      </div>
      <Button type="submit" variant="primary" disabled={!path.trim() || importFolder.isPending}>
        <FolderOpen className="size-4" aria-hidden /> Open
      </Button>
      {importFolder.isError && (
        <p role="alert" className="w-full text-xs text-err">
          {importFolder.error.message}
        </p>
      )}
      {browsing && (
        <FolderBrowser
          open
          onOpenChange={setBrowsing}
          initialPath={path.trim() || null}
          onChoose={(chosen) => setPath(chosen)}
        />
      )}
    </form>
  )
}

/** Progress of the running import, or the outcome of the last one. */
export function ImportStatus() {
  const { job, running } = useLatestImport()
  if (!job) return null
  if (running) {
    return (
      <div className="flex items-center gap-3 border-b border-line bg-panel/60 px-4 py-1.5 text-xs" role="status">
        <span className="shrink-0 text-fg">
          Importing… {job.completed} / {job.total}
        </span>
        <ProgressBar value={job.progress} label="Import progress" className="max-w-md flex-1" />
      </div>
    )
  }
  return job.summary ? (
    <div className="border-b border-line bg-panel/60 px-4 py-1 text-[11px] text-muted" role="status">
      Last import: {job.summary}
    </div>
  ) : null
}
