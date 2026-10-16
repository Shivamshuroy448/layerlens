import { useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PlacedNode } from './layout'
import { FAMILY_COLORS } from './layout'
import { useLens } from '../store'

interface Props {
  placed: PlacedNode
  /** Hide the floating label unless the node is shallow, hovered or selected. */
  sparseLabels?: boolean
}

export function LayerNode({ placed, sparseLabels = false }: Props) {
  const { node, position, size } = placed
  const { selectedId, select } = useLens()
  const [hovered, setHovered] = useState(false)
  const group = useRef<THREE.Group>(null!)
  const mat = useRef<THREE.MeshStandardMaterial>(null!)
  const selected = selectedId === node.id
  const color = FAMILY_COLORS[node.family]
  const depth = (node.attrs.depth as number | undefined) ?? 0
  const showLabel = !sparseLabels || selected || hovered || depth <= 1

  const edgeGeom = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(size[0], size[1], size[2])),
    [size],
  )

  useFrame((state, rawDt) => {
    const dt = Math.min(rawDt, 0.05)
    // gentle grow on hover / select
    const s = THREE.MathUtils.damp(
      group.current.scale.x, hovered || selected ? 1.12 : 1, 10, dt,
    )
    group.current.scale.setScalar(s)
    // glow: idle shimmer, hover lift, selected pulse
    const pulse = selected
      ? 0.65 + Math.sin(state.clock.elapsedTime * 3.5) * 0.28
      : hovered
        ? 0.34
        : 0.08
    mat.current.emissiveIntensity = THREE.MathUtils.damp(
      mat.current.emissiveIntensity, pulse, 10, dt,
    )
  })

  return (
    <group ref={group} position={position}>
      <mesh
        onClick={(e) => {
          e.stopPropagation()
          select(selected ? null : node.id)
        }}
        onPointerOver={(e) => {
          e.stopPropagation()
          setHovered(true)
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          setHovered(false)
          document.body.style.cursor = 'auto'
        }}
      >
        <boxGeometry args={size} />
        <meshStandardMaterial
          ref={mat}
          color={color}
          emissive={selected || hovered ? '#ffffff' : color}
          emissiveIntensity={0.06}
          roughness={0.34}
          metalness={0.22}
          transparent
          opacity={0.94}
        />
      </mesh>
      <lineSegments geometry={edgeGeom}>
        <lineBasicMaterial color={selected ? '#ffffff' : '#0b1020'} transparent opacity={0.9} />
      </lineSegments>
      {showLabel && (
        <Html position={[0, size[1] / 2 + 0.6, 0]} center distanceFactor={14}>
          <div className={`node-label ${selected ? 'selected' : ''}`}>{node.label}</div>
        </Html>
      )}
    </group>
  )
}
