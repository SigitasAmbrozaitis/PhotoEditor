/** The style's test set: hard photos (a black cat, a night street, a backlit rally shot) every change is checked
 * on. Shown as before | after strips. */
import { Plus, X } from 'lucide-react'
import { imageUrls } from '../../api/client'
import type { Style } from '../../api/types'
import { Button } from '../../components/ui'
import { useSelection } from '../../state/selection'
import { Section } from './StyleSection'
import type { StyleSave } from './useStyleSave'

export function StyleTestSet({ style, saver }: { style: Style; saver: StyleSave }) {
  const selection = useSelection()
  const ids = style.test_photo_ids
  const toAdd = selection.ids.filter((id) => !ids.includes(id))

  const add = () => void saver.save({ test_photo_ids: [...ids, ...toAdd] }, `added ${toAdd.length} to the test set`)
  const remove = (id: string) =>
    void saver.save({ test_photo_ids: ids.filter((x) => x !== id) }, 'removed a photo from the test set')

  return (
    <Section
      title={`Test set (${ids.length})`}
      actions={
        <Button size="sm" onClick={add} disabled={!toAdd.length || saver.saving}>
          <Plus className="size-3.5" aria-hidden /> Add {toAdd.length} selected
        </Button>
      }
    >
      {ids.length === 0 ? (
        <p className="text-sm text-muted">
          No test photos yet. Select hard cases in the Library (very dark or bright, backlit, night, a dark subject)
          and add them: the consistency report and version comparisons use them.
        </p>
      ) : (
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
          {ids.map((id) => (
            <li key={id} className="relative flex flex-col gap-1">
              <div className="grid grid-cols-2 gap-1">
                <img
                  src={imageUrls.preview(id, { before: true, size: 400 })}
                  alt={`Test photo ${id} before`}
                  className="aspect-[3/2] w-full rounded bg-raised object-cover"
                />
                <img
                  src={imageUrls.styleVersion(style.id, style.version, id, 400)}
                  alt={`Test photo ${id} with the style`}
                  className="aspect-[3/2] w-full rounded bg-raised object-cover"
                />
              </div>
              <Button
                size="sm"
                variant="ghost"
                className="absolute top-1 right-1 bg-black/60"
                aria-label={`Remove ${id} from the test set`}
                disabled={saver.saving}
                onClick={() => remove(id)}
              >
                <X className="size-3.5" aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}
