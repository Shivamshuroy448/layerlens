import { create } from 'zustand'
import type { AnalyzeResult, ModelGraph } from './types'
import { analysisToGraph } from './analysis'

export type ViewMode = 'arch' | 'model3d'
type Status = 'idle' | 'loading' | 'error'

const PROGRESS_STEPS = [
  'contacting huggingface.co…',
  'fetching config.json…',
  'resolving module tree…',
  'counting parameters…',
  'laying out the graph…',
]

let progressTimer: number | undefined

interface LensState {
  analysis: AnalyzeResult | null
  graph: ModelGraph | null
  view: ViewMode
  status: Status
  error: string | null
  progress: string
  selectedId: string | null
  analyze: (modelId: string) => Promise<void>
  setView: (v: ViewMode) => void
  select: (id: string | null) => void
  reset: () => void
}

export const useLens = create<LensState>((set) => ({
  analysis: null,
  graph: null,
  view: 'arch',
  status: 'idle',
  error: null,
  progress: PROGRESS_STEPS[0],
  selectedId: null,

  analyze: async (modelId: string) => {
    if (progressTimer) window.clearInterval(progressTimer)
    set({ status: 'loading', error: null, progress: PROGRESS_STEPS[0], view: 'arch', selectedId: null })
    let i = 0
    progressTimer = window.setInterval(() => {
      i = Math.min(i + 1, PROGRESS_STEPS.length - 1)
      useLens.setState({ progress: PROGRESS_STEPS[i] })
    }, 1500)
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId }),
      })
      const body = (await res.json().catch(() => ({}))) as {
        detail?: string
      } & Partial<AnalyzeResult>
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`)
      const analysis = body as AnalyzeResult
      set({
        analysis,
        graph: analysisToGraph(analysis),
        status: 'idle',
        selectedId: null,
      })
    } catch (e) {
      set({ status: 'error', error: e instanceof Error ? e.message : String(e) })
    } finally {
      if (progressTimer) window.clearInterval(progressTimer)
      progressTimer = undefined
    }
  },

  setView: (view) => set({ view }),
  select: (selectedId) => set({ selectedId }),
  reset: () =>
    set({
      analysis: null,
      graph: null,
      status: 'idle',
      error: null,
      selectedId: null,
      view: 'arch',
    }),
}))
