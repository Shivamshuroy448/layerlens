/** Sequential 3D layout: maps each layer node to a position + box size.
 *
 *  Box cross-section reflects tensor dims so you can *see* the data shrink:
 *  - 4D [N, C, H, W] -> width ~ W, height ~ H, depth ~ C
 *  - 2D [N, F]       -> flat slab sized by sqrt(F)
 *  M4 replaces this with a Sugiyama-style layered layout for branching nets.
 */
import type { GraphEdge, GraphNode, LayerFamily, ModelGraph } from '../types'

export const FAMILY_COLORS: Record<LayerFamily, string> = {
  input: '#9aa3b2',
  convolution: '#d9a13b',
  linear: '#a07fd4',
  activation: '#57b47e',
  pooling: '#5f93d6',
  normalization: '#45b3ab',
  reshape: '#c9b458',
  recurrent: '#d47ba4',
  attention: '#ff6a2b',
  output: '#e0655a',
  other: '#697284',
}

export interface PlacedNode {
  node: GraphNode
  position: [number, number, number]
  size: [number, number, number]
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

function boxSize(node: GraphNode): [number, number, number] {
  const shape = node.out_shape ?? node.in_shape
  if (shape && shape.length === 4) {
    const [, c, h, w] = shape // [N, C, H, W]
    return [clamp(w / 7, 0.6, 5), clamp(h / 7, 0.6, 5), clamp(c / 3.5, 0.6, 5)]
  }
  if (shape && shape.length === 2) {
    const f = shape[1]
    const s = clamp(Math.sqrt(f) / 3.2, 0.8, 4.2)
    return [s, 0.7, 0.7]
  }
  return [1, 1, 1]
}

const GAP = 2.2

export function layoutSequential(graph: ModelGraph): PlacedNode[] {
  const placed: PlacedNode[] = []
  let x = 0
  for (const node of graph.nodes) {
    const size = boxSize(node)
    placed.push({ node, position: [x + size[0] / 2, 0, 0], size })
    x += size[0] + GAP
  }
  // center the row on the origin
  const total = x - GAP
  return placed.map((p) => ({
    ...p,
    position: [p.position[0] - total / 2, 0, 0] as [number, number, number],
  }))
}

export function totalParams(graph: ModelGraph): number {
  return graph.nodes.reduce((s, n) => s + n.params, 0)
}

/** Serpentine grid layout for real HF graphs (tens–hundreds of modules).
 *  Nodes snake row by row; box size grows with log(parameter count). */
export function layoutSerpentine(graph: ModelGraph): PlacedNode[] {
  const n = graph.nodes.length
  const cols = Math.max(4, Math.ceil(Math.sqrt(n * 1.5)))
  const rows = Math.ceil(n / cols)
  const gapX = 3.6
  const gapZ = 3.2
  return graph.nodes.map((node, i) => {
    const row = Math.floor(i / cols)
    let col = i % cols
    if (row % 2 === 1) col = cols - 1 - col // snake back
    const s = paramBox(node.params)
    return {
      node,
      position: [(col - (cols - 1) / 2) * gapX, 0, (row - (rows - 1) / 2) * gapZ] as [
        number,
        number,
        number,
      ],
      size: [s * 1.7, s * 0.85, s * 0.85] as [number, number, number],
    }
  })
}

function paramBox(params: number): number {
  return clamp(0.55 + Math.log10(params + 1) * 0.38, 0.7, 2.4)
}

/** Max horizontal extent of the placed graph — drives camera + fog framing. */
export function sceneRadius(placed: PlacedNode[]): number {
  let r = 0
  for (const p of placed) {
    r = Math.max(
      r,
      Math.hypot(p.position[0], p.position[2]) + Math.max(p.size[0], p.size[2]),
    )
  }
  return Math.max(r, 12)
}

export interface EdgeSeg {
  a: [number, number, number]
  b: [number, number, number]
}

/** Edge segments anchored at each box's surface along the a→b direction —
 *  works for the row layout and the serpentine grid alike. */
export function edgeSegments(placed: PlacedNode[], edges: GraphEdge[]): EdgeSeg[] {
  const byId = new Map(placed.map((p) => [p.node.id, p]))
  const segs: EdgeSeg[] = []
  for (const e of edges) {
    const a = byId.get(e.source)
    const b = byId.get(e.target)
    if (!a || !b) continue
    const dx = b.position[0] - a.position[0]
    const dz = b.position[2] - a.position[2]
    const len = Math.hypot(dx, dz) || 1
    const ux = dx / len
    const uz = dz / len
    const ra = (Math.abs(ux) * a.size[0] + Math.abs(uz) * a.size[2]) / 2
    const rb = (Math.abs(ux) * b.size[0] + Math.abs(uz) * b.size[2]) / 2
    segs.push({
      a: [a.position[0] + ux * ra, 0, a.position[2] + uz * ra],
      b: [b.position[0] - ux * rb, 0, b.position[2] - uz * rb],
    })
  }
  return segs
}
