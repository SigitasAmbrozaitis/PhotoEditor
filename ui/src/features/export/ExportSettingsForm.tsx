import { useState, type ReactNode } from 'react'
import type {
  CollisionPolicy,
  ColorSpace,
  CropAnchor,
  DecodeSize,
  ExportSettings,
  FileFormat,
  MetadataPolicy,
  Orientation,
  ResizeMode,
  SharpenAmount,
  SharpenFor,
  TiffCompression,
} from '../../api/types'
import { Field, Select, Switch, TextInput } from '../../components/ui'
import { COLOR_SPACE_LABELS, FORMAT_LABELS, RESIZE_LABELS } from './exportSummary'

const ASPECTS = ['', '1:1', '4:5', '5:4', '1.91:1', '9:16', '16:9', '2:3', '3:2', '4:3', '5:7', '7:5', '1.414:1']
const SHARPEN_FOR: Record<SharpenFor, string> = {
  none: 'None',
  screen: 'Screen',
  matte_paper: 'Matte paper',
  glossy_paper: 'Glossy paper',
}
const METADATA: Record<MetadataPolicy, string> = {
  all: 'All metadata',
  copyright_only: 'Copyright only',
  copyright_and_contact: 'Copyright & contact info',
  all_except_camera_and_gps: 'All except camera & location info',
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="rounded border border-line p-3">
      <legend className="px-1 text-xs font-semibold text-strong">{title}</legend>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">{children}</div>
    </fieldset>
  )
}

function num(value: string): number | null {
  if (value.trim() === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/** A number that can't be empty: while the field is cleared, the setting keeps its last value. */
function RequiredNumberInput({
  value,
  onChange,
  ...props
}: { value: number; onChange: (value: number) => void; min?: number; max?: number; disabled?: boolean }) {
  const [text, setText] = useState(String(value))
  const shown = text.trim() === '' || num(text) === value ? text : String(value)
  return (
    <TextInput
      type="number"
      {...props}
      value={shown}
      onChange={(e) => {
        setText(e.target.value)
        const n = num(e.target.value)
        if (n !== null) onChange(n)
      }}
    />
  )
}

const parseKeywords = (text: string) =>
  text
    .split(',')
    .map((k) => k.trim())
    .filter(Boolean)

/** Keeps what's typed (e.g. a trailing comma) while the settings hold the parsed list. */
function KeywordsInput({
  keywords,
  disabled,
  onChange,
}: {
  keywords: string[]
  disabled: boolean
  onChange: (keywords: string[]) => void
}) {
  const [text, setText] = useState(keywords.join(', '))
  // Another preset was chosen: show its keywords.
  const shown = JSON.stringify(parseKeywords(text)) === JSON.stringify(keywords) ? text : keywords.join(', ')
  return (
    <TextInput
      value={shown}
      placeholder="rally, Lithuania"
      disabled={disabled}
      aria-label="Keywords"
      onChange={(e) => {
        setText(e.target.value)
        onChange(parseKeywords(e.target.value))
      }}
    />
  )
}

/** Controlled editor for every export setting (PLAN.md 4.6). */
export function ExportSettingsForm({
  value,
  onChange,
  disabled = false,
}: {
  value: ExportSettings
  onChange: (next: ExportSettings) => void
  disabled?: boolean
}) {
  const set = <K extends keyof ExportSettings>(key: K, patch: Partial<ExportSettings[K]>) => {
    const current = value[key]
    const next = typeof current === 'object' && current !== null ? { ...current, ...patch } : patch
    onChange({ ...value, [key]: next })
  }
  const { file, size, aspect, sharpening, metadata, naming } = value

  return (
    <div className="flex flex-col gap-4">
      <Section title="File">
        <Field label="Format">
          <Select
            value={file.format}
            disabled={disabled}
            onChange={(e) => {
              const format = e.target.value as FileFormat
              set('file', {
                format,
                bit_depth: format === 'jpeg' ? 8 : file.bit_depth,
                max_file_size_kb: format === 'jpeg' ? file.max_file_size_kb : null,
              })
            }}
          >
            {Object.entries(FORMAT_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        {file.format === 'jpeg' ? (
          <>
            <Field label="Quality" hint="1–100">
              <RequiredNumberInput
                min={1}
                max={100}
                value={file.jpeg_quality}
                disabled={disabled}
                onChange={(jpeg_quality) => set('file', { jpeg_quality })}
              />
            </Field>
            <Field label="Limit file size (KB)" hint="Empty = no limit">
              <TextInput
                type="number"
                min={50}
                value={file.max_file_size_kb ?? ''}
                disabled={disabled}
                onChange={(e) => set('file', { max_file_size_kb: num(e.target.value) })}
              />
            </Field>
          </>
        ) : (
          <>
            <Field label="Bit depth">
              <Select
                value={file.bit_depth}
                disabled={disabled}
                onChange={(e) => set('file', { bit_depth: Number(e.target.value) })}
              >
                <option value={8}>8-bit</option>
                <option value={16}>16-bit</option>
              </Select>
            </Field>
            {file.format === 'tiff' && (
              <Field label="Compression">
                <Select
                  value={file.tiff_compression}
                  disabled={disabled}
                  onChange={(e) => set('file', { tiff_compression: e.target.value as TiffCompression })}
                >
                  <option value="none">None</option>
                  <option value="lzw">LZW</option>
                  <option value="zip">ZIP</option>
                </Select>
              </Field>
            )}
          </>
        )}
        <Field label="Color space">
          <Select
            value={value.color_space}
            disabled={disabled}
            onChange={(e) => onChange({ ...value, color_space: e.target.value as ColorSpace })}
          >
            {Object.entries(COLOR_SPACE_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="RAW decode" hint="Half size is ~10× faster and enough for screen sizes">
          <Select
            value={file.decode}
            disabled={disabled}
            onChange={(e) => set('file', { decode: e.target.value as DecodeSize })}
          >
            <option value="auto">Automatic</option>
            <option value="full">Always full size</option>
          </Select>
        </Field>
      </Section>

      <Section title="Image size">
        <Field label="Resize">
          <Select
            value={size.mode}
            disabled={disabled}
            onChange={(e) => set('size', { mode: e.target.value as ResizeMode })}
          >
            {Object.entries(RESIZE_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        {size.mode === 'long_edge' && (
          <Field label="Long edge (px)">
            <TextInput
              type="number"
              value={size.long_edge ?? ''}
              disabled={disabled}
              onChange={(e) => set('size', { long_edge: num(e.target.value) })}
            />
          </Field>
        )}
        {size.mode === 'short_edge' && (
          <Field label="Short edge (px)">
            <TextInput
              type="number"
              value={size.short_edge ?? ''}
              disabled={disabled}
              onChange={(e) => set('size', { short_edge: num(e.target.value) })}
            />
          </Field>
        )}
        {size.mode === 'width_height' && (
          <>
            <Field label="Width (px)">
              <TextInput
                type="number"
                value={size.width ?? ''}
                disabled={disabled}
                onChange={(e) => set('size', { width: num(e.target.value) })}
              />
            </Field>
            <Field label="Height (px)">
              <TextInput
                type="number"
                value={size.height ?? ''}
                disabled={disabled}
                onChange={(e) => set('size', { height: num(e.target.value) })}
              />
            </Field>
          </>
        )}
        {size.mode === 'megapixels' && (
          <Field label="Megapixels">
            <TextInput
              type="number"
              step="0.1"
              value={size.megapixels ?? ''}
              disabled={disabled}
              onChange={(e) => set('size', { megapixels: num(e.target.value) })}
            />
          </Field>
        )}
        {size.mode === 'percentage' && (
          <Field label="Percentage">
            <TextInput
              type="number"
              value={size.percentage ?? ''}
              disabled={disabled}
              onChange={(e) => set('size', { percentage: num(e.target.value) })}
            />
          </Field>
        )}
        <Field label="Resolution (PPI)">
          <RequiredNumberInput
            min={1}
            value={size.ppi}
            disabled={disabled}
            onChange={(ppi) => set('size', { ppi })}
          />
        </Field>
        <div className="flex items-end pb-1.5">
          <Switch
            label="Don't enlarge"
            checked={size.dont_enlarge}
            disabled={disabled}
            onCheckedChange={(v) => set('size', { dont_enlarge: v })}
          />
        </div>
      </Section>

      <Section title="Aspect & orientation">
        <Field label="Crop to aspect">
          <Select
            value={aspect.ratio ?? ''}
            disabled={disabled}
            onChange={(e) => set('aspect', { ratio: e.target.value || null })}
          >
            {ASPECTS.map((a) => (
              <option key={a} value={a}>
                {a || 'Keep original'}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Orientation">
          <Select
            value={aspect.orientation}
            disabled={disabled}
            onChange={(e) => set('aspect', { orientation: e.target.value as Orientation })}
          >
            <option value="auto">Follow photo</option>
            <option value="portrait">Force portrait</option>
            <option value="landscape">Force landscape</option>
          </Select>
        </Field>
        <Field label="Center crop on">
          <Select
            value={aspect.anchor}
            disabled={disabled || !aspect.ratio}
            onChange={(e) => set('aspect', { anchor: e.target.value as CropAnchor })}
          >
            <option value="center">Image center</option>
            <option value="subject" disabled>
              Detected subject (Phase 6)
            </option>
          </Select>
        </Field>
      </Section>

      <Section title="Output sharpening">
        <Field label="Sharpen for">
          <Select
            value={sharpening.target}
            disabled={disabled}
            onChange={(e) => set('sharpening', { target: e.target.value as SharpenFor })}
          >
            {Object.entries(SHARPEN_FOR).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Amount">
          <Select
            value={sharpening.amount}
            disabled={disabled || sharpening.target === 'none'}
            onChange={(e) => set('sharpening', { amount: e.target.value as SharpenAmount })}
          >
            <option value="low">Low</option>
            <option value="standard">Standard</option>
            <option value="high">High</option>
          </Select>
        </Field>
      </Section>

      <Section title="Metadata">
        <Field label="Include">
          <Select
            value={metadata.policy}
            disabled={disabled}
            onChange={(e) => {
              const policy = e.target.value as MetadataPolicy
              // Only "All metadata" can carry GPS at all.
              set('metadata', { policy, strip_gps: policy === 'all' ? metadata.strip_gps : true })
            }}
          >
            {Object.entries(METADATA).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Copyright" hint="{year} = capture year. Empty = your default">
          <TextInput
            value={metadata.copyright ?? ''}
            placeholder="© {year} Your Name"
            disabled={disabled}
            onChange={(e) => set('metadata', { copyright: e.target.value || null })}
          />
        </Field>
        {metadata.policy !== 'copyright_only' && (
          <Field label="Creator" hint="Empty = your default">
            <TextInput
              value={metadata.creator ?? ''}
              placeholder="Your Name"
              disabled={disabled}
              onChange={(e) => set('metadata', { creator: e.target.value || null })}
            />
          </Field>
        )}
        <Field label="Keywords" hint="Comma-separated" className="col-span-2">
          <KeywordsInput
            keywords={metadata.keywords}
            disabled={disabled}
            onChange={(keywords) => set('metadata', { keywords })}
          />
        </Field>
        <div className="flex items-end pb-1.5">
          <Switch
            label="Remove location (GPS)"
            checked={metadata.strip_gps}
            disabled={disabled || metadata.policy !== 'all'}
            onCheckedChange={(v) => set('metadata', { strip_gps: v })}
          />
        </div>
      </Section>

      <Section title="File naming">
        <Field label="Name template" hint="{original} {date} {time} {seq} {seq:03} {style} {preset} {camera}" className="col-span-2">
          <TextInput
            value={naming.template}
            disabled={disabled}
            onChange={(e) => set('naming', { template: e.target.value })}
          />
        </Field>
        <Field label="If file exists">
          <Select
            value={naming.on_collision}
            disabled={disabled}
            onChange={(e) => set('naming', { on_collision: e.target.value as CollisionPolicy })}
          >
            <option value="suffix">Add a number</option>
            <option value="overwrite">Overwrite</option>
            <option value="skip">Skip</option>
          </Select>
        </Field>
      </Section>
    </div>
  )
}
