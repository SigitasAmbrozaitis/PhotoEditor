import type { FoundCandidate, SubjectBox } from '../api/types'
import { cn } from '../lib/cn'
import { candidateName, candidateText, percent } from './detectionWords'

const boxStyle = (b: SubjectBox) => ({
  left: `${b.left * 100}%`,
  top: `${b.top * 100}%`,
  width: `${(b.right - b.left) * 100}%`,
  height: `${(b.bottom - b.top) * 100}%`,
})

function Tag({ children, tone }: { children: string; tone: 'subject' | 'found' | 'guess' }) {
  return (
    <span
      className={cn(
        'pointer-events-none absolute -top-px left-0 -translate-y-full rounded-t px-1 text-[10px] leading-4 whitespace-nowrap',
        tone === 'subject' && 'bg-amber-400 text-black',
        tone === 'found' && 'bg-sky-300 text-black',
        tone === 'guess' && 'bg-black/70 text-white/80',
      )}
    >
      {children}
    </span>
  )
}

/**
 * What detection found, drawn over a photo (normalized boxes; the parent is `relative` and sized like the
 * photo): every candidate with its name and confidence, the subject, and the camera's focus point. With
 * `onCandidate`, recognized candidates and guesses can be clicked to make them the subject.
 */
export function DetectionOverlay({
  subject,
  subjectLabel,
  manual,
  candidates,
  focus,
  onCandidate,
  disabled = false,
}: {
  subject: SubjectBox | null
  subjectLabel: string
  manual: boolean
  candidates: FoundCandidate[]
  focus: SubjectBox | null
  onCandidate?: (index: number) => void
  disabled?: boolean
}) {
  // The subject is drawn on its own when no candidate stands for it (set by hand, the focus point, a group).
  const subjectShown = candidates.some((c) => c.chosen && subject && sameBox(c.box, subject))
  return (
    <div className="pointer-events-none absolute inset-0" data-testid="detection-overlay">
      {focus && (
        <div className="absolute border border-dashed border-white/80" style={boxStyle(focus)} data-testid="focus-point">
          <span className="absolute top-1/2 left-1/2 size-1.5 -translate-1/2 rounded-full bg-white" />
        </div>
      )}
      {[...candidates].reverse().map((c) => {
        const tone = c.chosen ? 'subject' : c.recognized ? 'found' : 'guess'
        const className = cn(
          'absolute border-2',
          tone === 'subject' && 'border-amber-400',
          tone === 'found' && 'border-dashed border-sky-300',
          tone === 'guess' && 'border-dotted border-white/50',
        )
        const text = candidateText(c)
        return onCandidate ? (
          <button
            key={c.index}
            type="button"
            disabled={disabled}
            aria-label={`Use the ${candidateName(c)} (${percent(c.score)})`}
            aria-pressed={c.chosen}
            onClick={() => onCandidate(c.index)}
            className={cn(className, 'pointer-events-auto hover:bg-white/10 disabled:cursor-not-allowed')}
            style={boxStyle(c.box)}
          >
            <Tag tone={tone}>{text}</Tag>
          </button>
        ) : (
          <div key={c.index} className={className} style={boxStyle(c.box)} data-testid="found-candidate">
            <Tag tone={tone}>{text}</Tag>
          </div>
        )
      })}
      {subject && !subjectShown && (
        <div className="absolute border-2 border-amber-400" style={boxStyle(subject)} data-testid="overlay-subject">
          <Tag tone="subject">{manual ? 'subject: set by hand' : `subject: ${subjectLabel}`}</Tag>
        </div>
      )}
    </div>
  )
}

function sameBox(a: SubjectBox, b: SubjectBox): boolean {
  const near = (x: number, y: number) => Math.abs(x - y) < 1e-6
  return near(a.left, b.left) && near(a.top, b.top) && near(a.right, b.right) && near(a.bottom, b.bottom)
}
