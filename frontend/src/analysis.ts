/** Adapter: real HF analysis → the ModelGraph contract the 3D scene speaks. */
import type { AnalyzeResult, LayerFamily, ModelGraph } from './types'

/** Map a Hugging Face module class name onto an M0 layer family (drives 3D color). */
export function familyFor(typeName: string): LayerFamily {
  const s = typeName.toLowerCase()
  if (s.includes('embedding')) return 'input'
  if (s.includes('attention') || s.includes('selfattn') || s.includes('crossattn')) return 'attention'
  if (s.includes('linear') || s === 'dense' || s.endsWith('dense')) return 'linear'
  if (s.includes('layernorm') || s.includes('rmsnorm')) return 'normalization'
  if (s.includes('gelu') || s.includes('relu') || s.includes('dropout') || s.includes('activation') || s.includes('silu'))
    return 'activation'
  if (s.includes('pool')) return 'pooling'
  if (s.includes('conv')) return 'convolution'
  return 'other'
}

export function formatParams(p: number): string {
  if (p >= 1_000_000) return `${(p / 1_000_000).toFixed(2)}M`
  if (p >= 1_000) return `${(p / 1_000).toFixed(1)}k`
  return `${p}`
}

export function analysisToGraph(a: AnalyzeResult): ModelGraph {
  const childrenOf = new Map<string, string[]>()
  const labelOf = new Map(a.nodes.map((n) => [n.id, n.label]))
  for (const e of a.edges) {
    const list = childrenOf.get(e.source) ?? []
    list.push(labelOf.get(e.target) ?? e.target)
    childrenOf.set(e.source, list)
  }
  return {
    name: a.model_id,
    description: `${a.summary.model_type ?? 'unknown architecture'} · ${formatParams(a.summary.n_parameters)} params`,
    nodes: a.nodes.map((n) => ({
      id: n.id,
      op: n.type,
      label: n.label,
      family: familyFor(n.type),
      attrs: {
        module_type: n.type,
        depth: n.depth,
        children: childrenOf.get(n.id) ?? [],
      },
      params: n.params,
      in_shape: null,
      out_shape: null,
    })),
    edges: a.edges.map((e) => ({ source: e.source, target: e.target, shape: null })),
    flowEdges: (a.flow_edges ?? []).map((e) => ({ source: e.source, target: e.target, shape: null })),
  }
}
