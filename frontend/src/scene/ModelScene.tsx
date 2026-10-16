import { useMemo, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { Line, OrbitControls } from '@react-three/drei'
import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing'
import type { ModelGraph } from '../types'
import { edgeSegments, layoutSequential, layoutSerpentine, sceneRadius } from './layout'
import { LayerNode } from './LayerNode'
import { CameraRig, CAMERA_START } from './CameraRig'
import { FlowDots } from './FlowDots'
import { useLens } from '../store'

interface Props {
  graph: ModelGraph
  autoRotate: boolean
  /** Real HF graphs use the serpentine grid; the M0 demo keeps the row. */
  serpentine?: boolean
  /** Hide labels except shallow/hovered/selected nodes (large graphs). */
  sparseLabels?: boolean
  /** Edge set to draw — defaults to the hierarchy edges. Pass the flow edges for the data-flow view. */
  edges?: { source: string; target: string; shape: number[] | null }[]
}

export function ModelScene({ graph, autoRotate, serpentine = false, sparseLabels = false, edges }: Props) {
  const placed = useMemo(
    () => (serpentine ? layoutSerpentine(graph) : layoutSequential(graph)),
    [graph, serpentine],
  )
  const [introDone, setIntroDone] = useState(false)
  const { selectedId } = useLens()

  const focus = useMemo<[number, number, number] | null>(() => {
    const p = placed.find((p) => p.node.id === selectedId)
    return p ? p.position : null
  }, [placed, selectedId])

  const segments = useMemo(
    () => edgeSegments(placed, edges ?? graph.edges),
    [placed, edges, graph.edges],
  )

  // Frame the camera on the graph's actual extent for large HF models.
  const framing = useMemo(() => {
    if (!serpentine) return undefined
    const r = sceneRadius(placed)
    return {
      start: [r * 1.1, r * 0.66, r * 1.1] as [number, number, number],
      end: [r * 0.42, r * 0.24, r * 0.42] as [number, number, number],
      far: r * 2.8,
      ground: r * 1.6,
    }
  }, [placed, serpentine])

  const fogFar = framing?.far ?? 80
  const groundR = framing?.ground ?? 48

  return (
    <Canvas camera={{ position: CAMERA_START, fov: 45 }} dpr={[1, 2]} gl={{ antialias: true }}>
      <color attach="background" args={['#07080b']} />
      <fog attach="fog" args={['#07080b', fogFar * 0.4, fogFar]} />

      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 14, 8]} intensity={1.25} />
      <directionalLight position={[-8, -4, -10]} intensity={0.3} color="#9db4d8" />

      {placed.map((p) => (
        <LayerNode key={p.node.id} placed={p} sparseLabels={sparseLabels} />
      ))}
      {segments.map((s, i) => (
        <Line key={i} points={[s.a, s.b]} color="#7d8798" lineWidth={1.5} transparent opacity={0.42} />
      ))}
      <FlowDots segments={segments} />

      {/* ground disc + faint grid fading into the dark */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -4.6, 0]}>
        <circleGeometry args={[groundR, 64]} />
        <meshStandardMaterial color="#090b10" roughness={0.95} metalness={0.1} transparent opacity={0.6} />
      </mesh>
      <gridHelper args={[groundR * 2, Math.round(groundR), '#1b2334', '#0e141f']} position={[0, -4.55, 0]} />

      <CameraRig focus={focus} onIntroDone={() => setIntroDone(true)} start={framing?.start} end={framing?.end} />
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        minDistance={4}
        maxDistance={Math.max(70, fogFar)}
        autoRotate={autoRotate}
        autoRotateSpeed={0.7}
        enabled={introDone}
      />

      <EffectComposer>
        <Bloom intensity={0.5} luminanceThreshold={0.45} luminanceSmoothing={0.2} mipmapBlur />
        <Vignette eskil={false} offset={0.3} darkness={0.38} />
      </EffectComposer>
    </Canvas>
  )
}
