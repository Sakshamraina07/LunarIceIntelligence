/**
 * LunarScene.tsx
 * Assembles the full 3D landing scene: space background, restrained starfield,
 * the DEM-displaced Moon with its south-polar science overlay, cinematic
 * lighting, and the scroll-driven camera rig. Kept intentionally small and
 * readable — no bespoke render engine.
 */
import { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { Moon } from './Moon';
import { Starfield } from './Starfield';
import { SouthPoleTargets } from './SouthPoleTargets';
import { CameraRig } from './CameraRig';
import type { LunarTarget } from '../data/targets';

/** Key sun light whose grazing angle drifts subtly as we near the pole. */
function SceneLighting({ progress }: { progress: React.MutableRefObject<number> }) {
  const sun = useRef<THREE.DirectionalLight>(null);
  useFrame(() => {
    if (sun.current) {
      const p = progress.current;
      // Low grazing polar illumination that swings slightly during descent.
      const angle = 0.9 + p * 0.6;
      sun.current.position.set(Math.cos(angle) * 6, 1.5 - p * 2.2, Math.sin(angle) * 6);
    }
  });
  return (
    <>
      <ambientLight intensity={0.06} color="#22384a" />
      <directionalLight ref={sun} intensity={2.1} color="#fff6ec" position={[5, 1.5, 3]} />
      {/* cool cyan fill to sculpt the shadow side without flattening relief */}
      <directionalLight intensity={0.25} color="#2fb6d6" position={[-5, -2, -4]} />
    </>
  );
}

interface Props {
  progress: React.MutableRefObject<number>;
  targets: LunarTarget[];
  selectedId: string | null;
  onSelect: (t: LunarTarget) => void;
}

export function LunarScene({ progress, targets, selectedId, onSelect }: Props) {
  const moonRef = useRef<THREE.Group>(null);
  return (
    <Canvas
      dpr={[1, 2]}
      camera={{ position: [0, 1.4, 6.2], fov: 42, near: 0.1, far: 200 }}
      gl={{ antialias: true, powerPreference: 'high-performance' }}
      style={{ position: 'fixed', inset: 0, width: '100%', height: '100%' }}
    >
      <color attach="background" args={['#03060c']} />
      <fog attach="fog" args={['#03060c', 12, 30]} />
      <Suspense fallback={null}>
        <SceneLighting progress={progress} />
        <Starfield />
        <Moon ref={moonRef} progress={progress}>
          <SouthPoleTargets
            targets={targets}
            progress={progress}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        </Moon>
      </Suspense>
      <CameraRig progress={progress} />
    </Canvas>
  );
}
