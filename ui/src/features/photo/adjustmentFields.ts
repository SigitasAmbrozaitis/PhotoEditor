/**
 * UI metadata for adjustment parameters: labels, ranges, formatting.
 * Ranges must match the backend schema; adjustmentFields.test.ts checks them against openapi.json.
 */

export interface SliderField {
  /** Dotted path into AdjustmentParams (JSON names), e.g. "tone.exposure". */
  path: string
  label: string
  min: number
  max: number
  step: number
  /** Schema component and property that define the range, for the consistency test. */
  schema: [component: string, property: string]
  format?: (value: number) => string
  /** Label shown when the value is null (e.g. white balance "As shot"). */
  nullLabel?: string
  /** 'log': the slider track is logarithmic (temperature: 2500–10000 K would otherwise be a sliver). */
  scale?: 'log'
}

export interface SliderGroup {
  id: string
  title: string
  fields: SliderField[]
}

const signed = (v: number) => (v > 0 ? `+${round(v)}` : `${round(v)}`)
const round = (v: number) => Math.round(v * 100) / 100

function signed100(path: string, label: string, component: string): SliderField {
  const property = path.split('.').at(-1) ?? path
  return { path, label, min: -100, max: 100, step: 1, schema: [component, property], format: signed }
}

function unsigned100(path: string, label: string, component: string): SliderField {
  const property = path.split('.').at(-1) ?? path
  return { path, label, min: 0, max: 100, step: 1, schema: [component, property] }
}

export const BASIC_GROUPS: SliderGroup[] = [
  {
    id: 'white_balance',
    title: 'White balance',
    fields: [
      {
        path: 'white_balance.temperature',
        label: 'Temperature',
        min: 2000,
        max: 50000,
        step: 50,
        schema: ['WhiteBalance', 'temperature'],
        format: (v) => `${Math.round(v)} K`,
        nullLabel: 'As shot',
        scale: 'log',
      },
      {
        path: 'white_balance.tint',
        label: 'Tint',
        min: -150,
        max: 150,
        step: 1,
        schema: ['WhiteBalance', 'tint'],
        format: (v) => signed(Math.round(v)),
        nullLabel: 'As shot',
      },
    ],
  },
  {
    id: 'tone',
    title: 'Tone',
    fields: [
      {
        path: 'tone.exposure',
        label: 'Exposure',
        min: -5,
        max: 5,
        step: 0.05,
        schema: ['Tone', 'exposure'],
        format: (v) => `${signed(v)} EV`,
      },
      signed100('tone.contrast', 'Contrast', 'Tone'),
      signed100('tone.highlights', 'Highlights', 'Tone'),
      signed100('tone.shadows', 'Shadows', 'Tone'),
      signed100('tone.whites', 'Whites', 'Tone'),
      signed100('tone.blacks', 'Blacks', 'Tone'),
    ],
  },
  {
    id: 'presence',
    title: 'Presence',
    fields: [
      signed100('presence.vibrance', 'Vibrance', 'Presence'),
      signed100('presence.saturation', 'Saturation', 'Presence'),
      signed100('presence.clarity', 'Clarity', 'Presence'),
      signed100('presence.texture', 'Texture', 'Presence'),
      signed100('presence.dehaze', 'Dehaze', 'Presence'),
    ],
  },
  {
    id: 'tone_curve',
    title: 'Tone curve (parametric)',
    fields: [
      signed100('tone_curve.highlights', 'Highlights', 'ToneCurve'),
      signed100('tone_curve.lights', 'Lights', 'ToneCurve'),
      signed100('tone_curve.darks', 'Darks', 'ToneCurve'),
      signed100('tone_curve.shadows', 'Shadows', 'ToneCurve'),
    ],
  },
]

export const HSL_BANDS = ['red', 'orange', 'yellow', 'green', 'aqua', 'blue', 'purple', 'magenta'] as const
export const HSL_SWATCH: Record<(typeof HSL_BANDS)[number], string> = {
  red: '#e05050',
  orange: '#e8913a',
  yellow: '#e3cf3f',
  green: '#4fb453',
  aqua: '#42c1c4',
  blue: '#4a78d8',
  purple: '#8a5ad6',
  magenta: '#d454b4',
}
export const HSL_CHANNELS = [
  { key: 'hue', label: 'Hue' },
  { key: 'saturation', label: 'Saturation' },
  { key: 'luminance', label: 'Luminance' },
] as const

export function hslField(band: string, channel: string): SliderField {
  return { ...signed100(`hsl.${band}.${channel}`, band, 'HslBand'), schema: ['HslBand', channel] }
}

export const GRADE_WHEELS = [
  { key: 'shadows', label: 'Shadows' },
  { key: 'midtones', label: 'Midtones' },
  { key: 'highlights', label: 'Highlights' },
  { key: 'global', label: 'Global' },
] as const

export function gradeFields(wheel: string): SliderField[] {
  return [
    {
      path: `color_grading.${wheel}.hue`,
      label: 'Hue',
      min: 0,
      max: 359,
      step: 1,
      schema: ['GradeWheel', 'hue'],
      format: (v) => `${Math.round(v)}°`,
    },
    unsigned100(`color_grading.${wheel}.saturation`, 'Saturation', 'GradeWheel'),
    signed100(`color_grading.${wheel}.luminance`, 'Luminance', 'GradeWheel'),
  ]
}

export const GRADING_GLOBAL: SliderField[] = [
  unsigned100('color_grading.blending', 'Blending', 'ColorGrading'),
  signed100('color_grading.balance', 'Balance', 'ColorGrading'),
]

export const DETAIL_GROUPS: SliderGroup[] = [
  {
    id: 'sharpening',
    title: 'Sharpening',
    fields: [
      { path: 'detail.sharpening.amount', label: 'Amount', min: 0, max: 150, step: 1, schema: ['Sharpening', 'amount'] },
      {
        path: 'detail.sharpening.radius',
        label: 'Radius',
        min: 0.5,
        max: 3,
        step: 0.1,
        schema: ['Sharpening', 'radius'],
        format: (v) => v.toFixed(1),
      },
      unsigned100('detail.sharpening.detail', 'Detail', 'Sharpening'),
      unsigned100('detail.sharpening.masking', 'Masking', 'Sharpening'),
    ],
  },
  {
    id: 'noise_reduction',
    title: 'Noise reduction',
    fields: [
      unsigned100('detail.noise_reduction.luminance', 'Luminance', 'NoiseReduction'),
      unsigned100('detail.noise_reduction.color', 'Color', 'NoiseReduction'),
    ],
  },
  {
    id: 'vignette',
    title: 'Vignette',
    fields: [
      signed100('effects.vignette.amount', 'Amount', 'Vignette'),
      unsigned100('effects.vignette.midpoint', 'Midpoint', 'Vignette'),
      signed100('effects.vignette.roundness', 'Roundness', 'Vignette'),
      unsigned100('effects.vignette.feather', 'Feather', 'Vignette'),
    ],
  },
  {
    id: 'grain',
    title: 'Grain',
    fields: [
      unsigned100('effects.grain.amount', 'Amount', 'Grain'),
      unsigned100('effects.grain.size', 'Size', 'Grain'),
      unsigned100('effects.grain.roughness', 'Roughness', 'Grain'),
    ],
  },
]

export const GEOMETRY_FIELDS: SliderField[] = [
  {
    path: 'geometry.angle',
    label: 'Straighten',
    min: -45,
    max: 45,
    step: 0.1,
    schema: ['Geometry', 'angle'],
    format: (v) => `${signed(v)}°`,
  },
]

/** Read a dotted path from a nested object. */
export function getPath(obj: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((cur, key) => {
    if (cur && typeof cur === 'object' && key in cur) return (cur as Record<string, unknown>)[key]
    return undefined
  }, obj)
}

/** Slider track position ↔ parameter value (identity for linear fields). */
export function toTrack(field: SliderField, value: number): number {
  return field.scale === 'log' ? Math.log(value) : value
}

export function fromTrack(field: SliderField, position: number): number {
  if (field.scale !== 'log') return position
  return Math.min(field.max, Math.max(field.min, Math.round(Math.exp(position) / field.step) * field.step))
}

export function formatValue(field: SliderField, value: number | null): string {
  if (value === null) return field.nullLabel ?? '—'
  return field.format ? field.format(value) : String(round(value))
}

/** Every slider field the panel can show (used by the schema consistency test). */
export function allSliderFields(): SliderField[] {
  return [
    ...BASIC_GROUPS.flatMap((g) => g.fields),
    ...HSL_BANDS.flatMap((b) => HSL_CHANNELS.map((c) => hslField(b, c.key))),
    ...GRADE_WHEELS.flatMap((w) => gradeFields(w.key)),
    ...GRADING_GLOBAL,
    ...DETAIL_GROUPS.flatMap((g) => g.fields),
    ...GEOMETRY_FIELDS,
  ]
}
