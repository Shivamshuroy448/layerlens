/** TypeScript mirror of backend/app/schemas.py — the ModelGraph contract. */

export type LayerFamily =
  | 'input' | 'convolution' | 'linear' | 'activation'
  | 'pooling' | 'normalization' | 'reshape' | 'recurrent'
  | 'attention' | 'output' | 'other'

export interface GraphNode {
  id: string
  op: string
  label: string
  family: LayerFamily
  attrs: Record<string, unknown>
  params: number
  in_shape: number[] | null
  out_shape: number[] | null
}

export interface GraphEdge {
  source: string
  target: string
  shape: number[] | null
}

export interface ModelGraph {
  name: string
  description: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  flowEdges: GraphEdge[]
}

/** POST /api/analyze response — a real Hugging Face architecture. */

export interface AnalyzeSummary {
  model_type: string | null
  architectures: string[]
  n_parameters: number
  hidden_size: number | null
  num_hidden_layers: number | null
  num_attention_heads: number | null
  intermediate_size: number | null
  vocab_size: number | null
  max_position_embeddings: number | null
  pipeline_tag: string | null
}

export interface AnalyzeTreeNode {
  id: string
  name: string
  type: string
  params: number
  depth: number
  child_count: number
  children: AnalyzeTreeNode[]
  value: string | null
}

export interface AnalyzeFlatNode {
  id: string
  label: string
  type: string
  depth: number
  params: number
}

export interface AnalyzeFlatEdge {
  source: string
  target: string
}

export interface AnalyzeResult {
  model_id: string
  summary: AnalyzeSummary
  tree: AnalyzeTreeNode[]
  nodes: AnalyzeFlatNode[]
  edges: AnalyzeFlatEdge[]
  flow_edges: AnalyzeFlatEdge[]
  collapsed: boolean
  total_modules: number
  resolved: boolean
  note: string | null
}
