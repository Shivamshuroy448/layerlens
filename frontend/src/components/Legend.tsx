import type { LayerFamily } from '../types'
import { FAMILY_COLORS } from '../scene/layout'

const ORDER: LayerFamily[] = ['input', 'convolution', 'activation', 'pooling', 'reshape', 'linear', 'attention', 'normalization', 'recurrent', 'output', 'other']

export function Legend({ families }: { families?: LayerFamily[] }) {
  const shown = families ? ORDER.filter((f) => families.includes(f)) : ORDER.slice(0, 7)
  return (
    <div className="legend">
      {shown.map((f) => (
        <span key={f} className="legend-item">
          <span className="swatch" style={{ background: FAMILY_COLORS[f] }} />
          {f}
        </span>
      ))}
    </div>
  )
}
