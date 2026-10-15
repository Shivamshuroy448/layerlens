/** Cinematic camera: slow fly-in on load, then gently follows the selected layer. */
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame, useThree } from '@react-three/fiber'

const START: [number, number, number] = [36, 22, 36]
const END: [number, number, number] = [13, 7.5, 13]

const easeInOut = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2

interface Props {
  focus: [number, number, number] | null
  onIntroDone: () => void
  start?: [number, number, number]
  end?: [number, number, number]
}

export function CameraRig({ focus, onIntroDone, start = START, end = END }: Props) {
  const camera = useThree((s) => s.camera)
  const controls = useThree((s) => s.controls) as unknown as {
    target: THREE.Vector3
  } | null
  const intro = useRef(0)
  const done = useRef(false)
  const desired = useMemo(() => new THREE.Vector3(), [])
  const startV = useMemo(() => new THREE.Vector3(...start), [start])
  const endV = useMemo(() => new THREE.Vector3(...end), [end])

  useFrame((_, rawDt) => {
    const dt = Math.min(rawDt, 0.05)
    if (intro.current < 1) {
      intro.current = Math.min(1, intro.current + dt / 3.4)
      camera.position.lerpVectors(startV, endV, easeInOut(intro.current))
      camera.lookAt(0, 0, 0)
      if (intro.current >= 1 && !done.current) {
        done.current = true
        onIntroDone()
      }
    } else if (controls) {
      const f = focus ?? [0, 0, 0]
      desired.set(f[0], f[1], f[2])
      controls.target.lerp(desired, 1 - Math.exp(-3.2 * dt))
    }
  })
  return null
}

export const CAMERA_START: [number, number, number] = START
