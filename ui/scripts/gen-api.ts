/**
 * Generate TypeScript types for the HTTP API from the backend's OpenAPI schema.
 *
 *   npm run gen:api     (exports ../openapi via `photoedit openapi`, then runs this script)
 *
 * A test (gen-api.test.ts) fails when src/api/schema.d.ts is out of date with openapi.json, and a Python test
 * fails when openapi.json is out of date with the backend, so the UI can't silently drift from the API.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import openapiTS, { astToString } from 'openapi-typescript'

export const SCHEMA_FILE = fileURLToPath(new URL('../openapi.json', import.meta.url))
export const TYPES_FILE = fileURLToPath(new URL('../src/api/schema.d.ts', import.meta.url))

const BANNER = `/**
 * Generated from openapi.json by scripts/gen-api.ts. Do not edit by hand.
 * Regenerate with: npm run gen:api
 */

`

export async function generateTypes(schemaJson: string): Promise<string> {
  const ast = await openapiTS(schemaJson)
  return BANNER + astToString(ast)
}

async function main(): Promise<void> {
  const types = await generateTypes(readFileSync(SCHEMA_FILE, 'utf8'))
  writeFileSync(TYPES_FILE, types, 'utf8')
  console.log(`Wrote ${TYPES_FILE}`)
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main()
}
