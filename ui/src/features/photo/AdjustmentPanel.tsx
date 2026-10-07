import { Accordion, Slider, Tabs } from 'radix-ui'
import { ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'
import type { AdjustmentParams, PhotoEdit } from '../../api/types'
import { Tooltip } from '../../components/ui'
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
  type SliderField,
} from './adjustmentFields'

function AdjustmentSlider({
  field,
  params,
  overridden,
  label,
  swatch,
}: {
  field: SliderField
  params: AdjustmentParams
  overridden: Set<string>
  label?: string
  swatch?: string
}) {
  const raw = getPath(params, field.path)
  const value = typeof raw === 'number' ? raw : null
  const isOverridden = overridden.has(field.path)
  const text = formatValue(field, value)
  const name = label ?? field.label
  return (
    <div className="flex flex-col gap-1 py-1" data-path={field.path}>
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5 capitalize">
          {swatch && <span className="size-2.5 rounded-full" style={{ background: swatch }} aria-hidden />}
          {name}
          {isOverridden && (
            <Tooltip content="Overridden for this photo (differs from the style)">
              <span className="size-1.5 rounded-full bg-accent" aria-label="overridden for this photo" />
            </Tooltip>
          )}
        </span>
        <span className={cn('font-mono tabular-nums', value === null ? 'text-muted' : 'text-strong')}>{text}</span>
      </div>
      <Slider.Root
        disabled
        min={field.min}
        max={field.max}
        step={field.step}
        value={[value ?? (field.min + field.max) / 2]}
        aria-label={name}
        className="relative flex h-3 w-full touch-none items-center opacity-80 select-none"
      >
        <Slider.Track className="relative h-0.5 grow rounded-full bg-line">
          <Slider.Range className="absolute h-full rounded-full bg-muted" />
        </Slider.Track>
        <Slider.Thumb
          className={cn(
            'block size-2.5 rounded-full border',
            value === null ? 'border-line bg-raised' : 'border-fg bg-strong',
          )}
        />
      </Slider.Root>
    </div>
  )
}

function Group({ value, title, children }: { value: string; title: string; children: ReactNode }) {
  return (
    <Accordion.Item value={value} className="border-b border-line">
      <Accordion.Header>
        <Accordion.Trigger className="group flex w-full items-center justify-between px-3 py-2 text-xs font-semibold text-strong hover:bg-hover">
          {title}
          <ChevronDown className="size-3.5 text-muted transition-transform group-data-[state=open]:rotate-180" aria-hidden />
        </Accordion.Trigger>
      </Accordion.Header>
      <Accordion.Content className="px-3 pb-3">{children}</Accordion.Content>
    </Accordion.Item>
  )
}

function CurvePreview({ params }: { params: AdjustmentParams }) {
  const curves = [
    { key: 'rgb', color: '#d6d6d6' },
    { key: 'red', color: '#e05050' },
    { key: 'green', color: '#4fb453' },
    { key: 'blue', color: '#4a78d8' },
  ] as const
  return (
    <svg viewBox="0 0 100 100" className="mb-2 aspect-square w-full rounded border border-line bg-bg" aria-label="Tone curve">
      {[25, 50, 75].map((v) => (
        <g key={v} stroke="#333" strokeWidth="0.4">
          <line x1={v} y1="0" x2={v} y2="100" />
          <line x1="0" y1={v} x2="100" y2={v} />
        </g>
      ))}
      <line x1="0" y1="100" x2="100" y2="0" stroke="#444" strokeDasharray="2 2" strokeWidth="0.5" />
      {curves.map(({ key, color }) => (
        <polyline
          key={key}
          fill="none"
          stroke={color}
          strokeWidth="1"
          points={params.tone_curve[key].map((p) => `${p.x * 100},${100 - p.y * 100}`).join(' ')}
        />
      ))}
    </svg>
  )
}

/** Read-only view of every adjustment (Phase 1). Sliders become editable in Phase 3. */
export function AdjustmentPanel({ edit, styleName }: { edit: PhotoEdit; styleName?: string }) {
  const params = edit.adjustments
  const overridden = new Set(edit.overridden)
  const slider = (field: SliderField, extra: { label?: string; swatch?: string } = {}) => (
    <AdjustmentSlider key={field.path} field={field} params={params} overridden={overridden} {...extra} />
  )
  const geometry = params.geometry
  const crop = geometry.crop

  return (
    <div className="flex flex-col">
      <div className="border-b border-line px-3 py-2 text-xs">
        <p className="text-muted">Style</p>
        <p className="font-medium text-strong">{styleName ?? 'No style'}</p>
        {edit.overridden.length > 0 && (
          <p className="pt-1 text-muted">
            <span className="mr-1 inline-block size-1.5 rounded-full bg-accent align-middle" />
            {edit.overridden.length} per-photo override{edit.overridden.length === 1 ? '' : 's'}
          </p>
        )}
        <p className="pt-2 text-[11px] text-warn">Read-only preview. Editing arrives in Phase 3.</p>
      </div>
      <Accordion.Root type="multiple" defaultValue={['white_balance', 'tone', 'presence']}>
        {BASIC_GROUPS.map((group) => (
          <Group key={group.id} value={group.id} title={group.title}>
            {group.id === 'tone_curve' && <CurvePreview params={params} />}
            {group.fields.map((f) => slider(f))}
          </Group>
        ))}
        <Group value="hsl" title="HSL / color mixer">
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
        <Group value="color_grading" title="Color grading">
          {GRADE_WHEELS.map((wheel) => (
            <div key={wheel.key} className="mb-2">
              <p className="pt-1 text-[11px] font-semibold text-muted uppercase">{wheel.label}</p>
              {gradeFields(wheel.key).map((f) => slider(f))}
            </div>
          ))}
          {GRADING_GLOBAL.map((f) => slider(f))}
        </Group>
        {DETAIL_GROUPS.map((group) => (
          <Group key={group.id} value={group.id} title={group.title}>
            {group.fields.map((f) => slider(f))}
          </Group>
        ))}
        <Group value="geometry" title="Crop & geometry">
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
            <dt className="text-muted">Crop</dt>
            <dd className="font-mono">
              {crop.left.toFixed(2)}, {crop.top.toFixed(2)} → {crop.right.toFixed(2)}, {crop.bottom.toFixed(2)}
            </dd>
            <dt className="text-muted">Aspect</dt>
            <dd>{geometry.aspect ?? 'Free'}</dd>
            <dt className="text-muted">Flip</dt>
            <dd>
              {[geometry.flip_horizontal && 'horizontal', geometry.flip_vertical && 'vertical']
                .filter(Boolean)
                .join(', ') || 'None'}
            </dd>
          </dl>
          {GEOMETRY_FIELDS.map((f) => slider(f))}
        </Group>
        <Group value="lens" title="Lens corrections">
          <dl className="grid grid-cols-2 gap-y-1 text-xs">
            <dt className="text-muted">Profile corrections</dt>
            <dd>{params.lens.profile_corrections ? 'On' : 'Off'}</dd>
            <dt className="text-muted">Remove chromatic aberration</dt>
            <dd>{params.lens.remove_chromatic_aberration ? 'On' : 'Off'}</dd>
          </dl>
        </Group>
      </Accordion.Root>
    </div>
  )
}
