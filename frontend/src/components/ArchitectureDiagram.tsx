import { useMemo, useState } from 'react'
import type { AnalyzeTreeNode } from '../types'
import { familyFor, formatParams } from '../analysis'
import { FAMILY_COLORS } from '../scene/layout'

const NODE_W = 208
const NODE_H = 50
const H_GAP = 30
const V_GAP = 66

interface Placed {
  node: AnalyzeTreeNode
  x: number
  y: number
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

/** Git-graph-style flow diagram of the module hierarchy (top-down, elbow edges). */
export function ArchitectureDiagram({ tree }: { tree: AnalyzeTreeNode[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const s = new Set<string>()
    const walk = (n: AnalyzeTreeNode) => {
      if (n.depth < 2 && n.children.length > 0) s.add(n.id)
      for (const c of n.children) walk(c)
    }
    tree.forEach(walk)
    return s
  })

  const { placed, edges, width, height } = useMemo(() => {
    const placed: Placed[] = []
    const edges: [Placed, Placed][] = []
    let leaf = 0
    let maxDepth = 0
    const visit = (node: AnalyzeTreeNode, depth: number): Placed => {
      maxDepth = Math.max(maxDepth, depth)
      const kids = expanded.has(node.id) ? node.children : []
      const p: Placed = { node, x: 0, y: depth * (NODE_H + V_GAP) }
      placed.push(p)
      if (kids.length === 0) {
        p.x = leaf * (NODE_W + H_GAP)
        leaf += 1
      } else {
        const cps = kids.map((k) => visit(k, depth + 1))
        p.x = (cps[0].x + cps[cps.length - 1].x) / 2
        for (const c of cps) edges.push([p, c])
      }
      return p
    }
    tree.forEach((r) => visit(r, 0))
    return {
      placed,
      edges,
      width: Math.max(1, leaf) * (NODE_W + H_GAP),
      height: maxDepth * (NODE_H + V_GAP) + NODE_H + 28,
    }
  }, [tree, expanded])

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const edgePath = (a: Placed, b: Placed) => {
    const x1 = a.x + NODE_W / 2
    const y1 = a.y + NODE_H
    const x2 = b.x + NODE_W / 2
    const y2 = b.y
    const mid = (y1 + y2) / 2
    return `M ${x1} ${y1} V ${mid} H ${x2} V ${y2}`
  }

  return (
    <div className="arch-diagram-scroll">
      <svg
        className="arch-diagram"
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Architecture flow diagram"
      >
        {edges.map(([a, b], i) => (
          <path key={`${a.node.id}-${b.node.id}-${i}`} d={edgePath(a, b)} className="arch-edge" />
        ))}
        {placed.map((p) => {
          const color = FAMILY_COLORS[familyFor(p.node.type)]
          const hasKids = p.node.children.length > 0
          const isOpen = expanded.has(p.node.id)
          return (
            <g
              key={p.node.id}
              className={`arch-node${hasKids ? ' clickable' : ''}`}
              onClick={() => hasKids && toggle(p.node.id)}
            >
              <title>
                {p.node.value != null
                  ? `${p.node.name} = ${p.node.value}`
                  : `${p.node.name} · ${p.node.type} · ${formatParams(p.node.params)} params`}
              </title>
              <rect
                x={p.x}
                y={p.y}
                width={NODE_W}
                height={NODE_H}
                rx={10}
                className="arch-node-box"
                style={{ stroke: color }}
              />
              <rect x={p.x} y={p.y} width={5} height={NODE_H} rx={2.5} fill={color} />
              <text x={p.x + 15} y={p.y + 21} className="arch-node-name">
                {truncate(p.node.name, 24)}
              </text>
              <text x={p.x + 15} y={p.y + 38} className="arch-node-type">
                {p.node.value != null
                  ? truncate(`= ${p.node.value}`, 28)
                  : truncate(p.node.type, 28)}
              </text>
              <text x={p.x + NODE_W - 10} y={p.y + 38} textAnchor="end" className="arch-node-params">
                {p.node.value != null ? '' : formatParams(p.node.params)}
              </text>
              {hasKids && (
                <text x={p.x + NODE_W - 10} y={p.y + 20} textAnchor="end" className="arch-node-caret">
                  {isOpen ? '▾' : '▸'}
                </text>
              )}
              {p.node.child_count > 0 && !isOpen && (
                <text x={p.x + NODE_W / 2} y={p.y + NODE_H + 16} textAnchor="middle" className="arch-node-folded">
                  +{p.node.child_count} folded
                </text>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
