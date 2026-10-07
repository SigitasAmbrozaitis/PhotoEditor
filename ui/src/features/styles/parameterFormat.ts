import { allSliderFields, formatValue } from '../photo/adjustmentFields'

const FIELDS = new Map(allSliderFields().map((f) => [f.path, f]))

/** "color_grading.shadows.hue" → "Color grading › Shadows › Hue" */
export function parameterLabel(path: string): string {
  return path
    .split('.')
    .map((part) => {
      const words = part.replace(/_/g, ' ')
      return words.charAt(0).toUpperCase() + words.slice(1)
    })
    .join(' › ')
}

export function parameterValue(path: string, value: unknown): string {
  const field = FIELDS.get(path)
  if (field && (typeof value === 'number' || value === null)) return formatValue(field, value)
  if (Array.isArray(value)) return 'custom curve'
  if (typeof value === 'boolean') return value ? 'On' : 'Off'
  return String(value)
}
