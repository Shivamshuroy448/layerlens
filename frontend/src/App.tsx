import { Model3DView } from './components/Model3DView'
import { ArchitectureView } from './components/ArchitectureView'
import { AnalyzeLanding } from './components/AnalyzeLanding'
import { ViewToggle } from './components/ViewToggle'
import { formatParams } from './analysis'
import { useLens } from './store'
import './index.css'

export default function App() {
  const { analysis, graph, view, reset } = useLens()

  if (!analysis || !graph) {
    return (
      <div className="app">
        <AnalyzeLanding />
      </div>
    )
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <svg width="21" height="21" viewBox="0 0 22 22" fill="none" aria-hidden>
            <rect x="2" y="2.5" width="18" height="4.6" rx="1.6" fill="#ff4d00" />
            <rect x="5.5" y="8.7" width="11" height="4.6" rx="1.6" fill="#eef0f4" opacity="0.9" />
            <rect x="9" y="14.9" width="4" height="4.6" rx="1.6" fill="#eef0f4" opacity="0.45" />
          </svg>
          LayerLens
        </div>
        <div className="model-meta">
          <strong>{analysis.model_id}</strong>
          <span className="dim">{graph.nodes.length} modules</span>
          <span className="dim">·</span>
          <span className="dim">
            {analysis.resolved ? `${formatParams(analysis.summary.n_parameters)} params` : 'config view'}
          </span>
        </div>
        <button className="topbar-btn" onClick={reset} title="Analyze a different model">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M13.6 8a5.6 5.6 0 1 1-1.7-4" />
            <path d="M13.9 1.2v3.2h-3.2" />
          </svg>
          New model
        </button>
      </header>
      <ViewToggle />
      <main className="viewport">
        {view === 'arch' || !analysis.resolved ? (
          <ArchitectureView analysis={analysis} />
        ) : (
          <Model3DView graph={graph} />
        )}
      </main>
    </div>
  )
}
