/**
 * SouthPoleTargets.tsx
 * Data-driven scientific overlay for the south-polar region: candidate crater
 * markers, a permanently-shadowed pole cap, and a demo landing site + rover
 * route. All values come from data/targets.ts (or the backend via
 * services/missionData) — nothing scientific is computed here.
 *
 * Rendered as children of the Moon surface group, so overlays rotate with the
 * body and stay pinned to their coordinates. Everything fades in as the camera
 * descends toward the pole (progress -> 1) so the hero stays uncluttered.
 */
import { useMemo, useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Billboard, Text, Line } from '@react-three/drei';
import * as THREE from 'three';
import { latLonToVector3 } from '../data/latlon';
import { EVIDENCE_COLORS, type LunarTarget } from '../data/targets';
import { MOON_RADIUS } from './Moon';

function smoothstep(edge0: number, edge1: number, x: number) {
  const t = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

interface MarkerProps {
  target: LunarTarget;
  progress: React.MutableRefObject<number>;
  selected: boolean;
  onSelect: (t: LunarTarget) => void;
}

function TargetMarker({ target, progress, selected, onSelect }: MarkerProps) {
  const group = useRef<THREE.Group>(null);
  const core = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const color = EVIDENCE_COLORS[target.evidence];

  const pos = useMemo(
    () => latLonToVector3(target.lat, target.lon, MOON_RADIUS + 0.07),
    [target.lat, target.lon]
  );
  const normal = useMemo(() => pos.clone().normalize(), [pos]);
  // Crater-boundary ring points (small circle tangent to the surface).
  const ringPoints = useMemo(() => {
    const radius = Math.min(0.42, Math.max(0.08, target.diameterKm / 260));
    const tangent = new THREE.Vector3().crossVectors(normal, new THREE.Vector3(0, 1, 0)).normalize();
    if (tangent.lengthSq() < 1e-6) tangent.set(1, 0, 0);
    const bitangent = new THREE.Vector3().crossVectors(normal, tangent).normalize();
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 48; i++) {
      const a = (i / 48) * Math.PI * 2;
      pts.push(
        pos
          .clone()
          .addScaledVector(tangent, Math.cos(a) * radius)
          .addScaledVector(bitangent, Math.sin(a) * radius)
      );
    }
    return pts;
  }, [pos, normal, target.diameterKm]);

  useFrame(() => {
    const reveal = smoothstep(0.4, 0.62, progress.current);
    if (group.current) {
      group.current.visible = reveal > 0.01;
      const s = reveal * (hovered || selected ? 1.35 : 1);
      group.current.scale.setScalar(s);
    }
    if (core.current) {
      const m = core.current.material as THREE.MeshBasicMaterial;
      m.opacity = reveal;
    }
  });

  const reveal = smoothstep(0.4, 0.62, progress.current);
  const active = hovered || selected;

  return (
    <group ref={group} position={pos}>
      {/* Core dot */}
      <mesh
        ref={core}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHovered(false);
          document.body.style.cursor = 'auto';
        }}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(target);
        }}
      >
        <sphereGeometry args={[0.035, 16, 16]} />
        <meshBasicMaterial color={color} transparent toneMapped={false} />
      </mesh>

      {/* Pulsing halo on active */}
      {active && (
        <mesh>
          <sphereGeometry args={[0.06, 16, 16]} />
          <meshBasicMaterial color={color} transparent opacity={0.25} toneMapped={false} />
        </mesh>
      )}

      {/* Label */}
      {reveal > 0.6 && (
        <Billboard position={[0, 0.14, 0]}>
          <Text
            fontSize={active ? 0.085 : 0.07}
            color={active ? '#ffffff' : '#d7e6f0'}
            anchorX="center"
            anchorY="bottom"
            outlineWidth={0.004}
            outlineColor="#04121c"
          >
            {target.name.toUpperCase()}
          </Text>
          {active && (
            <Text
              position={[0, -0.02, 0]}
              fontSize={0.045}
              color={color}
              anchorX="center"
              anchorY="top"
              maxWidth={1.4}
              outlineWidth={0.003}
              outlineColor="#04121c"
            >
              {target.label}
            </Text>
          )}
        </Billboard>
      )}

      {/* Crater boundary ring — shown only when active, to keep the pole tidy */}
      {active && reveal > 0.5 && (
        <Line
          points={ringPoints.map((p) => p.clone().sub(pos))}
          color={color}
          lineWidth={1.6}
          transparent
          opacity={reveal * 0.8}
        />
      )}
    </group>
  );
}

/** Translucent dark cap over the pole = permanently shadowed regions. */
function ShadowCap({ progress }: { progress: React.MutableRefObject<number> }) {
  const mesh = useRef<THREE.Mesh>(null);
  useFrame(() => {
    const reveal = smoothstep(0.32, 0.55, progress.current);
    if (mesh.current) {
      mesh.current.visible = reveal > 0.01;
      (mesh.current.material as THREE.MeshBasicMaterial).opacity = reveal * 0.55;
    }
  });
  // A small spherical cap sitting on the south pole (-Y).
  return (
    <mesh ref={mesh} rotation={[Math.PI, 0, 0]}>
      <sphereGeometry args={[MOON_RADIUS + 0.05, 48, 24, 0, Math.PI * 2, 0, Math.PI / 7]} />
      <meshBasicMaterial color="#0a1626" transparent opacity={0} side={THREE.DoubleSide} depthWrite={false} />
    </mesh>
  );
}

/** Demo landing site + science-aware rover route near Shackleton. */
function RoverRoute({ progress }: { progress: React.MutableRefObject<number> }) {
  const group = useRef<THREE.Group>(null);
  const { landing, routePoints } = useMemo(() => {
    const land = latLonToVector3(-89.0, 100, MOON_RADIUS + 0.07);
    const target = latLonToVector3(-89.66, 129.2, MOON_RADIUS + 0.07); // Shackleton
    const pts: THREE.Vector3[] = [];
    const steps = 40;
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      const p = land.clone().lerp(target, t).normalize().multiplyScalar(MOON_RADIUS + 0.075);
      // small lateral wobble so the route reads as a planned traverse, not a chord
      p.x += Math.sin(t * Math.PI * 3) * 0.02;
      pts.push(p);
    }
    return { landing: land, routePoints: pts };
  }, []);

  useFrame(() => {
    const reveal = smoothstep(0.72, 0.9, progress.current);
    if (group.current) group.current.visible = reveal > 0.01;
  });

  return (
    <group ref={group} visible={false}>
      <mesh position={landing} rotation={[Math.PI / 4, Math.PI / 4, 0]}>
        <boxGeometry args={[0.05, 0.05, 0.05]} />
        <meshBasicMaterial color="#ffd166" toneMapped={false} />
      </mesh>
      <Line points={routePoints} color="#ffd166" lineWidth={1.4} dashed dashSize={0.05} gapSize={0.03} transparent opacity={0.9} />
      <Billboard position={landing.clone().multiplyScalar(1.03)}>
        <Text fontSize={0.05} color="#ffd166" anchorX="center" outlineWidth={0.003} outlineColor="#04121c">
          LANDING SITE
        </Text>
      </Billboard>
    </group>
  );
}

interface Props {
  targets: LunarTarget[];
  progress: React.MutableRefObject<number>;
  selectedId: string | null;
  onSelect: (t: LunarTarget) => void;
}

export function SouthPoleTargets({ targets, progress, selectedId, onSelect }: Props) {
  return (
    <group>
      <ShadowCap progress={progress} />
      {targets.map((t) => (
        <TargetMarker
          key={t.id}
          target={t}
          progress={progress}
          selected={selectedId === t.id}
          onSelect={onSelect}
        />
      ))}
      <RoverRoute progress={progress} />
    </group>
  );
}
