"""Hugging Face model analysis — resolve the TRUE architecture without weights.

Pipeline for a model id like ``bert-base-uncased``:
  1. Fetch ``config.json`` over plain HTTPS (``requests``, which respects the
     sandbox egress proxy — the vendored HTTP client inside
     ``huggingface_hub``/``transformers`` 5.x cannot parse this proxy env).
  2. Fetch ``https://huggingface.co/api/models/{id}`` for metadata.
  3. Build the ``PretrainedConfig`` from the dict (no network), resolve the
     model class through the local transformers mappings.
  4. Instantiate with ``AutoModel.from_config`` inside
     ``accelerate.init_empty_weights()`` — every parameter is a meta tensor,
     so no weights are downloaded and RAM stays flat.
  5. Walk ``model.named_modules()`` for the true hierarchy; parameter counts
     come from ``p.numel()``, which works on meta tensors.

Nothing here downloads weights or executes remote code (``trust_remote_code``
models are rejected).
"""
from __future__ import annotations

import re

import requests
import torch
from accelerate import init_empty_weights
from fastapi import HTTPException
from transformers import AutoModel
from transformers.models.auto.configuration_auto import CONFIG_MAPPING

from .hf_schemas import (
    AnalyzeResponse,
    AnalyzeSummary,
    FlatEdge,
    FlatNode,
    TreeNode,
)

HF_BASE = "https://huggingface.co"
HTTP_TIMEOUT = 60
MAX_MODULES_FULL = 600  # beyond this, fold the tree past depth 3
COLLAPSE_DEPTH = 3

_ID_RE = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")
_URL_RE = re.compile(r"^https?://(?:www\.)?huggingface\.co/(.+?)(?:/(?:tree|blob|resolve)/.*)?/?$")

_cache: dict[str, AnalyzeResponse] = {}


def parse_model_id(raw: str) -> str:
    """Accept a bare id (``gpt2``) or a full huggingface.co URL; return the id."""
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


def _json_or_502(resp: requests.Response, what: str) -> dict:
    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(502, f"{what} is not valid JSON")
    if not isinstance(data, dict):
        raise HTTPException(502, f"{what} is not a JSON object")
    return data


def fetch_config_and_meta(model_id: str) -> tuple[dict, dict]:
    """Return (config_dict, metadata_dict), mapping HF statuses to clean errors.

    Status-code semantics (verified 2026-10-09):
      - /api/models/{id} → 200 for public AND gated repos (metadata is public);
        404, or 401 with an "Invalid username or password" body, means the
        repo does not exist (this sandbox's egress maps missing repos to 401).
      - /raw/main/config.json → 200 normally; 401/403 with an "is restricted"
        body means gated/private and needs a token.
    """
    meta_resp = _get(f"{HF_BASE}/api/models/{model_id}")
    exists: bool | None = None
    meta: dict = {}
    if meta_resp.status_code == 200:
        exists = True
        meta = _json_or_502(meta_resp, f"metadata for {model_id!r}")
    elif meta_resp.status_code == 404 or "invalid username or password" in meta_resp.text.lower():
        raise HTTPException(404, f"Model {model_id!r} not found on Hugging Face")

    cfg: dict | None = None
    last_status: int | None = None
    for url in (
        f"{HF_BASE}/{model_id}/raw/main/config.json",
        f"{HF_BASE}/{model_id}/resolve/main/config.json",
    ):
        resp = _get(url)
        last_status = resp.status_code
        if resp.status_code == 200:
            cfg = _json_or_502(resp, f"config.json for {model_id!r}")
            break
        if resp.status_code in (401, 403) and "restricted" in resp.text.lower():
            raise HTTPException(
                403,
                f"Model {model_id!r} is gated/private — a Hugging Face token is required",
            )
    if cfg is None:
        if last_status in (401, 403):
            if exists:
                raise HTTPException(
                    403,
                    f"Model {model_id!r} is gated/private — a Hugging Face token is required",
                )
            raise HTTPException(404, f"Model {model_id!r} not found on Hugging Face")
        raise HTTPException(404, f"Model {model_id!r} not found on Hugging Face")
    return cfg, meta


def resolve_model_type(cfg: dict, meta: dict, model_id: str) -> str:
    mt = cfg.get("model_type") or (meta.get("config") or {}).get("model_type")
    if mt:
        return str(mt)
    # Last resort: match the id against known model types (e.g. bert-tiny
    # ships a minimal config.json with no model_type at all).
    low = model_id.lower()
    for cand in sorted(CONFIG_MAPPING.keys(), key=len, reverse=True):
        if cand and cand in low:
            return cand
    raise HTTPException(
        422,
        f"Could not determine the architecture of {model_id!r} "
        "(no model_type in config; is it a custom architecture?)",
    )


def build_model(cfg: dict, model_type: str):
    if "auto_map" in cfg:
        raise HTTPException(
            422,
            "This model needs custom remote code (trust_remote_code) — not supported",
        )
    try:
        config_cls = CONFIG_MAPPING[model_type]
    except KeyError:
        raise HTTPException(422, f"Unknown model_type {model_type!r} in this transformers version")
    config = config_cls.from_dict(cfg)
    with init_empty_weights():
        model = AutoModel.from_config(config)
    return config, model


def _own_params(module: torch.nn.Module) -> int:
    return sum(p.numel() for p in module.parameters(recurse=False))


def _dummy_inputs(config) -> dict:
    """Minimal fake inputs for one forward pass (created inside FakeTensorMode)."""
    vocab = getattr(config, "vocab_size", None) or 32000
    v = max(2, min(int(vocab), 1000))
    kw: dict = {"input_ids": torch.randint(0, v, (1, 8), dtype=torch.long)}
    if getattr(config, "is_encoder_decoder", False):
        kw["decoder_input_ids"] = torch.randint(0, v, (1, 8), dtype=torch.long)
    return kw


def trace_flow_edges(cfg: dict, model_type: str) -> list[FlatEdge]:
    """True data-flow edges from a shape-only forward pass.

    Rebuilds the model under FakeTensorMode (shapes only — no real weights,
    no real compute), hooks every leaf module, runs one forward pass on
    dummy inputs, and connects consecutively-executed leaves. Returns []
    when tracing is not possible for this architecture; callers then keep
    the containment-hierarchy edges.
    """
    try:
        from torch._subclasses.fake_tensor import FakeTensorMode

        config_cls = CONFIG_MAPPING[model_type]
        order: list[str] = []
        handles = []

        def rec(name: str):
            def hook(mod, inputs, output):
                order.append(name)

            return hook

        with FakeTensorMode():
            config = config_cls.from_dict(cfg)
            model = AutoModel.from_config(config)
            for dotted, mod in model.named_modules():
                if dotted and len(list(mod.children())) == 0:
                    handles.append(mod.register_forward_hook(rec(dotted)))
            model.eval()
            with torch.no_grad():
                model(**_dummy_inputs(config))
        for h in handles:
            h.remove()

        seen: set[tuple[str, str]] = set()
        edges: list[FlatEdge] = []
        for a, b in zip(order, order[1:]):
            if a != b and (a, b) not in seen:
                seen.add((a, b))
                edges.append(FlatEdge(source=a, target=b))
        return edges
    except Exception:
        return []


def build_tree(model: torch.nn.Module) -> tuple[dict, int]:
    """Nested dict tree from named_modules(); returns (root, module_count)."""
    nodes: dict[str, dict] = {}
    for dotted, mod in model.named_modules():
        nodes[dotted] = {
            "id": dotted or "model",
            "name": dotted.split(".")[-1] or "model",
            "type": type(mod).__name__,
            "params": _own_params(mod),
            "depth": dotted.count(".") + (1 if dotted else 0),
            "child_count": 0,
            "children": [],
        }
    root = nodes[""]
    for dotted, node in nodes.items():
        if dotted == "":
            continue
        parent = dotted.rpartition(".")[0]
        nodes[parent]["children"].append(node)
    return root, len(nodes)


def _descendant_count(node: dict) -> int:
    return sum(1 + _descendant_count(c) for c in node["children"])


def collapse_tree(node: dict, max_depth: int = COLLAPSE_DEPTH) -> None:
    """Fold everything deeper than max_depth into child_count counters."""
    if node["depth"] >= max_depth:
        if node["children"]:
            node["child_count"] = _descendant_count(node)
            node["children"] = []
        return
    for child in node["children"]:
        collapse_tree(child, max_depth)


def _to_tree_node(node: dict) -> TreeNode:
    return TreeNode(
        id=node["id"],
        name=node["name"],
        type=node["type"],
        params=node["params"],
        depth=node["depth"],
        child_count=node["child_count"],
        children=[_to_tree_node(c) for c in node["children"]],
        value=node.get("value"),
    )


MAX_CONFIG_NODES = 800
MAX_CONFIG_DEPTH = 6
MAX_LIST_ITEMS = 50


def _val_repr(v) -> str:
    r = repr(v)
    return r if len(r) <= 64 else r[:61] + "…"


def build_config_tree(cfg: dict) -> tuple[dict, int]:
    """Nested-dict tree mirroring build_tree(), but from config.json itself.

    Used when the model is not a transformers architecture (custom model_type
    or custom remote code): there is no PyTorch module graph to walk, so the
    config structure becomes the browsable hierarchy. Same dict shape as
    build_tree() so flatten_tree()/collapse_tree()/_to_tree_node() apply.
    """
    count = 0

    def visit(name: str, node_id: str, depth: int, v) -> dict | None:
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
            node["value"] = _val_repr(v)
        return node

    root = visit("config", "config", 0, cfg)
    assert root is not None
    return root, count


def _cfg_int(cfg: dict, *names) -> int | None:
    for n in names:
        v = cfg.get(n)
        if isinstance(v, int) and not isinstance(v, bool):
            return v
    return None


def _config_only_response(model_id: str, cfg: dict, meta: dict, reason: str) -> AnalyzeResponse:
    """Successful response for non-transformers architectures: config tree only."""
    root, total = build_config_tree(cfg)
    collapsed = False
    if total > MAX_MODULES_FULL:
        collapse_tree(root)
        collapsed = True
    flat_nodes, flat_edges = flatten_tree(root)
    summary = AnalyzeSummary(
        model_type=str(cfg.get("model_type")) if cfg.get("model_type") else None,
        architectures=[str(a) for a in (cfg.get("architectures") or [])],
        n_parameters=0,
        hidden_size=_cfg_int(cfg, "hidden_size", "d_model", "n_embd"),
        num_hidden_layers=_cfg_int(cfg, "num_hidden_layers", "n_layer", "num_layers"),
        num_attention_heads=_cfg_int(cfg, "num_attention_heads", "n_head", "num_heads"),
        intermediate_size=_cfg_int(cfg, "intermediate_size", "d_ff"),
        vocab_size=_cfg_int(cfg, "vocab_size"),
        max_position_embeddings=_cfg_int(cfg, "max_position_embeddings", "n_positions"),
        pipeline_tag=meta.get("pipeline_tag"),
    )
    return AnalyzeResponse(
        model_id=model_id,
        summary=summary,
        tree=[_to_tree_node(root)],
        nodes=flat_nodes,
        edges=flat_edges,
        collapsed=collapsed,
        total_modules=total,
        resolved=False,
        note=(
            f"{reason} — this is not a transformers/PyTorch architecture, "
            "so the tree shows the model's config.json structure instead of a layer graph."
        ),
    )


def flatten_tree(root: dict) -> tuple[list[FlatNode], list[FlatEdge]]:
    nodes: list[FlatNode] = []
    edges: list[FlatEdge] = []

    def visit(n: dict, parent_id: str | None) -> None:
        nodes.append(
            FlatNode(id=n["id"], label=n["name"], type=n["type"], depth=n["depth"], params=n["params"])
        )
        if parent_id is not None:
            edges.append(FlatEdge(source=parent_id, target=n["id"]))
        for c in n["children"]:
            visit(c, n["id"])

    visit(root, None)
    return nodes, edges


def _first(config, *names):
    for name in names:
        v = getattr(config, name, None)
        if v is not None:
            return v
    return None


def summarize(config, meta: dict, n_params: int) -> AnalyzeSummary:
    layers = _first(config, "num_hidden_layers", "n_layer")
    if layers is None:
        # encoder-decoder families: T5/BART-style configs split the counts
        enc = _first(config, "num_encoder_layers", "num_layers")
        dec = _first(config, "num_decoder_layers")
        if enc is not None or dec is not None:
            layers = (enc or 0) + (dec or 0)
        else:
            layers = _first(config, "num_layers")
    return AnalyzeSummary(
        model_type=getattr(config, "model_type", None),
        architectures=list(getattr(config, "architectures", None) or []),
        n_parameters=n_params,
        hidden_size=_first(config, "hidden_size", "d_model", "n_embd"),
        num_hidden_layers=layers,
        num_attention_heads=_first(config, "num_attention_heads", "n_head", "num_heads"),
        intermediate_size=_first(config, "intermediate_size", "d_ff"),
        vocab_size=_first(config, "vocab_size"),
        max_position_embeddings=_first(config, "max_position_embeddings", "n_positions"),
        pipeline_tag=meta.get("pipeline_tag"),
    )


def analyze(raw_id: str) -> AnalyzeResponse:
    model_id = parse_model_id(raw_id)
    if model_id in _cache:
        return _cache[model_id]

    cfg, meta = fetch_config_and_meta(model_id)
    try:
        model_type = resolve_model_type(cfg, meta, model_id)
        config, model = build_model(cfg, model_type)
    except HTTPException as exc:
        # Custom architectures (unknown model_type, remote code): no layer
        # graph exists — fall back to a browsable config.json tree instead
        # of failing the analysis outright.
        if exc.status_code != 422:
            raise
        reason = str(exc.detail)
    except Exception as exc:  # noqa: BLE001 — exotic configs degrade to config view
        reason = f"Could not instantiate the architecture ({type(exc).__name__}: {exc})"
    else:
        reason = None
    if reason is not None:
        result = _config_only_response(model_id, cfg, meta, reason)
        _cache[model_id] = result
        return result

    with torch.no_grad():
        n_params = sum(p.numel() for p in model.parameters())

    root, total_modules = build_tree(model)
    collapsed = False
    if total_modules > MAX_MODULES_FULL:
        collapse_tree(root)
        collapsed = True
    flat_nodes, flat_edges = flatten_tree(root)
    flow_edges = trace_flow_edges(cfg, model_type)

    result = AnalyzeResponse(
        model_id=model_id,
        summary=summarize(config, meta, n_params),
        tree=[_to_tree_node(root)],
        nodes=flat_nodes,
        edges=flat_edges,
        collapsed=collapsed,
        total_modules=total_modules,
        flow_edges=flow_edges,
    )
    _cache[model_id] = result
    return result
