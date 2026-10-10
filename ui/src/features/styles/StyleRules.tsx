/** The adaptive rules: how the style adapts to each photo (exposure metering, white balance). */
import { useState } from 'react'
import type { ExposureMetering, ExposureRule, Style, StyleRule, WhiteBalanceMode, WhiteBalanceRule } from '../../api/types'
import { Field, Select, Switch, TextInput } from '../../components/ui'
import { EditButton, SaveBar, Section } from './StyleSection'
import { METERING, WB_MODES, describeRule } from './styleWords'
import type { StyleSave } from './useStyleSave'

const DEFAULT_EXPOSURE: ExposureRule = {
  type: 'exposure',
  rule_version: 1,
  metering: 'middle',
  target: null,
  use_group: true,
  strength: 100,
  max_change: 1.5,
}

const DEFAULT_WB: WhiteBalanceRule = {
  type: 'white_balance',
  rule_version: 1,
  mode: 'as_shot',
  temperature_offset: 0,
  tint_offset: 0,
  temperature: null,
  tint: null,
}

const exposureOf = (rules: StyleRule[]) => rules.find((r): r is ExposureRule => r.type === 'exposure') ?? null
const whiteBalanceOf = (rules: StyleRule[]) =>
  rules.find((r): r is WhiteBalanceRule => r.type === 'white_balance') ?? null

export function StyleRules({ style, saver }: { style: Style; saver: StyleSave }) {
  const [editing, setEditing] = useState(false)
  const [exposure, setExposure] = useState<ExposureRule | null>(null)
  const [wb, setWb] = useState<WhiteBalanceRule | null>(null)

  const start = () => {
    setExposure(exposureOf(style.rules))
    setWb(whiteBalanceOf(style.rules))
    setEditing(true)
  }

  const save = async (note: string) => {
    const rules = [exposure, wb].filter((r): r is StyleRule => r !== null)
    if (await saver.save({ rules }, note)) setEditing(false)
  }

  if (!editing) {
    return (
      <Section title="Adaptive rules" actions={<EditButton onClick={start} label="Edit rules" />}>
        {style.rules.length ? (
          <ul className="flex flex-col gap-1 text-sm">
            {style.rules.map((r) => (
              <li key={r.type}>{describeRule(r)}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">None: the style's values are the same on every photo.</p>
        )}
      </Section>
    )
  }

  return (
    <Section title="Adaptive rules">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-3 rounded border border-line p-3">
          <Switch
            label="Auto exposure"
            checked={exposure !== null}
            onCheckedChange={(on) => setExposure(on ? { ...DEFAULT_EXPOSURE } : null)}
          />
          {exposure && (
            <>
              <Field label="Metering" hint={METERING[exposure.metering].hint}>
                <Select
                  value={exposure.metering}
                  onChange={(e) => setExposure({ ...exposure, metering: e.target.value as ExposureMetering })}
                >
                  {Object.entries(METERING).map(([value, m]) => (
                    <option key={value} value={value}>
                      {m.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <div className="grid grid-cols-3 gap-2">
                <Field label="Target (stops)" hint="Empty = default">
                  <NumberInput
                    value={exposure.target}
                    min={-4}
                    max={4}
                    step={0.1}
                    optional
                    onChange={(target) => setExposure({ ...exposure, target })}
                  />
                </Field>
                <Field label="Strength %">
                  <NumberInput
                    value={exposure.strength}
                    min={0}
                    max={100}
                    step={5}
                    onChange={(v) => setExposure({ ...exposure, strength: v ?? 100 })}
                  />
                </Field>
                <Field label="Max change EV">
                  <NumberInput
                    value={exposure.max_change}
                    min={0}
                    max={3}
                    step={0.25}
                    onChange={(v) => setExposure({ ...exposure, max_change: v ?? 1.5 })}
                  />
                </Field>
              </div>
              <Switch
                label="Use the group reference when evened out"
                checked={exposure.use_group}
                onCheckedChange={(use_group) => setExposure({ ...exposure, use_group })}
              />
            </>
          )}
        </div>

        <div className="flex flex-col gap-3 rounded border border-line p-3">
          <Switch
            label="White balance rule"
            checked={wb !== null}
            onCheckedChange={(on) => setWb(on ? { ...DEFAULT_WB } : null)}
          />
          {wb && (
            <>
              <Field label="Mode" hint={WB_MODES[wb.mode].hint}>
                <Select
                  value={wb.mode}
                  onChange={(e) => {
                    const mode = e.target.value as WhiteBalanceMode
                    setWb(
                      mode === 'fixed'
                        ? { ...wb, mode, temperature_offset: 0, tint_offset: 0, temperature: 5500, tint: 0 }
                        : { ...wb, mode, temperature: null, tint: null },
                    )
                  }}
                >
                  {Object.entries(WB_MODES).map(([value, m]) => (
                    <option key={value} value={value}>
                      {m.label}
                    </option>
                  ))}
                </Select>
              </Field>
              {wb.mode === 'fixed' ? (
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Temperature K">
                    <NumberInput
                      value={wb.temperature}
                      min={2000}
                      max={50000}
                      step={50}
                      onChange={(v) => setWb({ ...wb, temperature: v ?? 5500 })}
                    />
                  </Field>
                  <Field label="Tint">
                    <NumberInput
                      value={wb.tint}
                      min={-150}
                      max={150}
                      step={1}
                      onChange={(v) => setWb({ ...wb, tint: v ?? 0 })}
                    />
                  </Field>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Temperature offset K" hint="At 5500 K; same look under any light">
                    <NumberInput
                      value={wb.temperature_offset}
                      min={-3000}
                      max={3000}
                      step={50}
                      onChange={(v) => setWb({ ...wb, temperature_offset: v ?? 0 })}
                    />
                  </Field>
                  <Field label="Tint offset">
                    <NumberInput
                      value={wb.tint_offset}
                      min={-50}
                      max={50}
                      step={1}
                      onChange={(v) => setWb({ ...wb, tint_offset: v ?? 0 })}
                    />
                  </Field>
                </div>
              )}
            </>
          )}
        </div>
      </div>
      <SaveBar onSave={(note) => void save(note)} onCancel={() => setEditing(false)} saving={saver.saving} />
    </Section>
  )
}

/** A number field; out-of-range input is shown as invalid and not passed on (the server would reject it). */
function NumberInput({
  value,
  min,
  max,
  step,
  optional,
  onChange,
}: {
  value: number | null
  min: number
  max: number
  step: number
  optional?: boolean
  onChange: (value: number | null) => void
}) {
  const [text, setText] = useState(value === null ? '' : String(value))
  const parsed = text.trim() === '' ? null : Number(text)
  const valid = parsed === null ? Boolean(optional) : Number.isFinite(parsed) && parsed >= min && parsed <= max
  return (
    <TextInput
      type="number"
      inputMode="decimal"
      min={min}
      max={max}
      step={step}
      value={text}
      aria-invalid={!valid}
      className={valid ? undefined : 'border-err'}
      onChange={(e) => {
        setText(e.target.value)
        const next = e.target.value.trim() === '' ? null : Number(e.target.value)
        if (next === null ? optional : Number.isFinite(next) && next >= min && next <= max) onChange(next)
      }}
    />
  )
}
