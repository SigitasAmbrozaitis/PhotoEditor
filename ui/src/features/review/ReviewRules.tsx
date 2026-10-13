import { useState } from 'react'
import { useReviewSettings, useSaveReviewSettings } from '../../api/queries'
import type { ReviewSettings } from '../../api/types'
import { Button, Dialog, ErrorState, Field, Loading, Switch } from '../../components/ui'
import { RequiredNumberInput } from '../export/ExportSettingsForm'

type Switches = 'no_subject' | 'uncertain' | 'ambiguous' | 'cut_off' | 'zoom_limit'

const SWITCHES: { key: Switches; label: string; hint: string }[] = [
  { key: 'no_subject', label: 'No subject', hint: 'Nothing recognized: centered or on the focus point.' },
  { key: 'uncertain', label: 'Uncertain subject', hint: 'The detected subject scores below the minimum.' },
  { key: 'ambiguous', label: 'Two candidates', hint: 'Another subject scores nearly as well.' },
  { key: 'cut_off', label: 'Subject cut off', hint: "The crop can't hold the whole subject." },
  { key: 'zoom_limit', label: 'Zoom limit', hint: 'The subject stays small even at the most zoom.' },
]

function Rules({ initial, onDone }: { initial: ReviewSettings; onDone: () => void }) {
  const save = useSaveReviewSettings()
  const [draft, setDraft] = useState(initial)
  const set = (patch: Partial<ReviewSettings>) => setDraft((d) => ({ ...d, ...patch }))
  return (
    <div className="flex flex-col gap-3">
      {SWITCHES.map(({ key, label, hint }) => (
        <div key={key} className="flex flex-col gap-0.5">
          <Switch label={label} checked={draft[key]} onCheckedChange={(v) => set({ [key]: v })} />
          <span className="pl-10 text-[11px] text-muted">{hint}</span>
        </div>
      ))}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Minimum score" hint="0–1; lower trusts more detections.">
          <RequiredNumberInput
            step={0.05}
            min={0}
            max={1}
            value={draft.min_score}
            disabled={!draft.uncertain}
            onChange={(min_score) => set({ min_score })}
          />
        </Field>
        <Field label="Rival share" hint="0.1–1; a rival this close to the subject's score is a doubt.">
          <RequiredNumberInput
            step={0.05}
            min={0.1}
            max={1}
            value={draft.ambiguity}
            disabled={!draft.ambiguous}
            onChange={(ambiguity) => set({ ambiguity })}
          />
        </Field>
      </div>
      {save.isError && <ErrorState error={save.error} />}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button variant="primary" disabled={save.isPending} onClick={() => save.mutate(draft, { onSuccess: onDone })}>
          Save rules
        </Button>
      </div>
    </div>
  )
}

/** The review rules (for every review): which doubts put a photo in Check, and how strict. */
export function ReviewRules() {
  const [open, setOpen] = useState(false)
  const settings = useReviewSettings()
  return (
    <>
      <Button onClick={() => setOpen(true)}>Rules…</Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Review rules"
        description="What puts a photo in Check. Saving sorts every open review again."
        width="max-w-md"
      >
        {settings.isError ? (
          <ErrorState error={settings.error} />
        ) : settings.data ? (
          <Rules initial={settings.data} onDone={() => setOpen(false)} />
        ) : (
          <Loading />
        )}
      </Dialog>
    </>
  )
}
