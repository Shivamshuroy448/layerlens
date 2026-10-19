import { useMemo, useState } from 'react'
import type { AnalyzeResult, AnalyzeTreeNode } from '../types'
import { formatParams } from '../analysis'
import { ArchitectureDiagram } from './ArchitectureDiagram'

const fmtVal = (v: number | null) => (v === null || v === undefined ? '—' : v.toLocaleString())

function ConfigGrid({ a }: { a: AnalyzeResult }) {
  const s = a.summary
  const tiles: [string, string][] = [
    ['Hidden size', fmtVal(s.hidden_size)],
    ['Layers', fmtVal(s.num_hidden_layers)],
    ['Attention heads', fmtVal(s.num_attention_heads)],
    ['Intermediate size', fmtVal(s.intermediate_size)],
    ['Vocab size', fmtVal(s.vocab_size)],
    ['Max positions', fmtVal(s.max_position_embeddings)],
  ]
  return (
    <div className="config-grid">
      {tiles.map(([k, v]) => (
        <div key={k} className="config-tile">
          <span className="config-k">{k}</span>
          <span className="config-v">{v}</span>
        </div>
      ))}
    </div>
  )
}

function TreeRow({ node }: { node: AnalyzeTreeNode }) {
  const [open, setOpen] = useState(node.depth < 2)
  const hasKids = node.children.length > 0
  return (
    <div className="tree-node">
      <div
        className="tree-row"
        style={{ paddingLeft: 8 + node.depth * 18 }}
        onClick={() => hasKids && setOpen((o) => !o)}
      >
        <span className={`tree-caret ${hasKids ? '' : 'leaf'}`}>{hasKids ? (open ? '▾' : '▸') : '·'}</span>
        <span className="tree-name">{node.name}</span>
        {node.value != null ? (
          <span className="tree-value">= {node.value}</span>
        ) : (
          <span className="tree-type">{node.type}</span>
        )}
        <span className="tree-params">{node.value != null ? '' : formatParams(node.params)}</span>
        {node.child_count > 0 && <span className="tree-folded">+{node.child_count} folded</span>}
      </div>
      {open &&
        node.children.map((c) => <TreeRow key={c.id} node={c} />)}
    </div>
  )
}

interface FlatHit {
  id: string
  path: string
  type: string
  params: number
  value: string | null
}

function collect(node: AnalyzeTreeNode, trail: string, out: FlatHit[]) {
  const path = trail ? `${trail} › ${node.name}` : node.name
  out.push({ id: node.id, path, type: node.type, params: node.params, value: node.value })
  for (const c of node.children) collect(c, path, out)
}

export function ArchitectureView({ analysis }: { analysis: AnalyzeResult }) {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<'diagram' | 'list'>('diagram')
  const s = analysis.summary

  const hits = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return null
    const all: FlatHit[] = []
    for (const root of analysis.tree) collect(root, '', all)
    return all.filter((h) => h.path.toLowerCase().includes(q) || h.type.toLowerCase().includes(q)).slice(0, 200)
  }, [query, analysis])

  return (
    <div className="arch-view">
      <div className="arch-header card">
        <p className="arch-kicker">Model card</p>
        <div className="arch-id">{analysis.model_id}</div>
        <div className="arch-chips">
          {s.model_type && <span className="arch-chip">{s.model_type}</span>}
          {s.pipeline_tag && <span className="arch-chip accent">{s.pipeline_tag}</span>}
          {s.architectures.map((a) => (
            <span key={a} className="arch-chip mono">
              {a}
            </span>
          ))}
        </div>
        <div className="arch-params">
          <strong>{formatParams(s.n_parameters)}</strong>
          <span>parameters · {analysis.total_modules} modules</span>
        </div>
      </div>

      {!analysis.resolved && analysis.note && (
        <p className="arch-warn">
          <strong>Config view.</strong> {analysis.note}
        </p>
      )}

      <h2 className="arch-h">Configuration</h2>
      <ConfigGrid a={analysis} />

      <div className="arch-h-row">
        <h2 className="arch-h">Layer hierarchy</h2>
        <div className="seg-mini">
          <button className={mode === 'diagram' ? 'on' : ''} onClick={() => setMode('diagram')}>
            Diagram
          </button>
          <button className={mode === 'list' ? 'on' : ''} onClick={() => setMode('list')}>
            List
          </button>
        </div>
      </div>
      {analysis.collapsed && (
        <p className="arch-note">
          Tree folded past depth 3 — {analysis.total_modules} modules total, showing the top levels.
        </p>
      )}
      {mode === 'diagram' ? (
        <ArchitectureDiagram key={analysis.model_id} tree={analysis.tree} />
      ) : (
        <>
          <input
            className="tree-search"
            placeholder="Filter modules… (e.g. attention, layernorm)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            spellCheck={false}
          />
          <div className="card tree-card">
            {hits ? (
              hits.length === 0 ? (
                <p className="dim pad">No modules match.</p>
              ) : (
                hits.map((h) => (
                  <div key={h.id} className="tree-row hit">
                    <span className="tree-name">{h.path}</span>
                    {h.value != null ? (
                      <span className="tree-value">= {h.value}</span>
                    ) : (
                      <>
                        <span className="tree-type">{h.type}</span>
                        <span className="tree-params">{formatParams(h.params)}</span>
                      </>
                    )}
                  </div>
                ))
              )
            ) : (
              analysis.tree.map((root) => <TreeRow key={root.id} node={root} />)
            )}
          </div>
        </>
      )}
    </div>
  )
}
