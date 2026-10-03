"""ModelGraph schemas — THE contract between backend and frontend.

Every model, regardless of source framework, is converted into a
ModelGraph: a list of layer nodes and the data-flow edges between them.
The 3D frontend only ever speaks this format.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str = Field(description="Unique node id, e.g. 'conv1'")
    op: str = Field(description="ONNX-style op name, e.g. 'Conv', 'Relu', 'Gemm'")
    label: str = Field(description="Human-friendly label, e.g. 'Conv2d'")
    family: Literal[
        "input", "convolution", "linear", "activation",
        "pooling", "normalization", "reshape", "recurrent",
        "attention", "output", "other",
    ] = Field(description="Layer family — drives 3D coloring")
    attrs: dict[str, Any] = Field(
        default_factory=dict,
        description="Layer config, e.g. {'kernel': [3,3], 'out_channels': 64}",
    )
    params: int = Field(default=0, description="Trainable parameter count")
    in_shape: list[int] | None = Field(
        default=None, description="Input tensor shape, e.g. [1, 3, 32, 32]"
    )
    out_shape: list[int] | None = Field(
        default=None, description="Output tensor shape"
    )


class GraphEdge(BaseModel):
    source: str = Field(description="Source node id")
    target: str = Field(description="Target node id")
    shape: list[int] | None = Field(
        default=None, description="Tensor shape flowing along this edge"
    )


class ModelGraph(BaseModel):
    name: str = Field(description="Model name, e.g. 'lenet-mnist'")
    description: str = Field(default="", description="One-line model description")
    nodes: list[GraphNode]
    edges: list[GraphEdge]

    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}
