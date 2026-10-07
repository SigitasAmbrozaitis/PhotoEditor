import type { ColorSpace, ExportSettings, FileFormat, ResizeMode } from '../../api/types'

export const COLOR_SPACE_LABELS: Record<ColorSpace, string> = {
  srgb: 'sRGB',
  display_p3: 'Display P3',
  adobe_rgb: 'Adobe RGB',
}

export const FORMAT_LABELS: Record<FileFormat, string> = { jpeg: 'JPEG', tiff: 'TIFF', png: 'PNG' }

export const RESIZE_LABELS: Record<ResizeMode, string> = {
  original: 'Original size',
  long_edge: 'Long edge',
  short_edge: 'Short edge',
  width_height: 'Width × height',
  megapixels: 'Megapixels',
  percentage: 'Percentage',
}

export function describeSize(settings: ExportSettings): string {
  const s = settings.size
  switch (s.mode) {
    case 'original':
      return 'original size'
    case 'long_edge':
      return `long edge ${s.long_edge ?? '?'} px`
    case 'short_edge':
      return `short edge ${s.short_edge ?? '?'} px`
    case 'width_height':
      return `${s.width ?? '?'}×${s.height ?? '?'}`
    case 'megapixels':
      return `${s.megapixels ?? '?'} MP`
    case 'percentage':
      return `${s.percentage ?? '?'}%`
  }
}

export function describeFile(settings: ExportSettings): string {
  const f = settings.file
  if (f.format === 'jpeg') return `JPEG q${f.jpeg_quality}${f.max_file_size_kb ? ` ≤${f.max_file_size_kb} KB` : ''}`
  return `${FORMAT_LABELS[f.format]} ${f.bit_depth}-bit`
}

/** One-line human summary, e.g. "1080×1350 · 4:5 crop · JPEG q92 · sRGB → C:/Exports". */
export function exportSummary(settings: ExportSettings, destination?: string | null): string {
  const parts = [describeSize(settings)]
  if (settings.aspect.ratio) parts.push(`${settings.aspect.ratio} crop`)
  parts.push(describeFile(settings), COLOR_SPACE_LABELS[settings.color_space])
  const dest = destination?.trim() ? destination.trim() : '(choose a folder)'
  return `${parts.join(' · ')} → ${dest}`
}
