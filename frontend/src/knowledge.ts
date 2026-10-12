/** Mini curated knowledge base (M0 seed).
 *  M1 promotes this to knowledge/layers/*.yaml served by the backend.
 *  Keyed by node label; falls back to op name.
 */
export interface LayerDoc {
  tagline: string
  how: string
  watchOut?: string
}

export const LAYER_DOCS: Record<string, LayerDoc> = {
  Input: {
    tagline: 'Where data enters the network.',
    how: 'The input layer just holds the incoming tensor — here a 1×28×28 grayscale image. It has no parameters and performs no computation.',
  },
  Conv2d: {
    tagline: 'Learns spatial features: edges → textures → parts.',
    how: 'Slides small learned filters (kernels) across the image. Each filter produces one feature map highlighting where its pattern occurs. Early layers learn edges and blobs; deeper ones learn textures and object parts.',
    watchOut: 'Output size depends on kernel, stride and padding — change one and every downstream shape shifts.',
  },
  ReLU: {
    tagline: 'The non-linearity that lets networks learn curves.',
    how: 'Applies max(0, x) elementwise: negatives become zero, positives pass through. Without activations like this, a whole stack of layers would collapse into a single linear function.',
    watchOut: 'Neurons can "die" (stuck at zero) if their inputs stay negative — variants like LeakyReLU/GELU address this.',
  },
  MaxPool2d: {
    tagline: 'Downsamples by keeping only the strongest signal.',
    how: 'Takes the maximum over each 2×2 window, halving height and width. This builds translation invariance ("a cat shifted 2px is still a cat") and cuts computation for later layers.',
  },
  Flatten: {
    tagline: 'Reshapes the 3D feature maps into a 1D vector.',
    how: 'Unrolls [C, H, W] into a single vector so fully-connected layers can consume it. Pure reshaping — no parameters, no learning.',
  },
  Linear: {
    tagline: 'A learned weighted vote: y = Wx + b.',
    how: 'Every output is a weighted sum of every input plus a bias. This is where the network mixes all extracted features into class scores. Most of the model\'s parameters usually live here.',
    watchOut: 'Parameter count explodes with input size: (in_features + 1) × out_features.',
  },
  Softmax: {
    tagline: 'Turns raw scores into probabilities.',
    how: 'Exponentiates each logit and normalizes so all 10 outputs sum to 1. The largest value is the predicted digit; the spread expresses the model\'s confidence.',
  },
}

export function docFor(label: string, op: string): LayerDoc | undefined {
  return LAYER_DOCS[label] ?? LAYER_DOCS[op]
}
