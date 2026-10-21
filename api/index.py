from __future__ import annotations

import json
import os
import re
from typing import Any
import requests
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="LayerLens API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HF_BASE = "https://huggingface.co"
HTTP_TIMEOUT = 30
MAX_MODULES_FULL = 600
COLLAPSE_DEPTH = 3
MAX_CONFIG_NODES = 800
MAX_CONFIG_DEPTH = 6
MAX_LIST_ITEMS = 50

_ID_RE = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")
_URL_RE = re.compile(r"^https?://(?:www\.)?huggingface\.co/(.+?)(?:/(?:tree|blob|resolve)/.*)?/?$")

# Load precomputed models
_PRECOMPUTED_FILE = os.path.join(os.path.dirname(__file__), "precomputed_models.json")
_PRECOMPUTED: dict[str, dict] = {}
if os.path.exists(_PRECOMPUTED_FILE):
    try:
        with open(_PRECOMPUTED_FILE, "r") as f:
            _PRECOMPUTED = json.load(f)
    except Exception as e:
        print(f"Warning: could not load precomputed models: {e}")

_cache: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    model_id: str


def parse_model_id(raw: str) -> str:
    raw = (raw or "").strip()
    m = _URL_RE.match(raw)
    path = m.group(1) if m else raw
    model_id = "/".join(path.strip("/").split("/")[:2])
    if not model_id or not _ID_RE.match(model_id):
        raise HTTPException(400, f"Not a valid Hugging Face model ID or URL: {raw!r}")
    return model_id


def _get(url: str) -> requests.Response:
    try:
        return requests.get(url, timeout=HTTP_TIMEOUT)
    except requests.RequestException as exc:
        raise HTTPException(502, f"Could not reach huggingface.co: {exc}")


def _val_repr(v: Any) -> str:
    r = repr(v)
    return r if len(r) <= 64 else r[:61] + "…"


def build_config_tree(cfg: dict) -> tuple[dict, int]:
    count = 0

    def visit(name: str, node_id: str, depth: int, v: Any) -> dict | None:
        nonlocal count
        if count >= MAX_CONFIG_NODES:
            return None
        count += 1
        node: dict = {
            "id": node_id,
            "name": name,
            "type": "value",
            "params": 0,
            "depth": depth,
            "child_count": 0,
            "children": [],
            "value": None,
        }
        if isinstance(v, dict):
            node["type"] = "object"
            if depth >= MAX_CONFIG_DEPTH:
                node["child_count"] = len(v)
            else:
                for k, subv in v.items():
                    c = visit(str(k), f"{node_id}.{k}", depth + 1, subv)
                    if c is not None:
                        node["children"].append(c)
                    else:
                        node["child_count"] += 1
        elif isinstance(v, list):
            node["type"] = f"array[{len(v)}]"
            if depth >= MAX_CONFIG_DEPTH:
                node["child_count"] = len(v)
            else:
                for i, subv in enumerate(v):
                    if i >= MAX_LIST_ITEMS:
                        node["child_count"] += len(v) - MAX_LIST_ITEMS
                        break
                    c = visit(f"[{i}]", f"{node_id}.{i}", depth + 1, subv)
                    if c is not None:
                        node["children"].append(c)
                    else:
                        node["child_count"] += 1
        else:
            node["value"] = _val_repr(v)
        return node

    root = visit("config", "config", 0, cfg)
    return root or {}, count


def _descendant_count(node: dict) -> int:
    return sum(1 + _descendant_count(c) for c in node.get("children", []))


def collapse_tree(node: dict, max_depth: int = COLLAPSE_DEPTH) -> None:
    if node.get("depth", 0) >= max_depth:
        if node.get("children"):
            node["child_count"] = _descendant_count(node)
            node["children"] = []
        return
    for child in node.get("children", []):
        collapse_tree(child, max_depth)


def flatten_tree(root: dict) -> tuple[list[dict], list[dict]]:
    nodes: list[dict] = []
    edges: list[dict] = []

    def visit(n: dict, parent_id: str | None) -> None:
        nodes.append({
            "id": n["id"],
            "label": n["name"],
            "type": n["type"],
            "depth": n["depth"],
            "params": n.get("params", 0),
        })
        if parent_id is not None:
            edges.append({"source": parent_id, "target": n["id"]})
        for c in n.get("children", []):
            visit(c, n["id"])

    visit(root, None)
    return nodes, edges


def _cfg_int(cfg: dict, *names: str) -> int | None:
    for n in names:
        v = cfg.get(n)
        if isinstance(v, int) and not isinstance(v, bool):
            return v
    return None


def build_pipeline_architecture(
    model_id: str,
    meta: dict,
    target_repo: str,
    model_idx: dict,
    is_lora: bool = False,
    lora_file: str | None = None,
) -> dict:
    pipeline_class = model_idx.get("_class_name", "DiffusionPipeline")
    pipeline_tag = meta.get("pipeline_tag") or "text-to-image"

    backbone_name = "transformer" if "transformer" in model_idx else ("unet" if "unet" in model_idx else "model")
    backbone_class = (
        model_idx.get(backbone_name, ["diffusers", "DiffusionBackbone"])[1]
        if backbone_name in model_idx
        else "Backbone"
    )

    # Fetch backbone config
    bb_resp = _get(f"{HF_BASE}/{target_repo}/raw/main/{backbone_name}/config.json")
    bb_cfg = bb_resp.json() if bb_resp.status_code == 200 else {}

    dim = bb_cfg.get("dim") or bb_cfg.get("hidden_size") or bb_cfg.get("cross_attention_dim") or 1024
    layers = bb_cfg.get("n_layers") or bb_cfg.get("num_layers") or bb_cfg.get("layers_per_block") or 24
    heads = bb_cfg.get("n_heads") or bb_cfg.get("num_attention_heads") or 16
    in_channels = bb_cfg.get("in_channels", 4)

    # Text encoder
    te_name = "text_encoder"
    te_class = (
        model_idx.get(te_name, ["transformers", "TextEncoder"])[1]
        if te_name in model_idx
        else "TextEncoder"
    )
    te_resp = _get(f"{HF_BASE}/{target_repo}/raw/main/{te_name}/config.json")
    te_cfg = te_resp.json() if te_resp.status_code == 200 else {}
    te_dim = te_cfg.get("hidden_size", 1024)
    te_layers = te_cfg.get("num_hidden_layers", 12)
    te_heads = te_cfg.get("num_attention_heads", 16)
    vocab_size = te_cfg.get("vocab_size", 32000)

    vae_class = model_idx.get("vae", ["diffusers", "AutoencoderKL"])[1] if "vae" in model_idx else "AutoencoderKL"
    scheduler_class = (
        model_idx.get("scheduler", ["diffusers", "Scheduler"])[1]
        if "scheduler" in model_idx
        else "Scheduler"
    )

    # Calculate parameter counts
    te_params = int(te_dim * te_dim * te_layers * 4 + te_dim * vocab_size)
    bb_params = int(dim * dim * layers * 4)
    vae_params = 84_000_000
    lora_params = 15_728_640 if is_lora else 0
    total_params = te_params + bb_params + vae_params + lora_params

    # 1. Build hierarchical tree for Architecture View
    tree_root: dict = {
        "id": "pipeline",
        "name": model_id.split("/")[-1],
        "type": pipeline_class,
        "params": 0,
        "depth": 0,
        "child_count": 0,
        "children": [],
        "value": None,
    }

    # Text encoder branch
    te_node: dict = {
        "id": "pipeline.text_encoder",
        "name": "text_encoder",
        "type": te_class,
        "params": te_params,
        "depth": 1,
        "child_count": 0,
        "children": [
            {
                "id": "pipeline.text_encoder.embed",
                "name": "embeddings",
                "type": "Embedding",
                "params": te_dim * vocab_size,
                "depth": 2,
                "child_count": 0,
                "children": [],
                "value": f"{te_dim}d (vocab: {vocab_size:,})",
            },
            {
                "id": "pipeline.text_encoder.layers",
                "name": f"encoder_stack[0..{te_layers-1}]",
                "type": "AttentionBlocks",
                "params": te_dim * te_dim * te_layers * 4,
                "depth": 2,
                "child_count": te_layers,
                "children": [
                    {
                        "id": f"pipeline.text_encoder.layer.{i}",
                        "name": f"layer.{i}",
                        "type": "SelfAttentionLayer",
                        "params": int(te_dim * te_dim * 4),
                        "depth": 3,
                        "child_count": 0,
                        "children": [],
                        "value": f"{te_heads} heads",
                    }
                    for i in range(min(te_layers, 4))
                ],
                "value": f"{te_layers} layers",
            },
        ],
        "value": None,
    }
    tree_root["children"].append(te_node)

    # Backbone branch (Transformer / UNet)
    bb_node: dict = {
        "id": f"pipeline.{backbone_name}",
        "name": backbone_name,
        "type": backbone_class,
        "params": bb_params,
        "depth": 1,
        "child_count": 0,
        "children": [
            {
                "id": f"pipeline.{backbone_name}.in_proj",
                "name": "in_projection",
                "type": "Conv2d",
                "params": dim * in_channels * 4,
                "depth": 2,
                "child_count": 0,
                "children": [],
                "value": f"in_channels: {in_channels} → {dim}d",
            },
            {
                "id": f"pipeline.{backbone_name}.blocks",
                "name": f"blocks[0..{layers-1}]",
                "type": "DiTBlocks",
                "params": bb_params,
                "depth": 2,
                "child_count": layers,
                "children": [
                    {
                        "id": f"pipeline.{backbone_name}.block.{i}",
                        "name": f"block.{i}",
                        "type": "CrossAttentionBlock",
                        "params": int(dim * dim * 4),
                        "depth": 3,
                        "child_count": 0,
                        "children": [],
                        "value": f"{heads} heads, {dim} dim",
                    }
                    for i in range(min(layers, 6))
                ],
                "value": f"{layers} layers, {heads} heads",
            },
        ],
        "value": None,
    }

    if is_lora:
        bb_node["children"].append({
            "id": f"pipeline.{backbone_name}.lora",
            "name": "lora_adapter",
            "type": "LoRALayer",
            "params": lora_params,
            "depth": 2,
            "child_count": 0,
            "children": [],
            "value": lora_file or "Rank-16/32 Adapters",
        })

    tree_root["children"].append(bb_node)

    # VAE branch
    vae_node: dict = {
        "id": "pipeline.vae",
        "name": "vae",
        "type": vae_class,
        "params": vae_params,
        "depth": 1,
        "child_count": 0,
        "children": [
            {
                "id": "pipeline.vae.decoder",
                "name": "decoder",
                "type": "UpDecoderBlock2D",
                "params": 54_000_000,
                "depth": 2,
                "child_count": 0,
                "children": [],
                "value": "Latent → RGB Pixel Space",
            }
        ],
        "value": None,
    }
    tree_root["children"].append(vae_node)

    # Scheduler branch
    tree_root["children"].append({
        "id": "pipeline.scheduler",
        "name": "scheduler",
        "type": scheduler_class,
        "params": 0,
        "depth": 1,
        "child_count": 0,
        "children": [],
        "value": "Noise Schedule / Flow Match",
    })

    # 2. Build flat nodes for the 3D scene (Model3DView)
    flat_nodes: list[dict] = [
        {"id": "input_prompt", "label": "Prompt Input", "type": "Input", "depth": 0, "params": 0},
        {"id": "te_embed", "label": "Text Embeddings", "type": "Embedding", "depth": 1, "params": te_dim * vocab_size},
        {"id": "te_attn", "label": f"{te_class} ({te_layers}L)", "type": "Attention", "depth": 1, "params": te_params},
        {"id": "latent_noise", "label": "Latent Noise (16ch)", "type": "Input", "depth": 0, "params": 0},
        {"id": "bb_patch", "label": "Patch Embed", "type": "Conv2d", "depth": 1, "params": dim * in_channels * 4},
    ]

    sample_blocks = min(layers, 8)
    for i in range(sample_blocks):
        flat_nodes.append({
            "id": f"bb_block_{i}",
            "label": f"DiT Block {i}",
            "type": "Attention",
            "depth": 2,
            "params": int(dim * dim * 4),
        })

    if is_lora:
        flat_nodes.append({
            "id": "lora_layer",
            "label": "LoRA Adapter",
            "type": "Linear",
            "depth": 2,
            "params": lora_params,
        })

    flat_nodes.extend([
        {"id": "scheduler_node", "label": scheduler_class, "type": "Relu", "depth": 1, "params": 0},
        {"id": "vae_decode", "label": "VAE Decoder", "type": "Conv2d", "depth": 1, "params": vae_params},
        {"id": "image_output", "label": "Output Image", "type": "Softmax", "depth": 0, "params": 0},
    ])

    # 3. Build edges connecting the flow
    flat_edges: list[dict] = [
        {"source": "input_prompt", "target": "te_embed"},
        {"source": "te_embed", "target": "te_attn"},
        {"source": "latent_noise", "target": "bb_patch"},
        {"source": "bb_patch", "target": "bb_block_0"},
        {"source": "te_attn", "target": "bb_block_0"},
    ]

    for i in range(sample_blocks - 1):
        flat_edges.append({"source": f"bb_block_{i}", "target": f"bb_block_{i+1}"})

    last_block = f"bb_block_{sample_blocks - 1}"
    if is_lora:
        flat_edges.append({"source": "lora_layer", "target": "bb_block_0"})

    flat_edges.extend([
        {"source": last_block, "target": "scheduler_node"},
        {"source": "scheduler_node", "target": "vae_decode"},
        {"source": "vae_decode", "target": "image_output"},
    ])

    flow_edges = list(flat_edges)

    note = (
        f"LoRA adapter targeting {target_repo} ({pipeline_class})"
        if is_lora
        else f"Diffusers {pipeline_class} architecture ({target_repo})"
    )

    return {
        "model_id": model_id,
        "summary": {
            "model_type": "lora-adapter" if is_lora else "diffusion-pipeline",
            "architectures": [pipeline_class, backbone_class],
            "n_parameters": total_params,
            "hidden_size": dim,
            "num_hidden_layers": layers,
            "num_attention_heads": heads,
            "intermediate_size": te_dim,
            "vocab_size": vocab_size,
            "max_position_embeddings": 1024,
            "pipeline_tag": pipeline_tag,
        },
        "tree": [tree_root],
        "nodes": flat_nodes,
        "edges": flat_edges,
        "collapsed": False,
        "total_modules": len(flat_nodes),
        "flow_edges": flow_edges,
        "resolved": True,
        "note": note,
    }


def build_repo_assets_response(model_id: str, meta: dict) -> dict:
    siblings = meta.get("siblings", [])
    pipeline_tag = meta.get("pipeline_tag") or "custom"

    tree_root: dict = {
        "id": "repo",
        "name": model_id.split("/")[-1],
        "type": "HuggingFaceRepository",
        "params": 0,
        "depth": 0,
        "child_count": len(siblings),
        "children": [],
        "value": None,
    }

    flat_nodes: list[dict] = [
        {"id": "repo_root", "label": model_id.split("/")[-1], "type": "Input", "depth": 0, "params": 0}
    ]
    flat_edges: list[dict] = []

    for idx, sib in enumerate(siblings[:30]):
        fn = sib.get("rfilename", f"file_{idx}")
        ext = fn.split(".")[-1] if "." in fn else "file"
        node_id = f"file_{idx}"
        tree_root["children"].append({
            "id": node_id,
            "name": fn,
            "type": f"File ({ext})",
            "params": 0,
            "depth": 1,
            "child_count": 0,
            "children": [],
            "value": f"{ext.upper()} asset",
        })
        flat_nodes.append({
            "id": node_id,
            "label": fn.split("/")[-1],
            "type": "Linear" if ext in ("safetensors", "bin", "pt") else "Conv",
            "depth": 1,
            "params": 0,
        })
        flat_edges.append({"source": "repo_root", "target": node_id})

    return {
        "model_id": model_id,
        "summary": {
            "model_type": "repository-assets",
            "architectures": [pipeline_tag],
            "n_parameters": 0,
            "hidden_size": None,
            "num_hidden_layers": len(siblings),
            "num_attention_heads": None,
            "intermediate_size": None,
            "vocab_size": None,
            "max_position_embeddings": None,
            "pipeline_tag": pipeline_tag,
        },
        "tree": [tree_root],
        "nodes": flat_nodes,
        "edges": flat_edges,
        "collapsed": False,
        "total_modules": len(siblings),
        "flow_edges": [],
        "resolved": False,
        "note": "Repository weights and assets without standard config.json architecture file.",
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/graph/demo")
def demo_graph(name: str = Query(default="lenet-mnist")):
    return {
        "name": "lenet-mnist",
        "description": "LeNet-style CNN: 28×28 digit image → 10 class probabilities.",
        "nodes": [
            {"id": "input", "op": "Input", "label": "Input", "family": "input", "attrs": {}, "params": 0, "in_shape": [1, 1, 28, 28], "out_shape": [1, 1, 28, 28]},
            {"id": "conv1", "op": "Conv", "label": "Conv2d", "family": "convolution", "attrs": {"kernel": [5, 5], "in_channels": 1, "out_channels": 6, "stride": [1, 1]}, "params": 156, "in_shape": [1, 1, 28, 28], "out_shape": [1, 6, 24, 24]},
            {"id": "relu1", "op": "Relu", "label": "ReLU", "family": "activation", "attrs": {}, "params": 0, "in_shape": [1, 6, 24, 24], "out_shape": [1, 6, 24, 24]},
            {"id": "pool1", "op": "MaxPool", "label": "MaxPool2d", "family": "pooling", "attrs": {"kernel": [2, 2], "stride": [2, 2]}, "params": 0, "in_shape": [1, 6, 24, 24], "out_shape": [1, 6, 12, 12]},
            {"id": "conv2", "op": "Conv", "label": "Conv2d", "family": "convolution", "attrs": {"kernel": [5, 5], "in_channels": 6, "out_channels": 16, "stride": [1, 1]}, "params": 2416, "in_shape": [1, 6, 12, 12], "out_shape": [1, 16, 8, 8]},
            {"id": "relu2", "op": "Relu", "label": "ReLU", "family": "activation", "attrs": {}, "params": 0, "in_shape": [1, 16, 8, 8], "out_shape": [1, 16, 8, 8]},
            {"id": "pool2", "op": "MaxPool", "label": "MaxPool2d", "family": "pooling", "attrs": {"kernel": [2, 2], "stride": [2, 2]}, "params": 0, "in_shape": [1, 16, 8, 8], "out_shape": [1, 16, 4, 4]},
            {"id": "flatten", "op": "Flatten", "label": "Flatten", "family": "reshape", "attrs": {}, "params": 0, "in_shape": [1, 16, 4, 4], "out_shape": [1, 256]},
            {"id": "fc1", "op": "Gemm", "label": "Linear", "family": "linear", "attrs": {"in_features": 256, "out_features": 120}, "params": 30840, "in_shape": [1, 256], "out_shape": [1, 120]},
            {"id": "relu3", "op": "Relu", "label": "ReLU", "family": "activation", "attrs": {}, "params": 0, "in_shape": [1, 120], "out_shape": [1, 120]},
            {"id": "fc2", "op": "Gemm", "label": "Linear", "family": "linear", "attrs": {"in_features": 120, "out_features": 84}, "params": 10164, "in_shape": [1, 120], "out_shape": [1, 84]},
            {"id": "fc3", "op": "Gemm", "label": "Linear", "family": "linear", "attrs": {"in_features": 84, "out_features": 10}, "params": 850, "in_shape": [1, 84], "out_shape": [1, 10]},
            {"id": "output", "op": "Softmax", "label": "Softmax", "family": "output", "attrs": {"dim": 1}, "params": 0, "in_shape": [1, 10], "out_shape": [1, 10]},
        ],
        "edges": [
            {"source": "input", "target": "conv1", "shape": [1, 6, 24, 24]},
            {"source": "conv1", "target": "relu1", "shape": [1, 6, 24, 24]},
            {"source": "relu1", "target": "pool1", "shape": [1, 6, 12, 12]},
            {"source": "pool1", "target": "conv2", "shape": [1, 16, 8, 8]},
            {"source": "conv2", "target": "relu2", "shape": [1, 16, 8, 8]},
            {"source": "relu2", "target": "pool2", "shape": [1, 16, 4, 4]},
            {"source": "pool2", "target": "flatten", "shape": [1, 256]},
            {"source": "flatten", "target": "fc1", "shape": [1, 120]},
            {"source": "fc1", "target": "relu3", "shape": [1, 120]},
            {"source": "relu3", "target": "fc2", "shape": [1, 84]},
            {"source": "fc2", "target": "fc3", "shape": [1, 10]},
            {"source": "fc3", "target": "output", "shape": [1, 10]},
        ],
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    model_id = parse_model_id(req.model_id)

    # 1. External backend proxy if configured
    backend_url = os.environ.get("BACKEND_URL")
    if backend_url:
        try:
            r = requests.post(f"{backend_url.rstrip('/')}/api/analyze", json={"model_id": model_id}, timeout=HTTP_TIMEOUT)
            return Response(content=r.content, status_code=r.status_code, media_type="application/json")
        except Exception as e:
            print(f"Proxy to BACKEND_URL failed: {e}")

    # 2. Check in-memory cache
    if model_id in _cache:
        return _cache[model_id]

    # 3. Check precomputed models (high-fidelity PyTorch models with meta tensors & flow edges)
    if model_id in _PRECOMPUTED:
        res = _PRECOMPUTED[model_id]
        _cache[model_id] = res
        return res

    # 4. Fetch repo metadata from Hugging Face
    meta_resp = _get(f"{HF_BASE}/api/models/{model_id}")
    if meta_resp.status_code == 404 or "invalid username or password" in meta_resp.text.lower():
        raise HTTPException(404, f"Model {model_id!r} not found on Hugging Face")

    try:
        meta = meta_resp.json()
    except Exception:
        raise HTTPException(502, f"Invalid metadata response for {model_id!r}")

    # 5. Check if standard config.json exists
    cfg_resp = _get(f"{HF_BASE}/{model_id}/raw/main/config.json")
    if cfg_resp.status_code == 200:
        cfg = cfg_resp.json()
        root, total = build_config_tree(cfg)
        collapsed = False
        if total > MAX_MODULES_FULL:
            collapse_tree(root)
            collapsed = True
        flat_nodes, flat_edges = flatten_tree(root)

        res = {
            "model_id": model_id,
            "summary": {
                "model_type": str(cfg.get("model_type")) if cfg.get("model_type") else None,
                "architectures": [str(a) for a in (cfg.get("architectures") or [])],
                "n_parameters": 0,
                "hidden_size": _cfg_int(cfg, "hidden_size", "d_model", "n_embd"),
                "num_hidden_layers": _cfg_int(cfg, "num_hidden_layers", "n_layer", "num_layers"),
                "num_attention_heads": _cfg_int(cfg, "num_attention_heads", "n_head", "num_heads"),
                "intermediate_size": _cfg_int(cfg, "intermediate_size", "d_ff"),
                "vocab_size": _cfg_int(cfg, "vocab_size"),
                "max_position_embeddings": _cfg_int(cfg, "max_position_embeddings", "n_positions"),
                "pipeline_tag": meta.get("pipeline_tag"),
            },
            "tree": [root],
            "nodes": flat_nodes,
            "edges": flat_edges,
            "collapsed": collapsed,
            "total_modules": total,
            "flow_edges": [],
            "resolved": False,
            "note": "Resolved from Hugging Face config.json",
        }
        _cache[model_id] = res
        return res

    # 6. Check if it is a Diffusers model with model_index.json
    idx_resp = _get(f"{HF_BASE}/{model_id}/raw/main/model_index.json")
    if idx_resp.status_code == 200:
        try:
            model_idx = idx_resp.json()
            res = build_pipeline_architecture(model_id, meta, model_id, model_idx, is_lora=False)
            _cache[model_id] = res
            return res
        except Exception as e:
            print(f"Failed to build diffusers pipeline: {e}")

    # 7. Check if it is a LoRA / Adapter with base_model
    base_model = meta.get("cardData", {}).get("base_model")
    if not base_model:
        for tag in meta.get("tags", []):
            if tag.startswith("base_model:"):
                base_model = tag.split("base_model:", 1)[1]
                break

    lora_file = None
    for sib in meta.get("siblings", []):
        rfn = sib.get("rfilename", "")
        if rfn.endswith((".safetensors", ".bin", ".pt")):
            lora_file = rfn
            break

    if base_model:
        base_idx_resp = _get(f"{HF_BASE}/{base_model}/raw/main/model_index.json")
        if base_idx_resp.status_code == 200:
            try:
                model_idx = base_idx_resp.json()
                res = build_pipeline_architecture(
                    model_id, meta, base_model, model_idx, is_lora=True, lora_file=lora_file
                )
                _cache[model_id] = res
                return res
            except Exception as e:
                print(f"Failed to build LoRA + base model pipeline: {e}")

    # 8. Check adapter_config.json
    adp_resp = _get(f"{HF_BASE}/{model_id}/raw/main/adapter_config.json")
    if adp_resp.status_code == 200:
        try:
            adp_cfg = adp_resp.json()
            root, total = build_config_tree(adp_cfg)
            flat_nodes, flat_edges = flatten_tree(root)
            res = {
                "model_id": model_id,
                "summary": {
                    "model_type": "lora-adapter",
                    "architectures": [adp_cfg.get("peft_type", "LoRA")],
                    "n_parameters": 0,
                    "hidden_size": adp_cfg.get("r"),
                    "num_hidden_layers": None,
                    "num_attention_heads": None,
                    "intermediate_size": adp_cfg.get("lora_alpha"),
                    "vocab_size": None,
                    "max_position_embeddings": None,
                    "pipeline_tag": meta.get("pipeline_tag"),
                },
                "tree": [root],
                "nodes": flat_nodes,
                "edges": flat_edges,
                "collapsed": False,
                "total_modules": total,
                "flow_edges": [],
                "resolved": False,
                "note": f"PEFT LoRA adapter (base: {adp_cfg.get('base_model_name_or_path', 'unknown')})",
            }
            _cache[model_id] = res
            return res
        except Exception as e:
            print(f"Failed to parse adapter_config.json: {e}")

    # 9. Fallback: Repository Assets Tree
    res = build_repo_assets_response(model_id, meta)
    _cache[model_id] = res
    return res
