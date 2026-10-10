import { CircleAlert, FolderOpen } from 'lucide-react'
import { useState } from 'react'
import { useExportDestinations } from '../../api/queries'
import type { DestinationCheck } from '../../api/types'
import { Button, Field, TextInput } from '../../components/ui'
import { FolderBrowser } from '../library/FolderBrowser'

/** Output folder input with a folder browser, recent folders and a check as you type. */
export function DestinationField({
  value,
  onChange,
  status,
}: {
  value: string
  onChange: (value: string) => void
  status: DestinationCheck | undefined
}) {
  const { data: recent } = useExportDestinations()
  const [browsing, setBrowsing] = useState(false)
  const refused = status && !status.ok
  return (
    <Field
      label="Destination folder"
      hint={status?.ok && !status.exists ? 'The folder will be created.' : 'Exports are new files; original photos are never changed.'}
    >
      <div className="flex gap-2">
        <TextInput
          className="flex-1"
          value={value}
          placeholder="e.g. C:\Users\you\Pictures\Exports"
          onChange={(e) => onChange(e.target.value)}
          aria-label="Destination folder"
          aria-invalid={refused || undefined}
        />
        <Button onClick={() => setBrowsing(true)}>
          <FolderOpen className="size-4" aria-hidden /> Browse…
        </Button>
      </div>
      {refused && (
        <p role="alert" className="flex items-start gap-1.5 pt-1 text-xs text-err">
          <CircleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
          {status.reason}
        </p>
      )}
      {recent && recent.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span className="text-[11px] text-muted">Recent:</span>
          {recent.slice(0, 4).map((d) => (
            <button
              key={d}
              type="button"
              className="max-w-full truncate rounded bg-raised px-2 py-0.5 text-[11px] text-fg hover:bg-hover"
              onClick={() => onChange(d)}
            >
              {d}
            </button>
          ))}
        </div>
      )}
      {browsing && (
        <FolderBrowser
          open={browsing}
          onOpenChange={setBrowsing}
          initialPath={value.trim() || recent?.[0] || null}
          onChoose={onChange}
          title="Choose the export folder"
          description="New files are written here. Photo folders can't be chosen (originals are read-only)."
        />
      )}
    </Field>
  )
}
