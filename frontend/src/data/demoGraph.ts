/** Local fallback copy of the backend demo graph.
 *  Used when the API is unreachable (e.g. opening the frontend standalone).
 *  Keep in sync with backend/app/demo_graphs.py.
 */
import type { ModelGraph } from '../types'

const N = (
  id: string, op: string, label: string, family: ModelGraph['nodes'][number]['family'],
  attrs: Record<string, unknown> = {}, params = 0,
  in_shape: number[] | null = null, out_shape: number[] | null = null,
) => ({ id, op, label, family, attrs, params, in_shape, out_shape })

export const DEMO_GRAPH: ModelGraph = {
  name: 'lenet-mnist',
  description: 'LeNet-style CNN: 28×28 digit image → 10 class probabilities.',
  nodes: [
    N('input', 'Input', 'Input', 'input', {}, 0, [1, 1, 28, 28], [1, 1, 28, 28]),
    N('conv1', 'Conv', 'Conv2d', 'convolution', { kernel: [5, 5], in_channels: 1, out_channels: 6, stride: [1, 1] }, 156, [1, 1, 28, 28], [1, 6, 24, 24]),
    N('relu1', 'Relu', 'ReLU', 'activation', {}, 0, [1, 6, 24, 24], [1, 6, 24, 24]),
    N('pool1', 'MaxPool', 'MaxPool2d', 'pooling', { kernel: [2, 2], stride: [2, 2] }, 0, [1, 6, 24, 24], [1, 6, 12, 12]),
    N('conv2', 'Conv', 'Conv2d', 'convolution', { kernel: [5, 5], in_channels: 6, out_channels: 16, stride: [1, 1] }, 2416, [1, 6, 12, 12], [1, 16, 8, 8]),
    N('relu2', 'Relu', 'ReLU', 'activation', {}, 0, [1, 16, 8, 8], [1, 16, 8, 8]),
    N('pool2', 'MaxPool', 'MaxPool2d', 'pooling', { kernel: [2, 2], stride: [2, 2] }, 0, [1, 16, 8, 8], [1, 16, 4, 4]),
    N('flatten', 'Flatten', 'Flatten', 'reshape', {}, 0, [1, 16, 4, 4], [1, 256]),
    N('fc1', 'Gemm', 'Linear', 'linear', { in_features: 256, out_features: 120 }, 30840, [1, 256], [1, 120]),
    N('relu3', 'Relu', 'ReLU', 'activation', {}, 0, [1, 120], [1, 120]),
    N('fc2', 'Gemm', 'Linear', 'linear', { in_features: 120, out_features: 84 }, 10164, [1, 120], [1, 84]),
    N('fc3', 'Gemm', 'Linear', 'linear', { in_features: 84, out_features: 10 }, 850, [1, 84], [1, 10]),
    N('output', 'Softmax', 'Softmax', 'output', { dim: 1 }, 0, [1, 10], [1, 10]),
  ],
  edges: [],
  flowEdges: [],
}

const ids = DEMO_GRAPH.nodes.map((n) => n.id)
DEMO_GRAPH.edges = ids.slice(0, -1).map((a, i) => ({
  source: a,
  target: ids[i + 1],
  shape: DEMO_GRAPH.nodes[i + 1].out_shape,
}))
