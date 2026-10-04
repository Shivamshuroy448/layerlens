"""Demo graphs — hardcoded architectures served for M0/M1.

In M2 this becomes a gallery of famous architectures converted to ONNX.
Each demo is a valid ModelGraph any frontend can render.
"""
from .schemas import GraphEdge, GraphNode, ModelGraph


def _n(id: str, op: str, label: str, family: str, attrs: dict | None = None,
       params: int = 0, in_shape: list[int] | None = None,
       out_shape: list[int] | None = None) -> GraphNode:
    return GraphNode(id=id, op=op, label=label, family=family,  # type: ignore[arg-type]
                     attrs=attrs or {}, params=params,
                     in_shape=in_shape, out_shape=out_shape)


def _chain(ids: list[str], shapes: list[list[int] | None]) -> list[GraphEdge]:
    return [GraphEdge(source=a, target=b, shape=s)
            for a, b, s in zip(ids, ids[1:], shapes[1:])]


def lenet_mnist() -> ModelGraph:
    """LeNet-style CNN for MNIST — the classic 'hello world' of vision models."""
    nodes = [
        _n("input", "Input", "Input", "input", in_shape=[1, 1, 28, 28], out_shape=[1, 1, 28, 28]),
        _n("conv1", "Conv", "Conv2d", "convolution",
           {"kernel": [5, 5], "in_channels": 1, "out_channels": 6, "stride": [1, 1]},
           params=(5 * 5 * 1 + 1) * 6, in_shape=[1, 1, 28, 28], out_shape=[1, 6, 24, 24]),
        _n("relu1", "Relu", "ReLU", "activation", in_shape=[1, 6, 24, 24], out_shape=[1, 6, 24, 24]),
        _n("pool1", "MaxPool", "MaxPool2d", "pooling",
           {"kernel": [2, 2], "stride": [2, 2]}, in_shape=[1, 6, 24, 24], out_shape=[1, 6, 12, 12]),
        _n("conv2", "Conv", "Conv2d", "convolution",
           {"kernel": [5, 5], "in_channels": 6, "out_channels": 16, "stride": [1, 1]},
           params=(5 * 5 * 6 + 1) * 16, in_shape=[1, 6, 12, 12], out_shape=[1, 16, 8, 8]),
        _n("relu2", "Relu", "ReLU", "activation", in_shape=[1, 16, 8, 8], out_shape=[1, 16, 8, 8]),
        _n("pool2", "MaxPool", "MaxPool2d", "pooling",
           {"kernel": [2, 2], "stride": [2, 2]}, in_shape=[1, 16, 8, 8], out_shape=[1, 16, 4, 4]),
        _n("flatten", "Flatten", "Flatten", "reshape", in_shape=[1, 16, 4, 4], out_shape=[1, 256]),
        _n("fc1", "Gemm", "Linear", "linear",
           {"in_features": 256, "out_features": 120},
           params=(256 + 1) * 120, in_shape=[1, 256], out_shape=[1, 120]),
        _n("relu3", "Relu", "ReLU", "activation", in_shape=[1, 120], out_shape=[1, 120]),
        _n("fc2", "Gemm", "Linear", "linear",
           {"in_features": 120, "out_features": 84},
           params=(120 + 1) * 84, in_shape=[1, 120], out_shape=[1, 84]),
        _n("fc3", "Gemm", "Linear", "linear",
           {"in_features": 84, "out_features": 10},
           params=(84 + 1) * 10, in_shape=[1, 84], out_shape=[1, 10]),
        _n("output", "Softmax", "Softmax", "output",
           {"dim": 1}, in_shape=[1, 10], out_shape=[1, 10]),
    ]
    ids = [n.id for n in nodes]
    shapes = [n.out_shape for n in nodes]
    return ModelGraph(
        name="lenet-mnist",
        description="LeNet-style CNN: 28×28 digit image → 10 class probabilities.",
        nodes=nodes,
        edges=_chain(ids, shapes),
    )


DEMOS: dict[str, ModelGraph] = {"lenet-mnist": lenet_mnist()}
