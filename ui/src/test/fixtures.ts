/** Typed test data. Shapes are checked against the generated API schema by the TypeScript compiler. */
import type {
  AdjustmentParams,
  ConsistencyReport,
  DirListing,
  EngineInfo,
  ExportPreset,
  Job,
  LibraryFolder,
  LibraryInfo,
  Photo,
  PhotoDetail,
  Style,
  StyleDiff,
  StyleSummary,
  StyleVersionInfo,
} from '../api/types'

const band = () => ({ hue: 0, saturation: 0, luminance: 0 })
const wheel = () => ({ hue: 0, saturation: 0, luminance: 0 })
const curve = () => [
  { x: 0, y: 0 },
  { x: 1, y: 1 },
]

export function neutralAdjustments(): AdjustmentParams {
  return {
    white_balance: { temperature: null, tint: null },
    tone: { exposure: 0, contrast: 0, highlights: 0, shadows: 0, whites: 0, blacks: 0 },
    presence: { vibrance: 0, saturation: 0, clarity: 0, texture: 0, dehaze: 0 },
    tone_curve: { highlights: 0, lights: 0, darks: 0, shadows: 0, rgb: curve(), red: curve(), green: curve(), blue: curve() },
    hsl: {
      red: band(),
      orange: band(),
      yellow: band(),
      green: band(),
      aqua: band(),
      blue: band(),
      purple: band(),
      magenta: band(),
    },
    color_grading: {
      shadows: wheel(),
      midtones: wheel(),
      highlights: wheel(),
      global: wheel(),
      blending: 50,
      balance: 0,
    },
    detail: {
      sharpening: { amount: 40, radius: 1, detail: 25, masking: 0 },
      noise_reduction: { luminance: 0, color: 25 },
    },
    effects: {
      vignette: { amount: 0, midpoint: 50, roundness: 0, feather: 50 },
      grain: { amount: 0, size: 25, roughness: 50 },
    },
    geometry: {
      crop: { left: 0, top: 0, right: 1, bottom: 1 },
      aspect: null,
      angle: 0,
      flip_horizontal: false,
      flip_vertical: false,
    },
    lens: { profile_corrections: false, remove_chromatic_aberration: false },
  }
}

export const FOLDER = 'C:/Photos/Test'

export const engine: EngineInfo = {
  render_identity: 'dec2-libraw0.22.1-eng1',
  later_phase_parameters: {
    geometry: 6,
    'presence.clarity': 9,
    'presence.texture': 9,
    'presence.dehaze': 9,
    'detail.noise_reduction': 9,
    'effects.grain': 9,
    lens: 9,
  },
}

export function makePhoto(i: number, overrides: Partial<Photo> = {}): Photo {
  const filename = `DSCF${1000 + i}.RAF`
  return {
    id: `p${String(i).padStart(3, '0')}`,
    path: `${FOLDER}/${filename}`,
    filename,
    folder: FOLDER,
    file_size: 26_000_000,
    captured_at: `2026-08-11T0${i % 10}:00:00Z`,
    camera: 'FUJIFILM X-T3',
    lens: 'XF35mmF1.4 R',
    iso: 320,
    shutter: '1/250',
    aperture: 2.8,
    focal_length: 35,
    width: 6240,
    height: 4160,
    rating: i % 6,
    style_id: null,
    has_overrides: false,
    sidecar_jpeg: `${FOLDER}/DSCF${1000 + i}.JPG`,
    image_version: `v${i}`,
    ...overrides,
  }
}

export const photos: Photo[] = [
  makePhoto(1),
  makePhoto(2, { style_id: 'warm-film' }),
  makePhoto(3),
  makePhoto(4, { style_id: 'moody-forest', has_overrides: true, width: 4160, height: 6240 }),
  makePhoto(5),
  makePhoto(6),
]

export const library: LibraryInfo = {
  folder: FOLDER,
  include_subfolders: false,
  photo_count: photos.length,
  suggested_folder: FOLDER,
}

export const emptyLibrary: LibraryInfo = {
  folder: null,
  include_subfolders: false,
  photo_count: 0,
  suggested_folder: 'C:/Users/me/Pictures/2026-08-11',
}

export const folders: LibraryFolder[] = [
  { path: FOLDER, include_subfolders: false, photo_count: photos.length, last_imported_at: '2026-10-07T09:00:00Z' },
  { path: 'C:/Photos/Older', include_subfolders: true, photo_count: 12, last_imported_at: '2026-10-06T09:00:00Z' },
]

export function dirListing(path: string | null): DirListing {
  if (path === null) {
    return { path: null, parent: null, photo_count: 0, entries: [{ name: 'C:', path: 'C:/', photo_count: null }] }
  }
  const parent = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) || null : null
  return {
    path,
    parent,
    photo_count: path.endsWith('day1') ? 12 : 0,
    entries: path.endsWith('day1') ? [] : [{ name: 'day1', path: `${path}/day1`, photo_count: 12 }],
  }
}

function warmAdjustments(): AdjustmentParams {
  const a = neutralAdjustments()
  a.white_balance.temperature = 6200
  a.tone.exposure = 0.15
  a.tone.highlights = -30
  return a
}

export const styleSummaries: StyleSummary[] = [
  {
    id: 'moody-forest',
    name: 'Moody Forest',
    description: 'Dark greens and teal shadows.',
    cover_url: '/api/styles/moody-forest/samples/0/after.jpg',
    updated_at: '2026-08-01T10:00:00Z',
    version: 1,
    photo_count: 0,
    error: null,
  },
  {
    id: 'warm-film',
    name: 'Warm Film',
    description: 'Soft warm analog look.',
    cover_url: '/api/styles/warm-film/samples/0/after.jpg',
    updated_at: '2026-08-02T10:00:00Z',
    version: 2,
    photo_count: 3,
    error: null,
  },
]

const warmValues = { 'tone.exposure': 0.15, 'tone.highlights': -30 }

export const warmFilm: Style = {
  id: 'warm-film',
  name: 'Warm Film',
  description: 'Soft warm analog look.',
  cover_url: '/api/styles/warm-film/samples/0/after.jpg',
  updated_at: '2026-08-02T10:00:00Z',
  photo_count: 3,
  best_for: ['portraits', 'golden hour'],
  avoid_on: ['night scenes'],
  values: warmValues,
  rules: [
    {
      type: 'white_balance',
      rule_version: 1,
      mode: 'fixed',
      temperature_offset: 0,
      tint_offset: 0,
      temperature: 6200,
      tint: 0,
    },
  ],
  test_photo_ids: [],
  samples: [
    {
      photo_id: 'p1',
      caption: 'Sample 1',
      before_url: '/api/styles/warm-film/samples/0/before.jpg',
      after_url: '/api/styles/warm-film/samples/0/after.jpg',
      stale: false,
    },
  ],
  created_at: '2026-07-01T10:00:00Z',
  version: 2,
  change_note: '',
  look_hash: 'abc123',
  samples_stale: false,
  changed_parameters: warmValues,
}

export function photoDetail(photo: Photo): PhotoDetail {
  const styled = photo.style_id === 'warm-film'
  const adjustments = styled ? warmAdjustments() : neutralAdjustments()
  const overridden = photo.has_overrides ? ['tone.exposure'] : []
  if (photo.has_overrides) {
    adjustments.tone.exposure = 0.3
    adjustments.geometry.crop = { left: 0.1, top: 0, right: 0.9, bottom: 1 }
  }
  return {
    photo,
    edit: {
      photo_id: photo.id,
      style_id: photo.style_id,
      adjustments,
      overridden,
      revision: `r${photo.id}`,
      defaults: styled ? warmAdjustments() : neutralAdjustments(), // a reset goes back to the style's values
      unedited: neutralAdjustments(),
      style_values: styled ? ['tone.exposure', 'tone.highlights', 'white_balance.temperature', 'white_balance.tint'] : [],
      rules: styled
        ? [
            {
              type: 'white_balance',
              summary: 'fixed: 6200 K, tint +0.0',
              measured: null,
              target: null,
              values: { 'white_balance.temperature': 6200, 'white_balance.tint': 0 },
              note: null,
            },
          ]
        : [],
      style_version: styled ? 2 : null,
      style_error: null,
      group: null,
    },
    as_shot: { temperature: 5200, tint: 8 },
  }
}

export const presets: ExportPreset[] = [
  {
    id: 'instagram-portrait',
    name: 'Instagram portrait (4:5)',
    description: '1080×1350 feed format.',
    target: 'instagram',
    builtin: true,
    settings: {
      file: { format: 'jpeg', jpeg_quality: 92, max_file_size_kb: null, bit_depth: 8, tiff_compression: 'lzw' },
      color_space: 'srgb',
      size: {
        mode: 'width_height',
        long_edge: null,
        short_edge: null,
        width: 1080,
        height: 1350,
        megapixels: null,
        percentage: null,
        dont_enlarge: false,
        ppi: 72,
      },
      aspect: { ratio: '4:5', orientation: 'portrait', anchor: 'subject' },
      sharpening: { target: 'screen', amount: 'standard' },
      metadata: { policy: 'copyright_only', strip_gps: true, copyright: null, keywords: [] },
      naming: { template: '{original}_ig', on_collision: 'suffix' },
      destination: null,
    },
  },
  {
    id: 'web-full',
    name: 'Web full size',
    description: 'Long edge 2048 px.',
    target: 'web',
    builtin: true,
    settings: {
      file: { format: 'jpeg', jpeg_quality: 85, max_file_size_kb: null, bit_depth: 8, tiff_compression: 'lzw' },
      color_space: 'srgb',
      size: {
        mode: 'long_edge',
        long_edge: 2048,
        short_edge: null,
        width: null,
        height: null,
        megapixels: null,
        percentage: null,
        dont_enlarge: true,
        ppi: 72,
      },
      aspect: { ratio: null, orientation: 'auto', anchor: 'subject' },
      sharpening: { target: 'screen', amount: 'standard' },
      metadata: { policy: 'copyright_only', strip_gps: true, copyright: null, keywords: [] },
      naming: { template: '{original}_web', on_collision: 'suffix' },
      destination: null,
    },
  },
]

export function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: 'j0001',
    kind: 'apply_and_export',
    status: 'done',
    title: 'Apply Warm Film and export 2 photos (Instagram portrait (4:5))',
    created_at: '2026-10-07T10:00:00Z',
    finished_at: '2026-10-07T10:00:01Z',
    progress: 1,
    total: 2,
    completed: 2,
    failed: 0,
    style_id: 'warm-film',
    preset_id: 'instagram-portrait',
    destination: 'C:/Exports/ig',
    folder: null,
    summary: null,
    items: [
      { photo_id: 'p001', filename: 'DSCF1001.RAF', status: 'done', message: null, output_path: 'C:/Exports/ig/DSCF1001.jpg' },
      { photo_id: 'p002', filename: 'DSCF1002.RAF', status: 'done', message: null, output_path: 'C:/Exports/ig/DSCF1002.jpg' },
    ],
    ...overrides,
  }
}

export function makeImportJob(overrides: Partial<Job> = {}): Job {
  return makeJob({
    id: 'j0009',
    kind: 'import',
    title: 'Import 67 photos from Test',
    style_id: null,
    preset_id: null,
    destination: null,
    folder: FOLDER,
    total: 67,
    completed: 67,
    summary: '67 photos: 67 new; 1 other file skipped',
    items: [{ photo_id: 'p001', filename: 'DSCF1001.RAF', status: 'done', message: 'new', output_path: null }],
    ...overrides,
  })
}

export const styleHistory: StyleVersionInfo[] = [
  { version: 2, updated_at: '2026-08-02T10:00:00Z', change_note: 'warmer highlights', look_hash: 'abc123' },
  { version: 1, updated_at: '2026-07-01T10:00:00Z', change_note: 'created', look_hash: 'old111' },
]

export const styleDiff: StyleDiff = {
  style_id: 'warm-film',
  a: 1,
  b: 2,
  values: [{ name: 'tone.highlights', before: -10, after: -30 }],
  rules: [],
  fields: ['description'],
  same_look: false,
}

function measurements(middle: number) {
  return { middle, white: middle + 3, temperature: 5000, tint: 2 }
}

export const styleReport: ConsistencyReport = {
  style_id: 'warm-film',
  look_hash: 'abc123',
  photos: [
    {
      photo_id: 'p001',
      filename: 'DSCF5401.RAF',
      camera_ev: 11,
      before: measurements(-3.5),
      after: measurements(-2.7),
      rules: [{ type: 'exposure', summary: 'middle -3.50 -> target -2.70 stops: +0.80 EV', measured: -3.5, target: -2.7, values: { 'tone.exposure': 0.8 }, note: null }],
      deviation: 0,
    },
    {
      photo_id: 'p002',
      filename: 'DSCF5402.RAF',
      camera_ev: 9,
      before: measurements(-6.2),
      after: measurements(-4.7),
      rules: [{ type: 'exposure', summary: 'middle -6.20 -> target -2.70 stops: +1.50 EV', measured: -6.2, target: -2.7, values: { 'tone.exposure': 1.5 }, note: 'limited to 1.5 EV (wanted +3.50)' }],
      deviation: -2,
    },
  ],
  spread: [
    { measure: 'middle', before_mad: 1.35, after_mad: 1.0, before_range: 2.7, after_range: 2.0 },
    { measure: 'white', before_mad: 1.35, after_mad: 1.0, before_range: 2.7, after_range: 2.0 },
    { measure: 'temperature', before_mad: 0, after_mad: 0, before_range: 0, after_range: 0 },
    { measure: 'tint', before_mad: 0, after_mad: 0, before_range: 0, after_range: 0 },
  ],
}
