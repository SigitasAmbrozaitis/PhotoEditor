import { ArrowLeft, Copy, Images, Trash2, Wand2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useDeleteStyle, useDuplicateStyle, useStyle } from '../../api/queries'
import type { Style } from '../../api/types'
import { Button, Dialog, ErrorState, Loading, PageHeader, Tooltip } from '../../components/ui'
import { useSelection } from '../../state/selection'
import { ProcessWizard } from '../process/ProcessWizard'
import { StyleConsistency } from './StyleConsistency'
import { StyleHistory } from './StyleHistory'
import { StyleParameters } from './StyleParameters'
import { StyleRules } from './StyleRules'
import { StyleSamples } from './StyleSamples'
import { StyleTestSet } from './StyleTestSet'
import { StyleText } from './StyleText'
import { useStyleSave } from './useStyleSave'

export function StyleDetailPage() {
  const { styleId = '' } = useParams()
  const style = useStyle(styleId)
  if (style.isError) return <ErrorState error={style.error} />
  if (!style.data) return <Loading label="Loading style…" />
  // Keyed by version: every section's edit state starts fresh from the version on screen.
  return <StyleDetail key={`${style.data.id}-${style.data.version}`} style={style.data} />
}

function StyleDetail({ style }: { style: Style }) {
  const navigate = useNavigate()
  const selection = useSelection()
  const saver = useStyleSave(style)
  const duplicate = useDuplicateStyle(style.id)
  const [applying, setApplying] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const count = selection.ids.length

  const applyButton = (
    <Button variant="primary" disabled={count === 0} onClick={() => setApplying(true)}>
      <Wand2 className="size-4" aria-hidden /> Apply to {count} selected
    </Button>
  )

  return (
    <>
      <PageHeader
        title={style.name}
        subtitle={
          `Version ${style.version} · updated ${new Date(style.updated_at).toLocaleDateString()} · ` +
          `${style.photo_count} photo${style.photo_count === 1 ? '' : 's'}`
        }
        actions={
          <>
            <Button variant="ghost" onClick={() => void navigate('/styles')}>
              <ArrowLeft className="size-4" aria-hidden /> All styles
            </Button>
            <Button onClick={() => void navigate(`/library?style=${encodeURIComponent(style.id)}`)}>
              <Images className="size-4" aria-hidden /> Show photos
            </Button>
            <Button
              disabled={duplicate.isPending}
              onClick={() => duplicate.mutate(undefined, { onSuccess: (copy) => void navigate(`/styles/${copy.id}`) })}
            >
              <Copy className="size-4" aria-hidden /> Duplicate
            </Button>
            <Button variant="danger" onClick={() => setDeleting(true)}>
              <Trash2 className="size-4" aria-hidden /> Delete
            </Button>
            {count === 0 ? (
              <Tooltip content="Select photos in the Library first.">
                <span>{applyButton}</span>
              </Tooltip>
            ) : (
              applyButton
            )}
          </>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-6xl flex-col gap-8 p-4">
          {saver.conflict && (
            <div role="alert" className="flex items-center gap-3 rounded border border-warn/50 bg-warn/10 p-3 text-sm">
              <span className="flex-1">
                This style was changed somewhere else since you opened it, so your change was not saved. Reload to see
                the newest version, then make your change again.
              </span>
              <Button onClick={saver.reload}>Reload</Button>
            </div>
          )}
          {saver.error && (
            <p role="alert" className="text-sm text-err">
              {saver.error}
            </p>
          )}
          <StyleText style={style} saver={saver} />
          <StyleRules style={style} saver={saver} />
          <StyleParameters style={style} saver={saver} />
          <StyleTestSet style={style} saver={saver} />
          <StyleConsistency style={style} />
          <StyleSamples style={style} />
          <StyleHistory style={style} />
        </div>
      </div>
      {applying && (
        <ProcessWizard
          open
          onOpenChange={(o) => !o && setApplying(false)}
          photoIds={selection.ids}
          initialStyleId={style.id}
        />
      )}
      <DeleteStyleDialog style={style} open={deleting} onOpenChange={setDeleting} />
    </>
  )
}

function DeleteStyleDialog({
  style,
  open,
  onOpenChange,
}: {
  style: Style
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const remove = useDeleteStyle(style.id)
  const n = style.photo_count
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Delete "${style.name}"?`}
      width="max-w-md"
      footer={
        <>
          <Button onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            variant="danger"
            disabled={remove.isPending}
            onClick={() => remove.mutate(undefined, { onSuccess: () => void navigate('/styles') })}
          >
            Delete style
          </Button>
        </>
      }
    >
      <p className="text-sm">
        {n === 0
          ? 'No photos use this style.'
          : `${n} photo${n === 1 ? ' uses' : 's use'} this style. ${n === 1 ? 'It' : 'They'} will drop back to no style ` +
            'and keep their own tweaks.'}{' '}
        The style's folder, history and samples are deleted.
      </p>
      {remove.isError && <ErrorState error={remove.error} />}
    </Dialog>
  )
}
