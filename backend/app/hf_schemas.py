"""Pydantic schemas for POST /api/analyze — real Hugging Face architectures.

This is separate from schemas.py (the M0 ModelGraph contract) because the
analyze response carries richer, HF-specific data: the config summary and the
true nested module tree. The frontend adapts this into a ModelGraph for the
3D scene.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeSummary(BaseModel):
    model_type: str | None = Field(default=None, description="HF model_type, e.g. 'bert'")
    architectures: list[str] = Field(default_factory=list, description="config.architectures")
    n_parameters: int = Field(default=0, description="Total params counted on meta tensors")
    hidden_size: int | None = None
    num_hidden_layers: int | None = None
    num_attention_heads: int | None = None
    intermediate_size: int | None = None
    vocab_size: int | None = None
    max_position_embeddings: int | None = None
    pipeline_tag: str | None = Field(default=None, description="HF pipeline tag, e.g. 'text-generation'")


class TreeNode(BaseModel):
    id: str = Field(description="Full dotted module path, e.g. 'bert.encoder.layer.0.attention'")
    name: str = Field(description="Short module name, e.g. 'attention'")
    type: str = Field(description="Python class name, e.g. 'BertSelfAttention'")
    params: int = Field(description="This module's OWN params (not descendants)")
    depth: int = Field(description="0 = model root")
    child_count: int = Field(default=0, description="Folded descendants when tree was collapsed")
    children: list["TreeNode"] = Field(default_factory=list)
    value: str | None = Field(
        default=None,
        description="Scalar config value for config-only trees, e.g. \"'gqa'\"",
    )


TreeNode.model_rebuild()


class FlatNode(BaseModel):
    id: str
    label: str
    type: str
    depth: int
    params: int


class FlatEdge(BaseModel):
    source: str
    target: str


class AnalyzeResponse(BaseModel):
    model_id: str
    summary: AnalyzeSummary
    tree: list[TreeNode] = Field(description="Nested module hierarchy (root wrapped in a list)")
    nodes: list[FlatNode] = Field(description="Flat nodes for the 3D scene")
    edges: list[FlatEdge] = Field(description="Parent→child data-flow edges")
    collapsed: bool = Field(default=False, description="True when depth>3 was folded (module cap hit)")
    total_modules: int = Field(default=0, description="Module count before collapsing")
    flow_edges: list[FlatEdge] = Field(
        default_factory=list,
        description="True data-flow edges from a shape-only forward pass "
        "(consecutively-executed leaf modules); empty when tracing failed",
    )
    resolved: bool = Field(
        default=True,
        description="False when the architecture is not a transformers model "
        "and the tree is the config.json structure instead of a layer graph",
    )
    note: str | None = Field(
        default=None, description="Human-readable explanation when resolved is False"
    )
