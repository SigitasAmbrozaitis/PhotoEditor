/** The parameters the style sets, each removable. Values are edited by updating the style from a photo. */
import { X } from 'lucide-react'
import type { Style } from '../../api/types'
import { Button } from '../../components/ui'
import { Section } from './StyleSection'
import { parameterLabel, parameterValue } from './parameterFormat'
import type { StyleSave } from './useStyleSave'

export function StyleParameters({ style, saver }: { style: Style; saver: StyleSave }) {
  const entries = Object.entries(style.values)

  const remove = (name: string) => {
    const values = Object.fromEntries(entries.filter(([n]) => n !== name))
    void saver.save({ values }, `removed ${parameterLabel(name)}`)
  }

  return (
    <Section title={`Parameters (${entries.length} set by the style)`}>
      {entries.length === 0 ? (
        <p className="text-sm text-muted">
          The style sets no parameters directly. Edit a photo and use "Update style from this photo" to add some.
        </p>
      ) : (
        <table className="w-full max-w-2xl text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-muted">
              <th className="py-1.5 font-medium">Parameter</th>
              <th className="py-1.5 text-right font-medium">Value</th>
              <th className="w-8" aria-label="Remove" />
            </tr>
          </thead>
          <tbody>
            {entries.map(([path, value]) => (
              <tr key={path} className="border-b border-line/50">
                <td className="py-1.5">{parameterLabel(path)}</td>
                <td className="py-1.5 text-right font-mono tabular-nums">{parameterValue(path, value)}</td>
                <td className="text-right">
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Remove ${parameterLabel(path)} from the style`}
                    title="Remove from the style"
                    disabled={saver.saving}
                    onClick={() => remove(path)}
                  >
                    <X className="size-3.5" aria-hidden />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  )
}
