/** Glowing data pulses that travel along the edges — the network "breathing". */
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import type { EdgeSeg } from './layout'

export type { EdgeSeg }

function Dot({ a, b, speed, offset }: { a: THREE.Vector3; b: THREE.Vector3; speed: number; offset: number }) {
  const ref = useRef<THREE.Mesh>(null!)
  const t = useRef(offset)
  useFrame((_, rawDt) => {
    const dt = Math.min(rawDt, 0.05)
    t.current = (t.current + dt * speed) % 1
    ref.current.position.lerpVectors(a, b, t.current)
  })
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.11, 12, 12]} />
      <meshBasicMaterial color="#ffa76b" toneMapped={false} />
    </mesh>
  )
}

export function FlowDots({ segments }: { segments: EdgeSeg[] }) {
  const dots = useMemo(
    () =>
      segments.flatMap((s, i) =>
        [0, 1].map((k) => ({
          key: `${i}-${k}`,
          a: new THREE.Vector3(...s.a),
          b: new THREE.Vector3(...s.b),
          speed: 0.32,
          offset: (i * 0.37 + k * 0.5) % 1,
        })),
      ),
    [segments],
  )
  return (
    <group>
      {dots.map((d) => (
        <Dot key={d.key} a={d.a} b={d.b} speed={d.speed} offset={d.offset} />
      ))}
    </group>
  )
}
