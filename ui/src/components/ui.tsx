/** Small shared building blocks. Styling lives here so screens stay consistent. */
import { CircleAlert, LoaderCircle, Star, X } from 'lucide-react'
import { Dialog as RadixDialog, Switch as RadixSwitch, Tooltip as RadixTooltip } from 'radix-ui'
import { cn } from '../lib/cn'
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'

// ----------------------------------------------------------------- buttons

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-white hover:bg-accent-strong disabled:bg-raised disabled:text-muted',
  secondary: 'bg-raised text-fg border border-line hover:bg-hover disabled:text-muted',
  ghost: 'text-fg hover:bg-hover disabled:text-muted',
  danger: 'bg-err/90 text-white hover:bg-err disabled:bg-raised disabled:text-muted',
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' }) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded font-medium whitespace-nowrap transition-colors',
        'disabled:cursor-not-allowed',
        size === 'sm' ? 'h-7 px-2 text-xs' : 'h-8 px-3 text-[13px]',
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  )
}

// ----------------------------------------------------------------- feedback

export function Spinner({ className, label = 'Loading' }: { className?: string; label?: string }) {
  return <LoaderCircle aria-label={label} role="status" className={cn('size-4 animate-spin text-muted', className)} />
}

export function ProgressBar({ value, className, label }: { value: number; className?: string; label?: string }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      className={cn('h-1.5 w-full overflow-hidden rounded-full bg-raised', className)}
    >
      <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${pct}%` }} />
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 p-10 text-center text-muted">
      <p className="text-sm font-medium text-fg">{title}</p>
      {children}
    </div>
  )
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div role="alert" className="m-4 flex items-start gap-2 rounded border border-err/50 bg-err/10 p-3 text-sm">
      <CircleAlert className="mt-0.5 size-4 shrink-0 text-err" />
      <div>
        <p className="font-medium text-strong">Could not load data</p>
        <p className="text-muted">{message}</p>
      </div>
    </div>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-6 text-muted">
      <Spinner />
      <span>{label}</span>
    </div>
  )
}

export function Stars({ rating, className }: { rating: number; className?: string }) {
  return (
    <span className={cn('inline-flex', className)} aria-label={`${rating} of 5 stars`} title={`${rating} of 5 stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Star key={n} className={cn('size-3', n <= rating ? 'fill-warn text-warn' : 'text-line')} aria-hidden />
      ))}
    </span>
  )
}

const CHIP_TONES = {
  neutral: 'bg-raised text-fg',
  ok: 'bg-ok/15 text-ok',
  warn: 'bg-warn/15 text-warn',
  err: 'bg-err/15 text-err',
  overlay: 'bg-black/70 text-white backdrop-blur-sm',
} as const

export function Chip({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode
  tone?: keyof typeof CHIP_TONES
  className?: string
}) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[11px]', CHIP_TONES[tone], className)}>
      {children}
    </span>
  )
}

// ----------------------------------------------------------------- form controls

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string
  hint?: string
  children: ReactNode
  className?: string
}) {
  return (
    <label className={cn('flex flex-col gap-1', className)}>
      <span className="text-[11px] font-medium tracking-wide text-muted uppercase">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-muted">{hint}</span>}
    </label>
  )
}

const controlClass =
  'h-8 rounded border border-line bg-bg px-2 text-[13px] text-fg disabled:text-muted disabled:opacity-70 ' +
  'focus:border-accent focus:outline-none'

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(controlClass, 'pr-6', className)} {...props} />
}

export function TextInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(controlClass, className)} {...props} />
}

export function TextArea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(controlClass, 'h-auto min-h-16 py-1.5 leading-relaxed', className)} {...props} />
}

export function Switch({
  checked,
  onCheckedChange,
  label,
  disabled,
}: {
  checked: boolean
  onCheckedChange: (value: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-[13px]">
      <RadixSwitch.Root
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-label={label}
        className="relative h-4.5 w-8 rounded-full bg-line transition-colors data-[state=checked]:bg-accent"
      >
        <RadixSwitch.Thumb className="block size-3.5 translate-x-0.5 rounded-full bg-white transition-transform data-[state=checked]:translate-x-4" />
      </RadixSwitch.Root>
      <span>{label}</span>
    </label>
  )
}

// ----------------------------------------------------------------- overlays

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <RadixTooltip.Root delayDuration={300}>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          sideOffset={6}
          className="z-50 max-w-xs rounded border border-line bg-raised px-2 py-1 text-xs text-fg shadow-lg"
        >
          {content}
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  )
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  width = 'max-w-2xl',
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  width?: string
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <RadixDialog.Content
          className={cn(
            'fixed top-1/2 left-1/2 z-50 flex max-h-[90vh] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2',
            'flex-col rounded-lg border border-line bg-panel shadow-2xl',
            width,
          )}
        >
          <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-3">
            <div>
              <RadixDialog.Title className="text-base font-semibold text-strong">{title}</RadixDialog.Title>
              {description ? (
                <RadixDialog.Description className="text-xs text-muted">{description}</RadixDialog.Description>
              ) : (
                <RadixDialog.Description className="sr-only">{title}</RadixDialog.Description>
              )}
            </div>
            <RadixDialog.Close asChild>
              <button type="button" aria-label="Close" className="rounded p-1 text-muted hover:bg-hover hover:text-fg">
                <X className="size-4" />
              </button>
            </RadixDialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
          {footer && <div className="flex items-center justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-panel px-4 py-2.5">
      <div className="min-w-0">
        <h1 className="text-base font-semibold text-strong">{title}</h1>
        {subtitle && <div className="truncate text-xs text-muted">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
