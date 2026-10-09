/** Building blocks shared by the style detail sections. */
import { Pencil } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Button, TextInput } from '../../components/ui'

export function Section({ title, actions, children }: { title: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xs font-semibold tracking-wide text-muted uppercase">{title}</h2>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  )
}

export function EditButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <Button size="sm" variant="ghost" onClick={onClick} aria-label={label}>
      <Pencil className="size-3.5" aria-hidden /> Edit
    </Button>
  )
}

/** Save / cancel with an optional change note (shown in the style's history). */
export function SaveBar({
  onSave,
  onCancel,
  saving,
  disabled,
}: {
  onSave: (note: string) => void
  onCancel: () => void
  saving: boolean
  disabled?: boolean
}) {
  const [note, setNote] = useState('')
  return (
    <div className="flex flex-wrap items-center gap-2 rounded border border-line bg-raised/40 p-2">
      <TextInput
        className="min-w-48 flex-1"
        placeholder="Change note (optional), e.g. 'less contrast'"
        aria-label="Change note"
        value={note}
        maxLength={500}
        onChange={(e) => setNote(e.target.value)}
      />
      <Button onClick={onCancel} disabled={saving}>
        Cancel
      </Button>
      <Button variant="primary" onClick={() => onSave(note)} disabled={saving || disabled}>
        {saving ? 'Saving…' : 'Save'}
      </Button>
    </div>
  )
}
