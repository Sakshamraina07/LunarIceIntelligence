/**
 * MissionMap.tsx — the hero analysis map (≈70% of the workspace).
 *
 * A clean Leaflet CRS.Simple viewer over the real faustini tile pyramid
 * (/tiles/faustini/{layer}/{z}/{x}/{y}.png). This is a ground-up rewrite of
 * the old GISMapViewer whose getTileUrl used a modulo wrap that FABRICATED
 * in-range tiles for out-of-range requests — the source of the repeating
 * "checkerboard" grid.
 *
 * Root-cause fix (no CSS hiding):
 *   - MAP_SIZE = 256 makes Leaflet's own zoom number line up exactly with the
 *     backend pyramid's {z} folders (one 256px tile == one CRS.Simple unit at z0).
 *   - maxNativeZoom = 3 means Leaflet clamps coords.z into [0,3] (its _clampZoom
 *     honours maxNativeZoom) and upscales the z=3 tile past that — honest, no new tiles.
 *   - getTileUrl uses an ADDITIVE y-flip (coords.y + N), never a modulo, so an
 *     out-of-range index is never silently mapped onto a valid tile.
 *   - _isValidTile rejects any (x, y) outside [0,N) so missing/edge tiles render
 *     as dark background instead of a duplicate. maxBounds also stops overshoot.
 *
 * All map layers are declarative Leaflet objects; nothing scientific is computed
 * here — grid/site/route coordinates come straight from the backend mission state.
 */
import { useEffect, useImperativeHandle, useRef, forwardRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { MissionState, CandidateLandingSite } from '../types/mission';
import { LAYER_MAP } from './config';

const TILE_BASE = 'http://127.0.0.1:8000/tiles/faustini';
const MAP_SIZE = 256;
const IMAGE_BOUNDS: L.LatLngBoundsLiteral = [[0, 0], [MAP_SIZE, MAP_SIZE]];
const MAX_NATIVE = 3;
const KM_PER_DEG_LAT = 30.37;
const MIN_COS_LAT = 0.05;

/** Rover route strategy → line style. */
const ROUTE_STYLE: Record<string, { color: string; weight: number; dash?: string }> = {
  Shortest: { color: '#f2c14e', weight: 2.5, dash: '6 5' },
  Safest: { color: '#6ee7a8', weight: 2.5 },
  'Science-Aware': { color: '#4fd1e6', weight: 3.5 },
};

/** True multi-resolution tile layer with the additive y-flip + validity guard. */
class LunarTileLayer extends L.TileLayer {
  private layerName: string;
  constructor(layerName: string, options: L.TileLayerOptions = {}) {
    super('', { tileSize: 256, minZoom: 0, maxZoom: 6, maxNativeZoom: MAX_NATIVE, noWrap: true, ...options });
    this.layerName = layerName;
  }
  getTileUrl(coords: L.Coords): string {
    const z = Math.max(0, Math.min(MAX_NATIVE, coords.z));
    const n = Math.pow(2, z);
    // CRS.Simple with transformation (1,0,-1,0) yields tile rows in [-n,-1];
    // the disk stores rows [0,n-1] top-down, so the flip is additive, not modulo.
    const row = coords.y + n;
    return `${TILE_BASE}/${this.layerName}/${z}/${coords.x}/${row}.png`;
  }
  _isValidTile(coords: L.Coords): boolean {
    const z = Math.max(0, Math.min(MAX_NATIVE, coords.z));
    const n = Math.pow(2, z);
    const row = coords.y + n;
    return coords.x >= 0 && coords.x < n && row >= 0 && row < n;
  }
}

/** Grid (0–100) → CRS.Simple pixel [lat(py), lng(px)]. */
const gridToPixel = (gx: number, gy: number): [number, number] => [
  MAP_SIZE - (gy / 100) * MAP_SIZE,
  (gx / 100) * MAP_SIZE,
];

function approxLatLon(
  gx: number, gy: number,
  crater: { latitude_deg: number; longitude_deg: number },
  domainKm: number,
): { lat: number; lon: number } {
  const dLat = ((gy - 50) / 100) * (domainKm / KM_PER_DEG_LAT);
  const cosLat = Math.max(Math.abs(Math.cos((crater.latitude_deg * Math.PI) / 180)), MIN_COS_LAT);
  const dLon = ((gx - 50) / 100) * (domainKm / (KM_PER_DEG_LAT * cosLat));
  return {
    lat: Math.max(-90, Math.min(90, crater.latitude_deg + dLat)),
    lon: ((crater.longitude_deg + dLon + 540) % 360) - 180,
  };
}

export interface MissionMapHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  reset: () => void;
}

interface Props {
  mission: MissionState;
  activeLayer: string;
  showLandingSites: boolean;
  activeRoverStrategies: string[];
  selectedLandingSite: CandidateLandingSite | null;
  onSelectLandingSite: (s: CandidateLandingSite) => void;
  onCoords: (text: string) => void;
  onZoom: (z: number) => void;
}

export const MissionMap = forwardRef<MissionMapHandle, Props>(function MissionMap(
  { mission, activeLayer, showLandingSites, activeRoverStrategies, selectedLandingSite, onSelectLandingSite, onCoords, onZoom },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const baseRef = useRef<L.TileLayer | null>(null);
  const overlayRef = useRef<L.Layer | null>(null);
  const sitesRef = useRef<L.LayerGroup | null>(null);
  const routesRef = useRef<L.LayerGroup | null>(null);
  const targetRef = useRef<L.CircleMarker | null>(null);
  const gridRef = useRef<L.LayerGroup | null>(null);

  const crater = mission.selected_crater;
  const domainKm = (mission.grid_dimensions.pixel_scale_m * MAP_SIZE) / 1000;

  useImperativeHandle(ref, () => ({
    zoomIn: () => mapRef.current?.zoomIn(),
    zoomOut: () => mapRef.current?.zoomOut(),
    reset: () => mapRef.current?.flyToBounds(IMAGE_BOUNDS, { duration: 0.6 }),
  }), []);

  // ── init map once ──────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      crs: L.CRS.Simple,
      center: [MAP_SIZE / 2, MAP_SIZE / 2],
      zoom: 1,
      minZoom: 0,
      maxZoom: 6,
      zoomControl: false,
      attributionControl: false,
      maxBounds: IMAGE_BOUNDS,
      maxBoundsViscosity: 1.0,
      zoomSnap: 0.5,
      fadeAnimation: true,
    });
    mapRef.current = map;

    baseRef.current = new LunarTileLayer('hillshade', { zIndex: 100 }).addTo(map);

    // faint engineering graticule
    const grid = L.layerGroup().addTo(map);
    gridRef.current = grid;
    const style: L.PolylineOptions = { color: 'rgba(79,209,230,0.14)', weight: 1, dashArray: '3 7', interactive: false };
    for (let i = 0; i <= MAP_SIZE; i += MAP_SIZE / 5) {
      L.polyline([[i, 0], [i, MAP_SIZE]], style).addTo(grid);
      L.polyline([[0, i], [MAP_SIZE, i]], style).addTo(grid);
    }

    sitesRef.current = L.layerGroup().addTo(map);
    routesRef.current = L.layerGroup().addTo(map);

    map.fitBounds(IMAGE_BOUNDS);
    onZoom(map.getZoom());
    map.on('zoomend', () => onZoom(map.getZoom()));
    map.on('mousemove', (e: L.LeafletMouseEvent) => {
      const gx = Math.round((e.latlng.lng / MAP_SIZE) * 100);
      const gy = Math.round(((MAP_SIZE - e.latlng.lat) / MAP_SIZE) * 100);
      if (gx < 0 || gx > 100 || gy < 0 || gy > 100) return;
      const { lat, lon } = approxLatLon(gx, gy, crater, domainKm);
      onCoords(`GRID ${gx},${gy}  ·  ${lat.toFixed(3)}° ${lon.toFixed(3)}°`);
    });

    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── science overlay (base64 or tiled) follows activeLayer ──────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (overlayRef.current) { map.removeLayer(overlayRef.current); overlayRef.current = null; }
    if (activeLayer === 'hillshade') return;

    const def = LAYER_MAP[activeLayer];
    if (def?.tiled) {
      overlayRef.current = new LunarTileLayer(activeLayer, { opacity: 0.82, zIndex: 200 }).addTo(map);
    } else {
      const src = mission.raster_layers[activeLayer];
      if (src) overlayRef.current = L.imageOverlay(src, IMAGE_BOUNDS, { opacity: 0.82, zIndex: 200, interactive: false }).addTo(map);
    }
  }, [activeLayer, mission]);

  // ── smooth fly-to when the crater / target changes ─────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (targetRef.current) { map.removeLayer(targetRef.current); targetRef.current = null; }

    const t = mission.target_coordinates;
    const [py, px] = gridToPixel(t.x, t.y);
    const { lat, lon } = approxLatLon(t.x, t.y, crater, domainKm);

    const marker = L.circleMarker([py, px], {
      radius: 9, color: '#4fd1e6', weight: 2.5, fillColor: 'rgba(79,209,230,0.25)', fillOpacity: 1,
    }).addTo(map).bindPopup(
      `<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#4fd1e6;min-width:160px">
        <strong>CANDIDATE ICE TARGET</strong><br/>Lat ${lat.toFixed(4)}°<br/>Lon ${lon.toFixed(4)}°<br/>
        <span style="color:#7f93a5">Chandrayaan-2 DFSAR CPR peak</span></div>`,
    );
    targetRef.current = marker;
    map.flyTo([py, px], Math.max(map.getZoom(), 2), { duration: 0.7 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mission.selected_crater?.id, mission.target_coordinates?.x, mission.target_coordinates?.y]);

  // ── landing sites ──────────────────────────────────────────────
  useEffect(() => {
    const group = sitesRef.current;
    if (!group) return;
    group.clearLayers();
    if (!showLandingSites) return;
    mission.landing_sites.forEach((site) => {
      const [py, px] = gridToPixel(site.grid_x, site.grid_y);
      const sel = selectedLandingSite?.site_id === site.site_id;
      const rec = site.is_recommended;
      const marker = L.circleMarker([py, px], {
        radius: sel ? 10 : rec ? 8 : 6,
        color: rec ? '#4fd1e6' : '#7f93a5',
        weight: sel ? 3 : 2,
        fillColor: rec ? '#2b7c8c' : '#334155',
        fillOpacity: 0.9,
      }).addTo(group);
      marker.bindTooltip(`${rec ? '★ ' : ''}Site ${site.rank}`, { direction: 'top', offset: [0, -8], permanent: rec });
      marker.on('click', () => onSelectLandingSite(site));
    });
  }, [mission, showLandingSites, selectedLandingSite, onSelectLandingSite]);

  // ── rover routes ───────────────────────────────────────────────
  useEffect(() => {
    const group = routesRef.current;
    if (!group) return;
    group.clearLayers();
    Object.entries(ROUTE_STYLE).forEach(([strategy, s]) => {
      if (!activeRoverStrategies.includes(strategy)) return;
      const route = mission.rover_routes[strategy];
      if (!route?.path_found || !route.waypoints?.length) return;
      const pts = route.waypoints.map((wp) => gridToPixel(wp.x, wp.y));
      if (strategy === 'Science-Aware') {
        L.polyline(pts, { color: s.color, weight: s.weight + 6, opacity: 0.15, lineJoin: 'round' }).addTo(group);
      }
      L.polyline(pts, { color: s.color, weight: s.weight, opacity: 0.95, dashArray: s.dash, lineJoin: 'round', lineCap: 'round' })
        .addTo(group)
        .bindTooltip(`${strategy} · ${route.total_distance_km?.toFixed(1) ?? '?'} km`, { sticky: true });
    });
  }, [mission, activeRoverStrategies]);

  return <div ref={containerRef} className="mc-map" />;
});

