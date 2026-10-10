/** Name, description, best for / avoid on: read, or edit in place. */
import { useState } from 'react'
import type { Style } from '../../api/types'
import { Chip, Field, TextArea, TextInput } from '../../components/ui'
import { EditButton, SaveBar, Section } from './StyleSection'
import { listToText, textToList } from './styleWords'
import type { StyleSave } from './useStyleSave'

export function StyleText({ style, saver }: { style: Style; saver: StyleSave }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(style.name)
  const [description, setDescription] = useState(style.description)
  const [bestFor, setBestFor] = useState(listToText(style.best_for))
  const [avoidOn, setAvoidOn] = useState(listToText(style.avoid_on))

  const start = () => {
    setName(style.name)
    setDescription(style.description)
    setBestFor(listToText(style.best_for))
    setAvoidOn(listToText(style.avoid_on))
    setEditing(true)
  }

  const save = async (note: string) => {
    const changes = {
      name: name.trim(),
      description: description.trim(),
      best_for: textToList(bestFor),
      avoid_on: textToList(avoidOn),
    }
    if (await saver.save(changes, note)) setEditing(false)
  }

  if (editing) {
    return (
      <Section title="About this style">
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Name">
            <TextInput value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Best for" hint="Comma-separated, e.g. cats, golden hour">
            <TextInput value={bestFor} onChange={(e) => setBestFor(e.target.value)} />
          </Field>
          <Field label="Description" className="md:row-span-2">
            <TextArea rows={4} value={description} maxLength={2000} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Field label="Avoid on" hint="Comma-separated">
            <TextInput value={avoidOn} onChange={(e) => setAvoidOn(e.target.value)} />
          </Field>
        </div>
        <SaveBar
          onSave={(note) => void save(note)}
          onCancel={() => setEditing(false)}
          saving={saver.saving}
          disabled={!name.trim()}
        />
      </Section>
    )
  }

  return (
    <Section title="About this style" actions={<EditButton onClick={start} label="Edit name and description" />}>
      <div className="grid gap-4 md:grid-cols-3">
        <p className="text-sm leading-relaxed md:col-span-2">
          {style.description || <span className="text-muted">No description yet.</span>}
        </p>
        <div className="flex flex-col gap-3">
          <ChipList title="Best for" items={style.best_for} tone="ok" />
          <ChipList title="Avoid on" items={style.avoid_on} tone="err" />
        </div>
      </div>
    </Section>
  )
}

function ChipList({ title, items, tone }: { title: string; items: string[]; tone: 'ok' | 'err' }) {
  return (
    <div>
      <h3 className="mb-1 text-[11px] font-medium tracking-wide text-muted uppercase">{title}</h3>
      {items.length ? (
        <div className="flex flex-wrap gap-1.5">
          {items.map((t) => (
            <Chip key={t} tone={tone}>
              {t}
            </Chip>
          ))}
        </div>
      ) : (
        <span className="text-xs text-muted">—</span>
      )}
    </div>
  )
}
