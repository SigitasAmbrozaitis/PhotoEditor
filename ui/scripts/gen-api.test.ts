// @vitest-environment node
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { SCHEMA_FILE, TYPES_FILE, generateTypes } from './gen-api.ts'

describe('generated API types', () => {
  it('src/api/schema.d.ts is up to date with openapi.json (run `npm run gen:api`)', async () => {
    const expected = await generateTypes(readFileSync(SCHEMA_FILE, 'utf8'))
    const actual = readFileSync(TYPES_FILE, 'utf8')
    expect(actual.replace(/\r\n/g, '\n')).toBe(expected.replace(/\r\n/g, '\n'))
  }, 20_000)
})
