/**
 * Moon.tsx
 * The hero: a real lunar DEM raster (public/lunar-dem.png) mapped onto a sphere
 * as displacement + bump so the surface shows genuine crater relief rather than
 * a smooth ball. Albedo is a restrained lunar grey. A subtle fresnel rim gives
 * the "atmospheric/space lighting" edge without any cheesy glow.
 *
 * The whole Moon (surface + markers, passed as children) shares one group so
 * features rotate with the body. Idle spin slows to near-zero as the camera
 * descends to the pole (progress -> 1) so targets stay readable/clickable.
 */
import { forwardRef, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { useTexture } from '@react-three/drei';
import * as THREE from 'three';
import { DEFAULT_SURFACE_PROVIDER } from '../services/lunarBasemap';

export const MOON_RADIUS = 2;

/** Fresnel rim shell — cheap, additive, view-dependent edge light. */
function AtmosphereRim() {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        blending: THREE.AdditiveBlending,
        side: THREE.BackSide,
        depthWrite: false,
        uniforms: { uColor: { value: new THREE.Color('#3ba8c9') } },
        vertexShader: /* glsl */ `
          varying float vIntensity;
          void main() {
            vec3 vNormal = normalize(normalMatrix * normal);
            vec3 vView = normalize((modelViewMatrix * vec4(position, 1.0)).xyz);
            vIntensity = pow(1.0 - abs(dot(vNormal, vView)), 3.0);
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          varying float vIntensity;
          uniform vec3 uColor;
          void main() {
            gl_FragColor = vec4(uColor, vIntensity * 0.55);
          }
        `,
      }),
    []
  );
  return (
    <mesh material={material} scale={1.045}>
      <sphereGeometry args={[MOON_RADIUS, 64, 64]} />
    </mesh>
  );
}

interface MoonProps {
  progress: React.MutableRefObject<number>;
  children?: React.ReactNode;
}

export const Moon = forwardRef<THREE.Group, MoonProps>(function Moon(
  { progress, children },
  groupRef
) {
  const surfaceRef = useRef<THREE.Group>(null);

  // Real lunar DEM raster -> reused for colour, bump and displacement.
  const dem = useTexture(DEFAULT_SURFACE_PROVIDER.equirectUrl ?? '/lunar-dem.png');
  useMemo(() => {
    dem.colorSpace = THREE.SRGBColorSpace;
    dem.anisotropy = 4;
    dem.wrapS = dem.wrapT = THREE.RepeatWrapping;
  }, [dem]);

  useFrame((_, delta) => {
    if (surfaceRef.current) {
      const idle = 0.03 * (1 - progress.current * 0.92);
      surfaceRef.current.rotation.y += delta * idle;
    }
  });

  return (
    <group ref={groupRef}>
      <group ref={surfaceRef}>
        <mesh castShadow receiveShadow>
          <sphereGeometry args={[MOON_RADIUS, 256, 256]} />
          <meshStandardMaterial
            map={dem}
            bumpMap={dem}
            bumpScale={0.9}
            displacementMap={dem}
            displacementScale={0.06}
            color="#9a938a"
            roughness={0.97}
            metalness={0.0}
          />
        </mesh>
        {children}
      </group>
      <AtmosphereRim />
    </group>
  );
});
