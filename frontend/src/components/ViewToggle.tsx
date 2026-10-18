import { useLens, type ViewMode } from '../store'

const TABS: { id: ViewMode; label: string }[] = [
  { id: 'arch', label: 'Architecture' },
  { id: 'model3d', label: '3D Model' },
]

/** Fixed top-middle segmented control — persists across the session. */
export function ViewToggle() {
  const { view, setView, analysis } = useLens()
  const resolved = analysis?.resolved ?? true
  return (
    <div className="view-toggle" role="tablist" aria-label="View">
      {TABS.map((t) => {
        const disabled = t.id === 'model3d' && !resolved
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={view === t.id}
            className={view === t.id ? 'active' : ''}
            disabled={disabled}
            title={disabled ? '3D view needs a resolved layer graph' : undefined}
            onClick={() => !disabled && setView(t.id)}
          >
            {t.label}
          </button>
        )
      })}
    </div>
  )
}
