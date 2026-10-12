/** Two lines each way at the thirds, over whatever box contains it. */
export function ThirdsGrid({ className = '' }: { className?: string }) {
  return (
    <div className={`pointer-events-none absolute inset-0 ${className}`} data-testid="thirds-grid" aria-hidden>
      {[1, 2].map((i) => (
        <div key={i}>
          <div className="absolute top-0 bottom-0 w-px bg-white/50 shadow-[0_0_1px_rgba(0,0,0,0.8)]" style={{ left: `${(i * 100) / 3}%` }} />
          <div className="absolute right-0 left-0 h-px bg-white/50 shadow-[0_0_1px_rgba(0,0,0,0.8)]" style={{ top: `${(i * 100) / 3}%` }} />
        </div>
      ))}
    </div>
  )
}
