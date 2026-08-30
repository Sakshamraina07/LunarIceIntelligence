/**
 * CameraRig.tsx
 * Drives the cinematic descent from a full-Moon view to a south-pole
 * reconnaissance view, keyed off scroll progress (0..1).
 *
 * - progress < HERO_LIMIT: manual OrbitControls (drag / zoom / pan) with a slow
 *   idle auto-rotate — the interactive "full Moon" hero.
 * - progress >= HERO_LIMIT: OrbitControls is disabled and the camera is lerped
 *   along scripted keyframes down to the pole, so the story stays on-rails.
 *
 * Camera work happens entirely in useFrame via refs — no React re-renders.
 */
import { useEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';

const HERO_LIMIT = 0.03;

interface Keyframe {
  p: number;
  pos: [number, number, number];
  look: [number, number, number];
}

// Full Moon (slightly above) -> sweep beneath -> close recon over the south pole.
const KEYFRAMES: Keyframe[] = [
  { p: 0.0, pos: [0.0, 1.4, 6.2], look: [0, 0, 0] },
  { p: 0.3, pos: [1.2, -0.6, 5.2], look: [0, -0.6, 0] },
  { p: 0.55, pos: [0.6, -2.4, 3.8], look: [0, -1.4, 0] },
  { p: 0.78, pos: [0.2, -3.4, 2.9], look: [0, -1.85, 0] },
  { p: 1.0, pos: [0.0, -3.9, 2.5], look: [0, -2.0, 0] },
];

function sampleKeyframes(p: number, outPos: THREE.Vector3, outLook: THREE.Vector3) {
  let a = KEYFRAMES[0];
  let b = KEYFRAMES[KEYFRAMES.length - 1];
  for (let i = 0; i < KEYFRAMES.length - 1; i++) {
    if (p >= KEYFRAMES[i].p && p <= KEYFRAMES[i + 1].p) {
      a = KEYFRAMES[i];
      b = KEYFRAMES[i + 1];
      break;
    }
  }
  const span = b.p - a.p || 1;
  const t = THREE.MathUtils.clamp((p - a.p) / span, 0, 1);
  const e = t * t * (3 - 2 * t); // smoothstep easing
  outPos.set(
    THREE.MathUtils.lerp(a.pos[0], b.pos[0], e),
    THREE.MathUtils.lerp(a.pos[1], b.pos[1], e),
    THREE.MathUtils.lerp(a.pos[2], b.pos[2], e)
  );
  outLook.set(
    THREE.MathUtils.lerp(a.look[0], b.look[0], e),
    THREE.MathUtils.lerp(a.look[1], b.look[1], e),
    THREE.MathUtils.lerp(a.look[2], b.look[2], e)
  );
}

export function CameraRig({ progress }: { progress: React.MutableRefObject<number> }) {
  const controls = useRef<OrbitControlsImpl>(null);
  const { camera } = useThree();
  const targetPos = useRef(new THREE.Vector3(0, 1.4, 6.2));
  const targetLook = useRef(new THREE.Vector3(0, 0, 0));
  const currentLook = useRef(new THREE.Vector3(0, 0, 0));

  useEffect(() => {
    camera.position.set(0, 1.4, 6.2);
    camera.lookAt(0, 0, 0);
  }, [camera]);

  useFrame((_, delta) => {
    const p = progress.current;
    const hero = p < HERO_LIMIT;
    const c = controls.current;
    if (c) c.enabled = hero;

    if (hero) {
      // OrbitControls (with autoRotate) owns the camera; just track its target.
      if (c) currentLook.current.copy(c.target);
      return;
    }

    sampleKeyframes(p, targetPos.current, targetLook.current);
    const k = 1 - Math.pow(0.0016, delta); // frame-rate-independent damping
    camera.position.lerp(targetPos.current, k);
    currentLook.current.lerp(targetLook.current, k);
    camera.lookAt(currentLook.current);
  });

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enablePan
      enableZoom
      autoRotate
      autoRotateSpeed={0.35}
      minDistance={3.2}
      maxDistance={9}
      enableDamping
      dampingFactor={0.08}
    />
  );
}
