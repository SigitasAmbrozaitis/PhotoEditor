/** Typed test data. Shapes are checked against the generated API schema by the TypeScript compiler. */
import type {
  AdjustmentParams,
  ExportPreset,
  Job,
  LibraryInfo,
  Photo,
  PhotoDetail,
  Style,
  StyleSummary,
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

export const library: LibraryInfo = { folder: FOLDER, photo_count: photos.length }

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
  },
  {
    id: 'warm-film',
    name: 'Warm Film',
    description: 'Soft warm analog look.',
    cover_url: '/api/styles/warm-film/samples/0/after.jpg',
    updated_at: '2026-08-02T10:00:00Z',
  },
]

export const warmFilm: Style = {
  ...styleSummaries[1]!,
  best_for: ['portraits', 'golden hour'],
  avoid_on: ['night scenes'],
  adjustments: warmAdjustments(),
  samples: [
    {
      caption: 'Sample 1',
      before_url: '/api/styles/warm-film/samples/0/before.jpg',
      after_url: '/api/styles/warm-film/samples/0/after.jpg',
    },
  ],
  created_at: '2026-07-01T10:00:00Z',
  version: 2,
  changed_parameters: { 'white_balance.temperature': 6200, 'tone.exposure': 0.15, 'tone.highlights': -30 },
}

export function photoDetail(photo: Photo): PhotoDetail {
  const adjustments = photo.style_id === 'warm-film' ? warmAdjustments() : neutralAdjustments()
  const overridden = photo.has_overrides ? ['tone.exposure'] : []
  if (photo.has_overrides) {
    adjustments.tone.exposure = 0.3
    adjustments.geometry.crop = { left: 0.1, top: 0, right: 0.9, bottom: 1 }
  }
  return { photo, edit: { photo_id: photo.id, style_id: photo.style_id, adjustments, overridden } }
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
    items: [
      { photo_id: 'p001', filename: 'DSCF1001.RAF', status: 'done', message: null, output_path: 'C:/Exports/ig/DSCF1001.jpg' },
      { photo_id: 'p002', filename: 'DSCF1002.RAF', status: 'done', message: null, output_path: 'C:/Exports/ig/DSCF1002.jpg' },
    ],
    ...overrides,
  }
}
