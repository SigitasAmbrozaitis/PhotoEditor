import { Accordion, Slider, Tabs } from 'radix-ui'
import { ChevronDown, Redo2, RotateCcw, Undo2 } from 'lucide-react'
import { useEffect, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react'
import { useEngine } from '../../api/queries'
import type { AdjustmentParams, PhotoDetail } from '../../api/types'
import { Button, Tooltip } from '../../components/ui'
import { cn } from '../../lib/cn'
import {
  BASIC_GROUPS,
  DETAIL_GROUPS,
  formatValue,
  GEOMETRY_FIELDS,
  getPath,
  GRADE_WHEELS,
  gradeFields,
  GRADING_GLOBAL,
  HSL_BANDS,
  HSL_CHANNELS,
  HSL_SWATCH,
  hslField,
  fromTrack,
  toTrack,
  type SliderField,
} from './adjustmentFields'
import { useEditSession, withValue, type EditSession } from './editSession'
import { PhotoStyle } from './PhotoStyle'
import { ToneCurveEditor } from './ToneCurveEditor'

/** The phase that adds a parameter, if it isn't available yet (from the engine's list of prefixes). */
function laterPhase(path: string, later: Record<string, number> | undefined): number | null {
  if (!later) return null
  for (const [prefix, phase] of Object.entries(later)) {
    if (path === prefix || path.startsWith(`${prefix}.`)) return phase
  }
  return null
}

function resetPaths(params: AdjustmentParams, defaults: AdjustmentParams, paths: string[]): AdjustmentParams {
  return paths.reduce((acc, path) => withValue(acc, path, getPath(defaults, path)), params)
}

interface SliderContext {
  session: EditSession
  defaults: AdjustmentParams
  overridden: Set<string>
  fromStyle: Set<string>
  asShot: PhotoDetail['as_shot']
  later: Record<string, number> | undefined
}

function NumberEntry({
  field,
  value,
  onDone,
}: {
  field: SliderField
  value: number
  onDone: (value: number | null) => void
}) {
  const [text, setText] = useState(String(Math.round(value * 100) / 100))
  const parsed = Number(text)
  const valid = text.trim() !== '' && Number.isFinite(parsed) && parsed >= field.min && parsed <= field.max
  const onKeyDown = (e: ReactKeyboardEvent) => {
    if (e.key === 'Enter' && valid) onDone(parsed)
    else if (e.key === 'Escape') onDone(null)
  }
  return (
    <input
      autoFocus
      type="text"
      inputMode="decimal"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onKeyDown={onKeyDown}
      onBlur={() => onDone(valid ? parsed : null)}
      aria-label={`${field.label} value`}
      aria-invalid={!valid}
      title={`${field.min} to ${field.max}`}
      className={cn(
        'w-16 rounded border bg-bg px-1 text-right font-mono text-xs text-strong outline-none',
        valid ? 'border-accent' : 'border-err',
      )}
    />
  )
}

function AdjustmentSlider({
  field,
  ctx,
  label,
  swatch,
}: {
  field: SliderField
  ctx: SliderContext
  label?: string
  swatch?: string
}) {
  const { session, defaults, overridden, fromStyle, asShot, later } = ctx
  const [typing, setTyping] = useState(false)
  const raw = getPath(session.params, field.path)
  const value = typeof raw === 'number' ? raw : null
  const phase = laterPhase(field.path, later)
  const asShotValue =
    field.path === 'white_balance.temperature' ? asShot?.temperature : field.path === 'white_balance.tint' ? asShot?.tint : undefined
  const position = value ?? asShotValue ?? (field.min + field.max) / 2
  const name = label ?? field.label
  const text =
    value === null && asShotValue !== undefined
      ? `As shot ${formatValue(field, asShotValue)}`
      : formatValue(field, value)
  const set = (v: unknown) => session.set(field.path, v)

  return (
    <div
      className={cn('flex flex-col gap-1 py-1', phase !== null && 'opacity-60')}
      data-path={field.path}
      onDoubleClick={() => phase === null && set(getPath(defaults, field.path))}
    >
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5 capitalize">
          {swatch && <span className="size-2.5 rounded-full" style={{ background: swatch }} aria-hidden />}
          {name}
          {overridden.has(field.path) ? (
            <Tooltip content="Changed for this photo">
              <span className="size-1.5 rounded-full bg-accent" aria-label="changed for this photo" />
            </Tooltip>
          ) : (
            fromStyle.has(field.path) && (
              <Tooltip content="From the style (double-click a slider to go back to the style's value)">
                <span className="size-1.5 rounded-full bg-warn" aria-label="from the style" />
              </Tooltip>
            )
          )}
          {phase !== null && (
            <span className="rounded bg-raised px-1 text-[10px] tracking-wide text-muted normal-case">
              Phase {phase}
            </span>
          )}
        </span>
        {typing ? (
          <NumberEntry
            field={field}
            value={position}
            onDone={(v) => {
              setTyping(false)
              if (v !== null) set(v)
            }}
          />
        ) : (
          <button
            type="button"
            disabled={phase !== null}
            onClick={() => setTyping(true)}
            title="Click to type a value"
            className={cn('font-mono tabular-nums', value === null ? 'text-muted' : 'text-strong', 'disabled:cursor-default')}
          >
            {text}
          </button>
        )}
      </div>
      <Slider.Root
        disabled={phase !== null}
        min={toTrack(field, field.min)}
        max={toTrack(field, field.max)}
        step={field.scale === 'log' ? 0.001 : field.step}
        value={[toTrack(field, position)]}
        onValueChange={([v]) => v !== undefined && session.preview(field.path, fromTrack(field, v))}
        onValueCommit={([v]) => v !== undefined && set(fromTrack(field, v))}
        aria-label={name}
        className="relative flex h-3 w-full touch-none items-center select-none"
      >
        <Slider.Track className="relative h-0.5 grow rounded-full bg-line">
          <Slider.Range className="absolute h-full rounded-full bg-muted" />
        </Slider.Track>
        <Slider.Thumb
          aria-label={name}
          className={cn(
            'block size-3 rounded-full border focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none',
            value === null ? 'border-line bg-raised' : 'border-fg bg-strong',
          )}
        />
      </Slider.Root>
    </div>
  )
}

function Group({
  value,
  title,
  onReset,
  children,
}: {
  value: string
  title: string
  onReset?: () => void
  children: ReactNode
}) {
  return (
    <Accordion.Item value={value} className="border-b border-line">
      <Accordion.Header className="flex items-center">
        <Accordion.Trigger className="group flex flex-1 items-center justify-between px-3 py-2 text-xs font-semibold text-strong hover:bg-hover">
          {title}
          <ChevronDown className="size-3.5 text-muted transition-transform group-data-[state=open]:rotate-180" aria-hidden />
        </Accordion.Trigger>
        {onReset && (
          <button
            type="button"
            onClick={onReset}
            aria-label={`Reset ${title}`}
            title={`Reset ${title}`}
            className="px-2 py-2 text-muted hover:text-fg"
          >
            <RotateCcw className="size-3" aria-hidden />
          </button>
        )}
      </Accordion.Header>
      <Accordion.Content className="px-3 pb-3">{children}</Accordion.Content>
    </Accordion.Item>
  )
}

/** The adjustments of the open photo: every slider edits and saves automatically. */
export function AdjustmentPanel({ detail }: { detail: PhotoDetail }) {
  const session = useEditSession(detail)
  const engine = useEngine()
  const defaults = detail.edit.defaults
  const ctx: SliderContext = {
    session,
    defaults,
    overridden: new Set(detail.edit.overridden),
    fromStyle: new Set(detail.edit.style_values),
    asShot: detail.as_shot,
    later: engine.data?.later_phase_parameters,
  }
  const slider = (field: SliderField, extra: { label?: string; swatch?: string } = {}) => (
    <AdjustmentSlider key={field.path} field={field} ctx={ctx} {...extra} />
  )
  const resetGroup = (paths: string[]) => () => session.commit(resetPaths(session.params, defaults, paths))
  const { undo, redo } = session

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (!(e.ctrlKey || e.metaKey)) return
      const key = e.key.toLowerCase()
      if (key === 'z' && !e.shiftKey) {
        e.preventDefault()
        undo()
      } else if ((key === 'z' && e.shiftKey) || key === 'y') {
        e.preventDefault()
        redo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undo, redo])

  const changed = detail.edit.overridden.length
  return (
    <div className="flex flex-col">
      <div className="flex flex-col gap-2 border-b border-line px-3 py-2 text-xs">
        <PhotoStyle detail={detail} />
        <div className="flex items-start justify-between gap-2">
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" aria-label="Undo" title="Undo (Ctrl+Z)" disabled={!session.canUndo} onClick={undo}>
              <Undo2 className="size-3.5" aria-hidden />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              aria-label="Redo"
              title="Redo (Ctrl+Shift+Z)"
              disabled={!session.canRedo}
              onClick={redo}
            >
              <Redo2 className="size-3.5" aria-hidden />
            </Button>
            <Button
              size="sm"
              disabled={changed === 0 && !session.canUndo}
              onClick={session.resetAll}
              title={detail.edit.style_id ? "Drop this photo's own changes (the style stays)" : 'Back to the unedited photo'}
            >
              Reset all
            </Button>
          </div>
        </div>
        <p className="text-muted" role="status">
          {session.error ? (
            <span className="text-err">{session.error}</span>
          ) : session.saving ? (
            'Saving…'
          ) : changed > 0 ? (
            `${changed} change${changed === 1 ? '' : 's'} for this photo · saved`
          ) : detail.edit.style_id ? (
            'The style only'
          ) : (
            'Unedited'
          )}
        </p>
        <p className="text-[11px] text-muted">Double-click a slider to reset it · click a value to type one</p>
      </div>
      <Accordion.Root type="multiple" defaultValue={['white_balance', 'tone', 'presence']}>
        {BASIC_GROUPS.map((group) => (
          <Group
            key={group.id}
            value={group.id}
            title={group.title}
            onReset={resetGroup(
              group.id === 'tone_curve'
                ? [...group.fields.map((f) => f.path), 'tone_curve.rgb', 'tone_curve.red', 'tone_curve.green', 'tone_curve.blue']
                : group.fields.map((f) => f.path),
            )}
          >
            {group.id === 'tone_curve' && <ToneCurveEditor session={session} />}
            {group.fields.map((f) => slider(f))}
          </Group>
        ))}
        <Group
          value="hsl"
          title="HSL / color mixer"
          onReset={resetGroup(HSL_BANDS.flatMap((b) => HSL_CHANNELS.map((c) => `hsl.${b}.${c.key}`)))}
        >
          <Tabs.Root defaultValue="hue">
            <Tabs.List className="mb-2 flex gap-1" aria-label="HSL channel">
              {HSL_CHANNELS.map((c) => (
                <Tabs.Trigger
                  key={c.key}
                  value={c.key}
                  className="rounded px-2 py-0.5 text-[11px] text-muted data-[state=active]:bg-raised data-[state=active]:text-strong"
                >
                  {c.label}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
            {HSL_CHANNELS.map((c) => (
              <Tabs.Content key={c.key} value={c.key}>
                {HSL_BANDS.map((band) => slider(hslField(band, c.key), { label: band, swatch: HSL_SWATCH[band] }))}
              </Tabs.Content>
            ))}
          </Tabs.Root>
        </Group>
        <Group
          value="color_grading"
          title="Color grading"
          onReset={resetGroup([...GRADE_WHEELS.flatMap((w) => gradeFields(w.key).map((f) => f.path)), ...GRADING_GLOBAL.map((f) => f.path)])}
        >
          {GRADE_WHEELS.map((wheel) => (
            <div key={wheel.key} className="mb-2">
              <p className="pt-1 text-[11px] font-semibold text-muted uppercase">{wheel.label}</p>
              {gradeFields(wheel.key).map((f) => slider(f))}
            </div>
          ))}
          {GRADING_GLOBAL.map((f) => slider(f))}
        </Group>
        {DETAIL_GROUPS.map((group) => (
          <Group
            key={group.id}
            value={group.id}
            title={group.title}
            onReset={
              group.fields.every((f) => laterPhase(f.path, ctx.later) !== null)
                ? undefined
                : resetGroup(group.fields.map((f) => f.path))
            }
          >
            {group.fields.map((f) => slider(f))}
          </Group>
        ))}
        <Group value="geometry" title="Crop & geometry">
          <p className="pb-1 text-[11px] text-muted">Crop, straighten and flip arrive in Phase 6.</p>
          {GEOMETRY_FIELDS.map((f) => slider(f))}
        </Group>
        <Group value="lens" title="Lens corrections">
          <p className="text-[11px] text-muted">Profile corrections and chromatic aberration arrive in Phase 9.</p>
        </Group>
      </Accordion.Root>
    </div>
  )
}
