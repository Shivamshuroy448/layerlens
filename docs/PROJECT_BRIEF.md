# LayerLens — See Inside Your Neural Networks
### Project brief · PyTorch-first · long-term portfolio build

**One-liner:** Upload a PyTorch model (or paste its code) and get an interactive 3D visualization of its layers — click any layer to learn how it works, watch a forward pass flow through the network.

---

## 1. How it works (the pipeline)

```
User input → Parser (sandboxed) → ModelGraph JSON → 3D layout → Explain + Interact
   .onnx file      torch.fx / onnx        the contract         react-three-fiber   curated KB (+LLM later)
   .pt weights     shape inference        backend → frontend   click / hover       per-layer cards
   code paste      sandbox (Docker)                                          forward-pass animation
```

**Ingest (3 input modes, phased):**
- **M1:** Upload `.onnx` directly — simplest, no code execution needed.
- **M3:** Paste PyTorch `nn.Module` code → executed in a **sandboxed Docker worker** (no network, CPU/memory limits, timeout) → traced with `torch.fx.symbolic_trace` (falls back to `torch.jit.trace` with dummy input) → exported to ONNX → parsed.
- **Later:** `.pt`/`.safetensors` weights + code; plain-English description → LLM drafts candidate architecture for user to confirm.

> ⚠️ Security note: `torch.load` on `.pt` files is pickle-based = arbitrary code execution. **Never** `torch.load` an upload on the main backend — only inside the sandbox. Prefer `.onnx` and `.safetensors` for direct uploads.

**Parse → ModelGraph (the single most important design decision):**
Everything becomes one intermediate representation, e.g.:
```json
{
  "nodes": [
    {"id": "conv1", "op": "Conv", "family": "convolution",
     "attrs": {"kernel": [3,3], "out_channels": 64, "stride": [1,1]},
     "params": 1792, "in_shape": [1,3,32,32], "out_shape": [1,64,32,32]}
  ],
  "edges": [{"from": "conv1", "to": "relu1", "shape": [1,64,32,32]}]
}
```
Use `onnx.shape_inference.infer_shapes` so every edge carries tensor shapes even when the uploader didn't provide them.

**3D layout (frontend):**
- *Sequential models:* stack slabs along one axis; block cross-section ∝ tensor dims, depth ∝ log(params); color by layer family.
- *Branching models (ResNet, transformers):* layered **Sugiyama-style layout in 3D** — rank nodes by longest path from input, order within rank to minimize edge crossings, lift branches into depth. This is a genuinely interesting algorithm to implement and a great interview story.
- *Interaction:* raycast click → select layer (camera eases to it); hover → highlight node + its edges; toggle labels, x-ray (wireframe) mode.

**Explain (click a layer):** side panel with
1. what the layer does (plain-English intuition),
2. the math (e.g. convolution formula),
3. *this instance's* config pulled from the graph ("64 filters, 3×3, stride 1 — turns 32×32×3 into 32×32×64"),
4. parameter count + why (e.g. "(3·3·3 + 1)·64 = 1792"),
5. "watch out" notes (e.g. "BatchNorm behaves differently in train vs eval").

**Source of explanations:** start with a **curated knowledge base** (`knowledge/layers/*.yaml` — deterministic, always correct). Add an **LLM pass in a later milestone** that writes model-specific narratives grounded in the actual graph (with the curated entry as guardrails against hallucination).

**"Show me how it works" (M4):** backend runs a real forward pass on sample input, captures per-layer output shapes/stats; frontend animates a pulse through the graph in topological order — the demo moment.

---

## 2. Tech stack

| Piece | Choice | Why |
|---|---|---|
| Frontend | React + TypeScript + Vite | Standard, hireable |
| 3D | react-three-fiber + drei | Declarative Three.js, OrbitControls/Html/Line out of the box |
| State | zustand | Tiny, no boilerplate for selected-layer/graph state |
| Backend | FastAPI (Python) | Async, Pydantic models = your ModelGraph schema, great docs |
| Parsing | `onnx`, `torch.fx`, `onnx.shape_inference` | Industry-standard tracing |
| Sandbox | Docker (`--network none`, memory/CPU caps, timeout) | Good enough for portfolio; note the tradeoff vs gVisor/Firecracker in docs |
| Queue (later) | Redis + RQ/Celery | Parsing can take seconds — don't block HTTP |
| Deploy (frontend) | Vercel | Free, instant previews |
| Deploy (backend) | Fly.io or Railway | Docker-native, free tier to start |
| Storage (later) | Cloudflare R2 / S3 | Uploaded models |

---

## 3. Milestones (each ends with a shippable demo)

- **M0 — Foundation (1–2 wks):** monorepo, CI, Docker Compose (frontend+backend), docs skeleton, `ModelGraph` Pydantic schema + JSON examples.
- **M1 — "Hello model" (3–4 wks):** ONNX upload → 3D sequential viz → click layer → curated explanation. **Deploy it.** First portfolio link.
- **M2 — Demo gallery (2 wks):** one-click famous architectures (LeNet, VGG-11, ResNet-18, tiny ViT, char-LSTM, MLP) preloaded as ONNX. Shows range instantly to visitors.
- **M3 — Code paste (4–6 wks):** sandboxed `torch.fx` tracing of pasted `nn.Module`. The hardest, most impressive milestone.
- **M4 — Branching + animation (3–4 wks):** Sugiyama 3D layout for skip connections; animated forward pass with real activations.
- **M5 — LLM explanations (2–3 wks):** model-level summaries ("a CNN for image classification…"), shareable links.
- **M6 — Launch polish (2 wks):** landing page, README with architecture diagram, demo video, blog post ("How I built a 3D neural network visualizer").

**Curated layer KB coverage (M1):** Linear, Conv1d/2d/3d, BatchNorm1d/2d, LayerNorm, ReLU, GELU, SiLU, Sigmoid, Tanh, Softmax, MaxPool2d, AvgPool2d, AdaptiveAvgPool2d, Dropout, Flatten, Embedding, LSTM, GRU, MultiheadAttention, Add, Concat, MatMul/Gemm.

---

## 4. Repo structure

```
layerlens/
├── frontend/                 # Vite + React + TS + R3F
│   └── src/
│       ├── scene/            # ModelScene, LayerNode, EdgeFlow, LayoutEngine
│       ├── components/       # UploadPanel, LayerInspector, Timeline
│       ├── store/            # zustand stores
│       └── api/              # backend client
├── backend/                  # FastAPI
│   └── app/
│       ├── routers/          # upload, parse, models, explain, infer
│       ├── schemas/          # ModelGraph pydantic models  ← the contract
│       ├── parsers/          # onnx_parser.py
│       └── explain/          # knowledge-base loader
├── parser-worker/            # Dockerfile: torch + sandbox runner
│   └── trace.py              # fx tracing → ONNX → ModelGraph JSON
├── knowledge/
│   └── layers/*.yaml         # curated explanations
├── infra/                    # docker-compose.yml, fly.toml, vercel.json
└── docs/                     # architecture.md, milestones.md, decisions/
```

---

## 5. What this teaches you (your interview narrative)

- `torch.fx` graph capture and ONNX internals — rare, valuable knowledge
- Designing an IR (the ModelGraph contract) between two systems
- 3D math: graph layout algorithms, camera animation, raycasting
- Practical security: sandboxing untrusted code, pickle risks
- Full-stack deployment with Docker

## 6. Suggested next step

M0 this week: scaffold the monorepo + `ModelGraph` schema + one hardcoded demo graph rendering as 3D blocks in the browser. That single win — *a neural net floating in 3D in your browser* — makes the whole project feel real.
