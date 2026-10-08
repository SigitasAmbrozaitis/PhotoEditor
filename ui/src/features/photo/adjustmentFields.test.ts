// @vitest-environment node
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { allSliderFields, formatValue, getPath } from './adjustmentFields'
import { neutralAdjustments } from '../../test/fixtures'

interface PropSchema {
  minimum?: number
  maximum?: number
  exclusiveMaximum?: number
  anyOf?: PropSchema[]
}

const openapi = JSON.parse(readFileSync(fileURLToPath(new URL('../../../openapi.json', import.meta.url)), 'utf8')) as {
  components: { schemas: Record<string, { properties: Record<string, PropSchema> }> }
}

function range(component: string, property: string): { min?: number; max?: number; exclusiveMax?: number } {
  // Models used both in requests and responses appear as `Name-Input` and `Name-Output`; the ranges are the same.
  const schemas = openapi.components.schemas
  const prop = (schemas[component] ?? schemas[`${component}-Output`])?.properties[property]
  if (!prop) throw new Error(`${component}.${property} missing from openapi.json`)
  const numeric = prop.anyOf?.find((s) => s.minimum !== undefined || s.maximum !== undefined) ?? prop
  return { min: numeric.minimum, max: numeric.maximum, exclusiveMax: numeric.exclusiveMaximum }
}

describe('adjustment slider metadata', () => {
  it('uses the same ranges as the backend schema', () => {
    for (const field of allSliderFields()) {
      const [component, property] = field.schema
      const r = range(component, property)
      expect(field.min, `${field.path} min`).toBe(r.min)
      if (r.exclusiveMax !== undefined) {
        expect(field.max, `${field.path} max`).toBeLessThan(r.exclusiveMax)
        expect(field.max, `${field.path} max`).toBeGreaterThanOrEqual(r.exclusiveMax - 1)
      } else {
        expect(field.max, `${field.path} max`).toBe(r.max)
      }
    }
  })

  it('every slider path exists in the adjustment params', () => {
    const params = neutralAdjustments()
    for (const field of allSliderFields()) {
      const value = getPath(params, field.path)
      expect(value === null || typeof value === 'number', field.path).toBe(true)
    }
  })

  it('formats values', () => {
    const [temperature, tint] = allSliderFields()
    expect(formatValue(temperature!, null)).toBe('As shot')
    expect(formatValue(temperature!, 5500)).toBe('5500 K')
    expect(formatValue(tint!, 8)).toBe('+8')
    expect(formatValue(tint!, -3)).toBe('-3')
  })
})
