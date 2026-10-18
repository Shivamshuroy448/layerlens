import type { GraphNode } from '../types'
import { docFor } from '../knowledge'
import { FAMILY_COLORS } from '../scene/layout'
import { useLens } from '../store'

const fmtShape = (s: number[] | null) => (s ? `[${s.join(', ')}]` : '—')
const fmtParams = (p: number) =>
  p === 0 ? '0' : p >= 1000 ? `${p.toLocaleString()} (${(p / 1000).toFixed(1)}k)` : `${p}`

function AttrTable({ node }: { node: GraphNode }) {
  const entries = Object.entries(node.attrs)
  if (entries.length === 0) return null
  return (
    <table className="attr-table">
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k}>
            <td className="k">{k}</td>
            <td>{Array.isArray(v) ? `[${v.join(', ')}]` : String(v)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function LayerInspector() {
  const { graph, selectedId, select } = useLens()
  const node = graph?.nodes.find((n) => n.id === selectedId)

  if (!graph) return null

  if (!node) {
    return (
      <aside className="inspector inspector-empty">
        <h2>Inspector</h2>
        <p className="hint">
          Select any block in the scene to inspect it — operation, tensor
          shapes, and parameter count.
        </p>
        <p className="hint dim">Drag to orbit · Scroll to zoom · Right-drag to pan</p>
      </aside>
    )
  }

  const doc = docFor(node.label, node.op)
  const color = FAMILY_COLORS[node.family]

  return (
    <aside className="inspector">
      <button className="close" onClick={() => select(null)} aria-label="Deselect">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" aria-hidden>
          <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" />
        </svg>
      </button>
      <div className="family-tag" style={{ background: color }}>
        {node.family}
      </div>
      <h2>{node.label}</h2>
      <p className="op">op: {node.op}</p>

      {doc && (
        <>
          <p className="tagline">{doc.tagline}</p>
          <p>{doc.how}</p>
          {doc.watchOut && (
            <p className="watch">
              <span className="watch-label">Watch out</span>
              {doc.watchOut}
            </p>
          )}
        </>
      )}

      <h3>This instance</h3>
      <table className="attr-table">
        <tbody>
          <tr>
            <td className="k">parameters</td>
            <td>{fmtParams(node.params)}</td>
          </tr>
          <tr>
            <td className="k">input</td>
            <td>{fmtShape(node.in_shape)}</td>
          </tr>
          <tr>
            <td className="k">output</td>
            <td>{fmtShape(node.out_shape)}</td>
          </tr>
        </tbody>
      </table>
      <AttrTable node={node} />
    </aside>
  )
}
