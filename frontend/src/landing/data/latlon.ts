/**
 * latlon.ts
 * Convert selenographic latitude/longitude to a point on a Three.js sphere.
 *
 * Convention used by the landing scene:
 *   - Moon centered at the origin, radius R.
 *   - South pole (lat = -90) sits at -Y so the camera can descend "down" onto it.
 *   - lon 0 faces +X, increasing lon rotates toward +Z.
 *
 * This mirrors the physical layout the mission's polar-stereographic map uses
 * (see frontend/src/utils/lunarCRS.ts) but expressed in 3D cartesian space.
 */
import * as THREE from 'three';

export function latLonToVector3(
  latDeg: number,
  lonDeg: number,
  radius: number
): THREE.Vector3 {
  const lat = THREE.MathUtils.degToRad(latDeg);
  const lon = THREE.MathUtils.degToRad(lonDeg);
  const cosLat = Math.cos(lat);
  return new THREE.Vector3(
    radius * cosLat * Math.cos(lon),
    radius * Math.sin(lat), // lat -90 -> -radius (south pole at bottom)
    radius * cosLat * Math.sin(lon)
  );
}
