/** The photo's style in the Adjust panel: pick or remove one, see what its rules did, save the photo's look as a
 * new style, or update the style from this photo. */
import { BookmarkPlus, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import {
  useCreateStyleFromPhoto,
  useSetPhotoStyle,
  useStyle,
  useStyles,
  useUpdateStyleFromPhoto,
} from '../../api/queries'
import type { AdjustmentGroup, PhotoDetail } from '../../api/types'
import { Button, Dialog, ErrorState, Field, Select, Switch, TextArea, TextInput } from '../../components/ui'
import { STYLE_GROUPS, changedPerGroup } from './photoStyleGroups'

export function PhotoStyle({ detail }: { detail: PhotoDetail }) {
  const styles = useStyles()
  const setStyle = useSetPhotoStyle(detail.photo.id)
  const [dialog, setDialog] = useState<'save' | 'update' | null>(null)
  const { edit } = detail
  const usable = styles.data?.filter((s) => !s.error) ?? []

  return (
    <div className="flex flex-col gap-1.5">
      <Field label="Style">
        <Select
          aria-label="Style"
          value={edit.style_id ?? ''}
          disabled={setStyle.isPending}
          onChange={(e) => setStyle.mutate(e.target.value || null)}
        >
          <option value="">No style</option>
          {usable.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </Field>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" title="Save this photo's look as a new style" onClick={() => setDialog('save')}>
          <BookmarkPlus className="size-3.5" aria-hidden /> Save as style…
        </Button>
        {edit.style_id && !edit.style_error && (
          <Button size="sm" title="Update the style from this photo" onClick={() => setDialog('update')}>
            <RefreshCw className="size-3.5" aria-hidden /> Update style…
          </Button>
        )}
      </div>
      {edit.style_error && <p className="text-[11px] text-err">{edit.style_error}</p>}
      {setStyle.isError && <p className="text-[11px] text-err">{setStyle.error.message}</p>}
      {edit.rules.length > 0 && (
        <ul className="text-[11px] text-muted" aria-label="What the style's rules did">
          {edit.rules.map((r) => (
            <li key={r.type}>
              {r.type === 'exposure' ? 'Auto exposure' : 'White balance'}: {r.summary}
              {r.note && <span className="text-warn"> ({r.note})</span>}
            </li>
          ))}
        </ul>
      )}
      {edit.group && (
        <p className="text-[11px] text-muted">Evened out with {edit.group.size - 1} other photos.</p>
      )}
      {dialog === 'save' && <SaveAsStyleDialog detail={detail} onClose={() => setDialog(null)} />}
      {dialog === 'update' && edit.style_id && (
        <UpdateStyleDialog detail={detail} styleId={edit.style_id} onClose={() => setDialog(null)} />
      )}
    </div>
  )
}

function GroupChoice({
  detail,
  groups,
  onChange,
}: {
  detail: PhotoDetail
  groups: AdjustmentGroup[]
  onChange: (groups: AdjustmentGroup[]) => void
}) {
  const counts = changedPerGroup(detail.edit.adjustments, detail.edit.unedited)
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1 text-[11px] font-medium tracking-wide text-muted uppercase">Take these groups</legend>
      {STYLE_GROUPS.map((g) => (
        <label key={g.id} className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={groups.includes(g.id)}
            onChange={(e) => onChange(e.target.checked ? [...groups, g.id] : groups.filter((x) => x !== g.id))}
          />
          {g.label}{' '}
          <span className="text-xs text-muted">
            {counts[g.id] ? `${counts[g.id]} changed` : 'unchanged'}
          </span>
        </label>
      ))}
    </fieldset>
  )
}

function SaveAsStyleDialog({ detail, onClose }: { detail: PhotoDetail; onClose: () => void }) {
  const navigate = useNavigate()
  const create = useCreateStyleFromPhoto()
  const setStyle = useSetPhotoStyle(detail.photo.id)
  const counts = changedPerGroup(detail.edit.adjustments, detail.edit.unedited)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [groups, setGroups] = useState<AdjustmentGroup[]>(STYLE_GROUPS.filter((g) => counts[g.id]).map((g) => g.id))
  const [exposure, setExposure] = useState<'match' | 'value' | 'none'>('match')
  const [whiteBalance, setWhiteBalance] = useState<'offset' | 'none'>('offset')
  const [useIt, setUseIt] = useState(true)

  const submit = () =>
    create.mutate(
      {
        photo_id: detail.photo.id,
        name: name.trim(),
        description: description.trim(),
        groups,
        exposure,
        white_balance: whiteBalance,
      },
      {
        onSuccess: (style) => {
          if (useIt) setStyle.mutate(style.id)
          onClose()
          if (!useIt) void navigate(`/styles/${style.id}`)
        },
      },
    )

  return (
    <Dialog
      open
      onOpenChange={(o) => !o && onClose()}
      title="Save as style"
      description={`A new style from ${detail.photo.filename}'s current look. The photo becomes its first test photo.`}
      width="max-w-lg"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={!name.trim() || create.isPending} onClick={submit}>
            Create style
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Name">
          <TextInput autoFocus value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Description">
          <TextArea rows={2} value={description} maxLength={2000} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <GroupChoice detail={detail} groups={groups} onChange={setGroups} />
        <Field
          label="Exposure"
          hint={
            exposure === 'match'
              ? "Auto exposure brings other photos to this photo's brightness (good for differently exposed shots)."
              : exposure === 'value'
                ? "The same exposure change on every photo."
                : "The style doesn't touch exposure."
          }
        >
          <Select value={exposure} onChange={(e) => setExposure(e.target.value as typeof exposure)}>
            <option value="match">Match this photo's brightness</option>
            <option value="value">Fixed exposure value</option>
            <option value="none">Leave exposure alone</option>
          </Select>
        </Field>
        <Field
          label="White balance"
          hint={
            whiteBalance === 'offset'
              ? "This photo's change from its camera white balance, applied to each photo's own (if you changed it)."
              : "The style doesn't touch white balance."
          }
        >
          <Select value={whiteBalance} onChange={(e) => setWhiteBalance(e.target.value as typeof whiteBalance)}>
            <option value="offset">As shot + this photo's offset</option>
            <option value="none">Leave white balance alone</option>
          </Select>
        </Field>
        <Switch label="Use the new style for this photo" checked={useIt} onCheckedChange={setUseIt} />
        {create.isError && <ErrorState error={create.error} />}
      </div>
    </Dialog>
  )
}

function UpdateStyleDialog({ detail, styleId, onClose }: { detail: PhotoDetail; styleId: string; onClose: () => void }) {
  const style = useStyle(styleId)
  const update = useUpdateStyleFromPhoto(styleId)
  const counts = changedPerGroup(detail.edit.adjustments, detail.edit.unedited)
  const [groups, setGroups] = useState<AdjustmentGroup[]>(STYLE_GROUPS.filter((g) => counts[g.id]).map((g) => g.id))
  const [note, setNote] = useState('')
  const affected = style.data?.photo_count ?? 0

  const submit = () => {
    if (!style.data) return
    update.mutate(
      {
        photo_id: detail.photo.id,
        groups,
        expected_version: style.data.version,
        change_note: note.trim(),
      },
      { onSuccess: onClose },
    )
  }

  return (
    <Dialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={`Update "${style.data?.name ?? styleId}" from this photo`}
      description="The chosen groups of the style get this photo's values; the rest of the style stays."
      width="max-w-lg"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={!groups.length || !style.data || update.isPending} onClick={submit}>
            Update style ({affected} photo{affected === 1 ? '' : 's'} change)
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <GroupChoice detail={detail} groups={groups} onChange={setGroups} />
        <p className="text-xs text-muted">
          Every photo using the style follows (their thumbnails re-render). Exposure and white balance stay with the
          style's rules; the old version stays in the style's history.
        </p>
        <Field label="Change note">
          <TextInput value={note} maxLength={500} placeholder="e.g. 'more contrast'" onChange={(e) => setNote(e.target.value)} />
        </Field>
        {update.isError && <ErrorState error={update.error} />}
      </div>
    </Dialog>
  )
}
