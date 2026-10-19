import { useMemo, useState } from 'react'
import type { LayerFamily, ModelGraph } from '../types'
import { ModelScene } from '../scene/ModelScene'
import { LayerInspector } from './LayerInspector'
import { Legend } from './Legend'
import { useLens } from '../store'

const FAMILY_ORDER: LayerFamily[] = [
  'input', 'convolution', 'linear', 'activation', 'pooling',
  'normalization', 'attention', 'reshape', 'recurrent', 'output', 'other',
]

function OrbitIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M13.6 8a5.6 5.6 0 1 1-1.7-4" />
      <path d="M13.9 1.2v3.2h-3.2" />
    </svg>
  )
}

function ResetIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" aria-hidden>
      <circle cx="8" cy="8" r="4.2" />
      <path d="M8 1v2.4M8 12.6V15M1 8h2.4M12.6 8H15" />
    </svg>
  )
}

/** The 3D scene fed with the real HF module graph. */
export function Model3DView({ graph }: { graph: ModelGraph }) {
  const { select } = useLens()
  const [autoRotate, setAutoRotate] = useState(false)
  const [sceneKey, setSceneKey] = useState(0)
  const [edgeMode, setEdgeMode] = useState<'hierarchy' | 'flow'>('hierarchy')
  const hasFlow = graph.flowEdges.length > 0

  const families = useMemo(() => {
    const present = new Set(graph.nodes.map((n) => n.family))
    return FAMILY_ORDER.filter((f) => present.has(f))
  }, [graph])

  return (
    <>
      <ModelScene
        key={sceneKey}
        graph={graph}
        autoRotate={autoRotate}
        serpentine
        sparseLabels
        edges={edgeMode === 'flow' ? graph.flowEdges : undefined}
      />
      <div className="scene-controls">
        {hasFlow && (
          <div className="seg-mini" role="tablist" aria-label="Edge style">
            <button
              className={edgeMode === 'hierarchy' ? 'on' : ''}
              onClick={() => setEdgeMode('hierarchy')}
              title="Module containment hierarchy"
            >
              Hierarchy
            </button>
            <button
              className={edgeMode === 'flow' ? 'on' : ''}
              onClick={() => setEdgeMode('flow')}
              title="True data-flow order from a forward pass"
            >
              Data flow
            </button>
          </div>
        )}
        <button
          className={autoRotate ? 'active' : ''}
          onClick={() => setAutoRotate((v) => !v)}
          title="Slowly orbit the camera"
        >
          <OrbitIcon /> Auto-orbit
        </button>
        <button
          onClick={() => {
            select(null)
            setSceneKey((k) => k + 1)
          }}
          title="Fly the camera back to the start"
        >
          <ResetIcon /> Reset view
        </button>
      </div>
      <LayerInspector />
      <Legend families={families} />
    </>
  )
}
