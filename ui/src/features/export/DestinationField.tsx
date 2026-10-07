import { FolderOpen } from 'lucide-react'
import { useJobs } from '../../api/queries'
import { Button, Field, TextInput, Tooltip } from '../../components/ui'

/** Output folder input with quick picks from recent jobs. */
export function DestinationField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { data: jobs } = useJobs()
  const recent = [...new Set((jobs ?? []).map((j) => j.destination).filter((d): d is string => Boolean(d)))].slice(
    0,
    3,
  )
  return (
    <Field label="Destination folder" hint="Exports are new files; original photos are never changed.">
      <div className="flex gap-2">
        <TextInput
          className="flex-1"
          value={value}
          placeholder="e.g. C:\Users\you\Pictures\Exports"
          onChange={(e) => onChange(e.target.value)}
          aria-label="Destination folder"
        />
        <Tooltip content="Folder browser arrives with real export in Phase 5. Type or paste a path for now.">
          <span>
            <Button disabled aria-label="Browse for folder">
              <FolderOpen className="size-4" aria-hidden /> Browse…
            </Button>
          </span>
        </Tooltip>
      </div>
      {recent.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span className="text-[11px] text-muted">Recent:</span>
          {recent.map((d) => (
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
    </Field>
  )
}
