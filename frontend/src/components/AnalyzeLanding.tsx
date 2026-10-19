import { useState } from 'react'
import { useLens } from '../store'

const EXAMPLES = ['bert-base-uncased', 'gpt2', 't5-small']

const STEPS: [string, string, string][] = [
  ['01', 'Paste a link', 'Any public model on the Hugging Face Hub.'],
  ['02', 'We resolve it', 'Config and module tree — weights are never downloaded.'],
  ['03', 'Explore in 3D', 'Orbit the layer graph, then flip to true data-flow.'],
]

export function AnalyzeLanding() {
  const { status, error, progress, analyze } = useLens()
  const [value, setValue] = useState('')

  const submit = (id: string) => {
    const trimmed = id.trim()
    if (trimmed && status !== 'loading') void analyze(trimmed)
  }

  return (
    <div className="landing">
      <div className="landing-card">
        <p className="landing-eyebrow">
          <span className="tick" /> Neural architecture inspector
        </p>
        <h1>
          See <em>inside</em> the model.
        </h1>
        <p className="landing-sub">
          Paste a Hugging Face link. LayerLens maps every layer and every
          connection &mdash; weights never leave the Hub.
        </p>

        <form
          className="landing-form"
          onSubmit={(e) => {
            e.preventDefault()
            submit(value)
          }}
        >
          <input
            className="landing-input"
            placeholder="bert-base-uncased or https://huggingface.co/…"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            disabled={status === 'loading'}
            spellCheck={false}
            autoFocus
          />
          <button type="submit" className="landing-btn" disabled={status === 'loading' || !value.trim()}>
            {status === 'loading' ? 'Analyzing…' : 'Analyze'}
          </button>
        </form>

        <div className="landing-examples">
          <span className="ex-label">Try</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              className="ex-pill"
              disabled={status === 'loading'}
              onClick={() => {
                setValue(ex)
                submit(ex)
              }}
            >
              {ex}
            </button>
          ))}
        </div>

        <div className="landing-steps">
          {STEPS.map(([n, t, d]) => (
            <div className="landing-step" key={n}>
              <span className="step-n">{n}</span>
              <div>
                <strong>{t}</strong>
                <p>{d}</p>
              </div>
            </div>
          ))}
        </div>

        {status === 'loading' && (
          <p className="landing-progress">
            <span className="pulse-dot" /> {progress}
          </p>
        )}
        {status === 'error' && (
          <div className="landing-error">
            <strong>Couldn't analyze that model.</strong>
            <p>{error}</p>
          </div>
        )}

        <p className="landing-note">No weights are downloaded &mdash; the architecture is resolved from config only.</p>
      </div>
    </div>
  )
}
