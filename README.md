---
title: LayerLens - See Inside Any Hugging Face Model
emoji: ◈
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
---

# ◈ LayerLens v2 — See Inside Any Hugging Face Model

Paste a Hugging Face model link or ID → the backend resolves the **real architecture**
(no weight download) → the frontend shows two switchable views behind a fixed
top-middle toggle:

- **Architecture** — model header (id, type, param count), config grid
  (hidden size, layers, heads, vocab…), collapsible layer-hierarchy tree with search.
- **3D Model** — the immersive 3D scene (bloom, fog, starfield, animated data-flow
  pulses, splash, auto-orbit, reset view) fed with the model's true module graph.
  Nodes are colored by module type; click one for its detail panel.

> **Milestone M1 (HF-first)** — `POST /api/analyze` builds the true module tree with
> `transformers` + `accelerate` meta tensors. The old M0 ONNX "Hello model" plan is
> superseded. M0's demo-graph endpoints (`/api/graph/demo`) still work.

## How it works (backend)

1. `POST /api/analyze { "model_id": "bert-base-uncased" }` — bare ID or full
   `https://huggingface.co/...` URL.
2. `config.json` + model metadata are fetched over plain HTTPS (`requests`,
   which respects the sandbox egress proxy).
3. The config is built from the dict (no network), then the model is instantiated
   with `AutoModel.from_config` inside `accelerate.init_empty_weights()` — every
   parameter is a **meta tensor**, so nothing downloads and RAM stays flat.
4. `model.named_modules()` is walked for the true hierarchy; parameter counts come
   from `p.numel()` (works on meta tensors).
5. Models with >600 modules get their tree folded past depth 3
   (`collapsed: true`, folded descendants counted in `child_count`).

Clean errors: unknown model → `404 "not found"`; gated/private → `403 "needs token"`;
custom remote code (`trust_remote_code`) → `422`.

## Quickstart

```bash
# 1. backend env (repo root — durable venv)
/workspace/layerlens # cd ~/workspace/layerlens
python3 -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only torch
pip install -r backend/requirements.txt
cd backend && python -m pytest -q        # 8 tests, incl. live bert-tiny analyze

# 2. backend server (http://localhost:8000)
cd ~/workspace/layerlens/backend
../.venv/bin/uvicorn app.main:app --port 8000

# 3. frontend dev server (http://localhost:5173, /api proxied to :8000)
cd ~/workspace/layerlens/frontend
npm install
npm run dev
```

Needs network access to `huggingface.co` (the sandbox provides it via the
`https_proxy` env vars — `requests` picks them up automatically).

Try: `bert-base-uncased`, `gpt2`, `t5-small` (chips on the landing page).

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/graph/demo?name=` | M0 hardcoded demo graph |
| POST | `/api/analyze` | `{ "model_id": "…" }` → `{ model_id, summary, tree, nodes, edges, collapsed, total_modules }` |

## Layout

- `backend/app/hf.py` — HF fetching, model building, tree/flatten/collapse, summary.
- `backend/app/hf_schemas.py` — analyze response schemas.
- `backend/app/routers/analyze.py` — `POST /api/analyze`.
- `frontend/src/components/AnalyzeLanding.tsx` — landing input + chips + loading/error.
- `frontend/src/components/ArchitectureView.tsx` — header, config grid, tree + search.
- `frontend/src/components/Model3DView.tsx` — immersive 3D view (M0 scene, serpentine layout).
- `frontend/src/components/ViewToggle.tsx` — fixed top-middle [Architecture | 3D Model].
- `frontend/src/analysis.ts` — HF analysis → `ModelGraph` adapter + module-type colors.

## Roadmap

- **M2** — richer per-module docs in the inspector; forward-pass animation along edges
- **M3** — share links for analyzed models
- **M4** — Sugiyama 3D layout for branching nets
