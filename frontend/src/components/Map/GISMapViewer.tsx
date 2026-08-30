/**
 * GISMapViewer.tsx
 *
 * Interactive pan/zoom lunar map powered by Leaflet.js with L.CRS.Simple.
 *
 * FIXED (this version — tile checkerboard bug):
 *  - Leaflet's CRS.Simple assumes "256 map units = 1 tile's worth of world
 *    at zoom 0" (its default scale/transformation bakes in a 256px tile
 *    grid). Our MAP_SIZE was set to 512, which is TWO tile-widths, not one.
 *    This silently shifted Leaflet's internal zoom numbering one level away
 *    from our backend's tile pyramid folder numbering ({z}/{x}/{y}.png):
 *    at Leaflet zoom 1, Leaflet only requested a 2x2 tile grid, but our
 *    pyramid's z=1 folder also only has 2x2 tiles — the correct-looking
 *    match was actually one zoom level short of what the current view
 *    needed, so some requested (x,y) indices didn't exist on disk and
 *    others were requested twice. That's what produced the checkerboard
 *    of correct tiles next to blank ones.
 *  - Fix: MAP_SIZE is now 256 (one native Leaflet "tile world" per zoom
 *    step), which makes Leaflet's zoom numbering land EXACTLY on our
 *    backend pyramid's {z} folders with no offset or hacks needed.
 *    getTileUrl() no longer needs the old "+numTiles"/clamp workaround —
 *    it just wraps safely at the edges as a defensive fallback.
 *  - maxBounds is now set on the map so Leaflet never even requests tiles
 *    outside the valid pyramid range in the first place.
 *
 * Uses the existing mission.raster_layers (base64 images) as a fallback
 * image overlay for any layer that doesn't yet have a generated tile
 * pyramid, while cpr_heatmap/dop_heatmap/dem_elevation/hazard_map/
 * illumination/hillshade use the real multi-resolution tile pyramid.
 *
 * Landing sites, rover routes, and target markers are rendered as real
 * Leaflet vector layers (L.circleMarker, L.polyline) with popups/tooltips.
 */

import React, { useEffect, useRef, useCallback, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { MissionState, CandidateLandingSite } from '../../types/mission';
import { Layers, Crosshair, RotateCcw, Info, ZoomIn } from 'lucide-react';

// Fix Leaflet default icon asset path (broken by bundler)
import markerIconUrl from 'leaflet/dist/images/marker-icon.png';
import markerIcon2xUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: markerIconUrl,
  iconRetinaUrl: markerIcon2xUrl,
  shadowUrl: markerShadowUrl,
});

// ─── Constants ────────────────────────────────────────────────────────────────

/**
 * Map domain size in CRS.Simple units. FIXED: this MUST be 256 (not 512)
 * so it matches Leaflet's built-in assumption of one 256px tile per unit
 * of zoom-0 world. This is what makes coords.z from Leaflet line up
 * exactly with our backend's tiles/faustini/{layer}/{z}/ folder numbering.
 */
const MAP_SIZE = 256;

/** Image bounds in CRS.Simple pixel coords: [[0,0], [MAP_SIZE, MAP_SIZE]] */
const IMAGE_BOUNDS: L.LatLngBoundsLiteral = [
  [0, 0],
  [MAP_SIZE, MAP_SIZE],
];

/** Approximate km per degree of latitude on the Moon */
const KM_PER_DEG_LAT = 30.37;

/** Hard floor for cos(lat) so we never divide by (near-)zero close to the pole */
const MIN_COS_LAT = 0.05;

/** Live USGS Astrogeology WMS endpoint for the locator mini-map */
const USGS_MOON_WMS_BASE =
  'https://planetarymaps.usgs.gov/cgi-bin/mapserv?map=/maps/moon/moon_simp_cyl.map';

/**
 * True Multi-Resolution Tile Layer for Chandrayaan-2 Real Science Data.
 * Connects directly to FastAPI backend static tile pyramid
 * (/tiles/faustini/{layer}/{z}/{x}/{y}.png). Native source: 2048x2048
 * arrays. With MAP_SIZE=256, Leaflet's own zoom number IS the pyramid's
 * {z} — no offset arithmetic needed.
 */
class LunarTileLayer extends L.TileLayer {
  private layerName: string;

  constructor(layerName: string, options: L.TileLayerOptions = {}) {
    super('', {
      tileSize: 256,
      minZoom: 0,
      maxZoom: 5,
      maxNativeZoom: 3, // backend pyramid only goes up to z=3 (2048x2048 native); beyond this Leaflet upscales the z=3 tile itself, which is the honest behavior
      noWrap: true,
      ...options,
    });
    this.layerName = layerName;
  }

  getTileUrl(coords: L.Coords): string {
    // Backend pyramid only has zoom folders 0..3 — deeper Leaflet zooms
    // (beyond maxNativeZoom) are handled by Leaflet's own upscaling of the
    // z=3 tiles, so we clamp the folder we ask for to what actually exists.
    const z = Math.max(0, Math.min(3, coords.z));
    const numTiles = Math.pow(2, z);

    // Defensive wrap-around (should rarely trigger now that maxBounds is
    // set on the map, but keeps us safe against any inertia/edge overshoot
    // instead of requesting a genuinely out-of-range tile).
    const col = ((coords.x % numTiles) + numTiles) % numTiles;
    const row = ((coords.y % numTiles) + numTiles) % numTiles;

    return `http://127.0.0.1:8000/tiles/faustini/${this.layerName}/${z}/${col}/${row}.png`;
  }
}

interface ColormapLegendConfig {
  title: string;
  gradient: string;
  lowLabel: string;
  highLabel: string;
  description: string;
}

const LAYER_LEGENDS: Record<string, ColormapLegendConfig> = {
  cpr_heatmap: {
    title: 'DFSAR CPR (Circular Polarization Ratio)',
    gradient: 'linear-gradient(to right, #0000ff, #00ffff, #00ff00, #ffff00, #ff0000)',
    lowLabel: '0.05 (Dry Regolith)',
    highLabel: '> 1.00 (Ice Anomaly)',
    description: 'Blue = low CPR (typical lunar regolith) → Red = high CPR (candidate ice deposits with Coherent Backscatter).'
  },
  dop_heatmap: {
    title: 'DFSAR DOP (Degree of Polarization)',
    gradient: 'linear-gradient(to right, #00204d, #414d6b, #7d7c78, #bca678, #ffea46)',
    lowLabel: '< 0.13 (Depolarized)',
    highLabel: '> 0.50 (Polarized)',
    description: 'Dark navy = volume depolarization (subsurface ice trap) → Gold = specular/surface reflection.'
  },
  dem_elevation: {
    title: 'LOLA Topographic Relief (DEM)',
    gradient: 'linear-gradient(to right, #440154, #3b528b, #21918c, #5ec962, #fde725)',
    lowLabel: '-3900m (Floor)',
    highLabel: '-1100m (Rim Crest)',
    description: 'Purple = deep cold-trap crater floor depression → Yellow = elevated sunlit crater rim peak.'
  },
  hazard_map: {
    title: 'Composite Terrain Hazard Index',
    gradient: 'linear-gradient(to right, #000080, #00ffff, #ffff00, #ff0000)',
    lowLabel: '0.0 (Safe Pass)',
    highLabel: '1.0 (Critical Barrier)',
    description: 'Blue/Green = safe slope & low roughness → Red = impassable cliff barrier (> 20° tilt).'
  },
  illumination: {
    title: 'Grazing Solar Illumination (1.5° Alt)',
    gradient: 'linear-gradient(to right, #000000, #8b0000, #ff4500, #ffff00, #ffffff)',
    lowLabel: '0.0% (True PSR)',
    highLabel: '100% (Sunlit)',
    description: 'Black = Permanent Shadow Region (PSR < 40K) → White = grazing solar radiation.'
  },
  hillshade: {
    title: 'Horn Analytical Shaded Relief',
    gradient: 'linear-gradient(to right, #111827, #4b5563, #9ca3af, #f3f4f6)',
    lowLabel: 'Deep Shadow',
    highLabel: 'Direct Sunlit Rim',
    description: 'Analytical shaded relief showing micro-craters, boulders, and wall passes under grazing sunlight.'
  },
  psr_mask: {
    title: 'Permanent Shadow Region (PSR) Mask',
    gradient: 'linear-gradient(to right, #1e293b, #06b6d4)',
    lowLabel: 'Sunlit Exterior',
    highLabel: 'True PSR Floor',
    description: 'Dark = illuminated crater slopes → Cyan = cold trap permanently shielded from sunlight.'
  },
  ml_likelihood: {
    title: 'ML Probabilistic Ice Likelihood P(ice)',
    gradient: 'linear-gradient(to right, #000000, #581845, #900c3f, #c70039, #ff5733, #ffc300)',
    lowLabel: 'P = 0.0 (Unlikely)',
    highLabel: 'P > 0.85 (High Candidate)',
    description: 'Random Forest model predicting ice probability from fused radar, slope, and temperature data.'
  }
};

// ─── Interfaces ───────────────────────────────────────────────────────────────

interface GISMapViewerProps {
  mission: MissionState;
  activeLayer: string;
  setActiveLayer: (layer: string) => void;
  showLandingSites: boolean;
  setShowLandingSites: (show: boolean) => void;
  activeRoverStrategies: string[];
  toggleRoverStrategy: (strategy: string) => void;
  selectedLandingSite: CandidateLandingSite | null;
  onSelectLandingSite: (site: CandidateLandingSite) => void;
}

// ─── Helper: grid coords (0–100) → pixel coords (0–MAP_SIZE) ─────────────────

const gridToPixel = (gx: number, gy: number): [number, number] => {
  const px = (gx / 100) * MAP_SIZE;
  const py = MAP_SIZE - (gy / 100) * MAP_SIZE;
  return [py, px];
};

function pixelToApproxLatLon(
  gridX: number,
  gridY: number,
  crater: { latitude_deg: number; longitude_deg: number },
  domainKm: number
): { lat: number; lon: number } {
  const dLatDeg = ((gridY - 50) / 100) * (domainKm / KM_PER_DEG_LAT);
  const cosLat = Math.max(
    Math.abs(Math.cos((crater.latitude_deg * Math.PI) / 180)),
    MIN_COS_LAT
  );
  const dLonDeg = ((gridX - 50) / 100) * (domainKm / (KM_PER_DEG_LAT * cosLat));

  const lat = Math.max(-90, Math.min(90, crater.latitude_deg + dLatDeg));
  const lon = ((crater.longitude_deg + dLonDeg + 540) % 360) - 180;

  return { lat, lon };
}

// ─── Component ────────────────────────────────────────────────────────────────

export const GISMapViewer: React.FC<GISMapViewerProps> = ({
  mission,
  activeLayer,
  setActiveLayer,
  showLandingSites,
  activeRoverStrategies,
  toggleRoverStrategy,
  selectedLandingSite,
  onSelectLandingSite,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);

  const [currentZoom, setCurrentZoom] = useState<number>(1);

  const locatorContainerRef = useRef<HTMLDivElement>(null);
  const locatorMapRef = useRef<L.Map | null>(null);
  const locatorMarkerRef = useRef<L.CircleMarker | null>(null);

  const baseOverlayRef = useRef<L.Layer | null>(null);
  const scienceOverlayRef = useRef<L.Layer | null>(null);
  const landingSiteGroupRef = useRef<L.LayerGroup | null>(null);
  const routeGroupRef = useRef<L.LayerGroup | null>(null);
  const targetMarkerRef = useRef<L.CircleMarker | null>(null);
  const gridGroupRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current, {
      crs: L.CRS.Simple,
      center: [MAP_SIZE / 2, MAP_SIZE / 2],
      zoom: 1,
      minZoom: 0,
      maxZoom: 5,
      zoomControl: false,
      attributionControl: false,
      maxBounds: IMAGE_BOUNDS,
      maxBoundsViscosity: 1.0,
    });

    mapRef.current = map;

    const updateZoom = () => setCurrentZoom(map.getZoom());
    map.on('zoom zoomend viewreset', updateZoom);
    updateZoom();

    const baseTile = new LunarTileLayer('hillshade', {
      opacity: 1.0,
      zIndex: 100,
    }).addTo(map);
    baseOverlayRef.current = baseTile;

    const gridGroup = L.layerGroup().addTo(map);
    gridGroupRef.current = gridGroup;

    const gridStyle: L.PolylineOptions = {
      color: 'rgba(6,182,212,0.12)',
      weight: 1,
      dashArray: '3 6',
    };

    const gridStep = MAP_SIZE / 5;
    for (let i = 0; i <= MAP_SIZE; i += gridStep) {
      L.polyline([[i, 0], [i, MAP_SIZE]], gridStyle).addTo(gridGroup);
      L.polyline([[0, i], [MAP_SIZE, i]], gridStyle).addTo(gridGroup);
    }

    const crater = mission.selected_crater;
    const pixelScale = mission.grid_dimensions.pixel_scale_m;
    const domainKm = (pixelScale * MAP_SIZE) / 1000;

    for (let pct = 0; pct <= 100; pct += 20) {
      const px = (pct / 100) * MAP_SIZE;
      const { lat: edgeLat } = pixelToApproxLatLon(50, pct, crater, domainKm);
      const { lon: edgeLon } = pixelToApproxLatLon(pct, 50, crater, domainKm);

      L.marker([MAP_SIZE - px, -2], {
        icon: L.divIcon({
          className: '',
          html: `<span style="color:rgba(6,182,212,0.5);font-size:9px;font-family:monospace;white-space:nowrap">${edgeLat.toFixed(2)}°</span>`,
          iconAnchor: [40, 6],
        }),
        interactive: false,
      }).addTo(gridGroup);

      L.marker([-4, px], {
        icon: L.divIcon({
          className: '',
          html: `<span style="color:rgba(6,182,212,0.5);font-size:9px;font-family:monospace;white-space:nowrap">${edgeLon.toFixed(1)}°</span>`,
          iconAnchor: [12, 0],
        }),
        interactive: false,
      }).addTo(gridGroup);
    }

    landingSiteGroupRef.current = L.layerGroup().addTo(map);
    routeGroupRef.current = L.layerGroup().addTo(map);

    map.fitBounds(IMAGE_BOUNDS);

    const coordDisplay = document.getElementById('leaflet-coord-readout');
    map.on('mousemove', (e: L.LeafletMouseEvent) => {
      if (!coordDisplay) return;
      const { lat: py, lng: px } = e.latlng;
      const gridX = Math.round((px / MAP_SIZE) * 100);
      const gridY = Math.round(((MAP_SIZE - py) / MAP_SIZE) * 100);
      const { lat: latApprox, lon: lonApprox } = pixelToApproxLatLon(gridX, gridY, crater, domainKm);
      coordDisplay.innerHTML = `Grid: (${gridX}, ${gridY}) · ${latApprox.toFixed(4)}° S, ${lonApprox.toFixed(4)}° E`;
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!locatorContainerRef.current || locatorMapRef.current) return;

    const container = locatorContainerRef.current;
    if ((container as any)._leaflet_id) {
      delete (container as any)._leaflet_id;
    }

    const crater = mission.selected_crater;

    const locatorMap = L.map(container, {
      crs: L.CRS.EPSG4326,
      center: [crater.latitude_deg, crater.longitude_deg],
      zoom: 6,
      minZoom: 3,
      maxZoom: 9,
      maxBounds: [[-90, -180], [90, 180]],
      maxBoundsViscosity: 1.0,
      zoomControl: false,
      attributionControl: false,
      dragging: true,
      scrollWheelZoom: true,
    });

    L.tileLayer.wms(USGS_MOON_WMS_BASE, {
      layers: 'MOON_LRO_WAC_MOSAIC_GLOBAL_303PPD',
      format: 'image/jpeg',
      transparent: false,
      version: '1.1.1',
      crs: L.CRS.EPSG4326,
    }).addTo(locatorMap);

    const marker = L.circleMarker([crater.latitude_deg, crater.longitude_deg], {
      radius: 6,
      color: '#00f0ff',
      weight: 2,
      fillColor: '#00f0ff',
      fillOpacity: 0.8,
    })
      .addTo(locatorMap)
      .bindTooltip(crater.name, { permanent: false });

    locatorMarkerRef.current = marker;
    locatorMapRef.current = locatorMap;

    return () => {
      locatorMap.remove();
      locatorMapRef.current = null;
      locatorMarkerRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const locatorMap = locatorMapRef.current;
    if (!locatorMap) return;
    const crater = mission.selected_crater;
    locatorMap.setView([crater.latitude_deg, crater.longitude_deg], locatorMap.getZoom());
    if (locatorMarkerRef.current) {
      locatorMarkerRef.current.setLatLng([crater.latitude_deg, crater.longitude_deg]);
      locatorMarkerRef.current.setTooltipContent(crater.name);
    }
  }, [mission.selected_crater?.name, mission.selected_crater?.latitude_deg, mission.selected_crater?.longitude_deg]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (scienceOverlayRef.current) {
      map.removeLayer(scienceOverlayRef.current);
      scienceOverlayRef.current = null;
    }

    if (activeLayer === 'hillshade') return;

    const availableTileLayers = ['cpr_heatmap', 'dop_heatmap', 'dem_elevation', 'hazard_map', 'illumination'];
    if (availableTileLayers.includes(activeLayer)) {
      const tileOverlay = new LunarTileLayer(activeLayer, {
        opacity: 0.85,
        zIndex: 200,
      }).addTo(map);
      scienceOverlayRef.current = tileOverlay;
    } else {
      const imgSrc = mission.raster_layers[activeLayer];
      if (imgSrc) {
        const overlay = L.imageOverlay(imgSrc, IMAGE_BOUNDS, {
          opacity: 0.85,
          zIndex: 200,
          interactive: false,
        }).addTo(map);
        scienceOverlayRef.current = overlay;
      }
    }
  }, [mission, activeLayer]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (targetMarkerRef.current) {
      map.removeLayer(targetMarkerRef.current);
      targetMarkerRef.current = null;
    }

    const target = mission.target_coordinates;
    const [py, px] = gridToPixel(target.x, target.y);

    const crater = mission.selected_crater;
    const domainKm = (mission.grid_dimensions.pixel_scale_m * MAP_SIZE) / 1000;
    const { lat: latApprox, lon: lonApprox } = pixelToApproxLatLon(target.x, target.y, crater, domainKm);

    const marker = L.circleMarker([py, px], {
      radius: 10,
      color: '#00f0ff',
      weight: 2.5,
      fillColor: 'rgba(0,240,255,0.3)',
      fillOpacity: 1,
    })
      .addTo(map)
      .bindPopup(
        `<div style="font-family:monospace;font-size:11px;color:#00f0ff;min-width:160px">
          <strong>🎯 CANDIDATE ICE TARGET</strong><br/>
          Lat: ${latApprox.toFixed(4)}°<br/>
          Lon: ${lonApprox.toFixed(4)}°<br/>
          Source: Chandrayaan-2 DFSAR CPR
        </div>`,
        { className: 'leaflet-dark-popup' }
      );

    targetMarkerRef.current = marker;
  }, [mission]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const map = mapRef.current;
    const group = landingSiteGroupRef.current;
    if (!map || !group) return;

    group.clearLayers();
    if (!showLandingSites) return;

    mission.landing_sites.forEach((site) => {
      const [py, px] = gridToPixel(site.grid_x, site.grid_y);
      const isSelected = selectedLandingSite?.site_id === site.site_id;
      const isRecommended = site.is_recommended;

      const color = isRecommended ? '#38bdf8' : '#64748b';
      const fillColor = isRecommended ? '#0284c7' : '#334155';
      const radius = isSelected ? 10 : isRecommended ? 8 : 6;

      const marker = L.circleMarker([py, px], {
        radius,
        color,
        weight: isSelected ? 3 : 2,
        fillColor,
        fillOpacity: 0.9,
      }).addTo(group);

      marker.bindTooltip(
        `<span style="font-family:monospace;font-size:10px">${isRecommended ? '⭐ ' : ''}Site ${site.rank}</span>`,
        { permanent: isRecommended, direction: 'top', offset: [0, -radius] }
      );

      marker.bindPopup(
        `<div style="font-family:monospace;font-size:11px;min-width:170px">
          <div style="color:#38bdf8;font-weight:bold;margin-bottom:4px">
            ${isRecommended ? '⭐ Recommended — ' : ''}Site ${site.rank}
          </div>
          <div>Lat: ${site.lat_deg.toFixed(4)}°</div>
          <div>Lon: ${site.lon_deg.toFixed(4)}°</div>
          <div>Slope: ${site.slope_deg.toFixed(1)}°</div>
          <div>Hazard: ${site.hazard_score.toFixed(3)}</div>
          <div>Science Value: ${site.scientific_value.toFixed(3)}</div>
          <div>Score: ${site.composite_landing_score.toFixed(3)}</div>
        </div>`,
        { className: 'leaflet-dark-popup', maxWidth: 220 }
      );

      marker.on('click', () => onSelectLandingSite(site));
    });
  }, [mission, showLandingSites, selectedLandingSite, onSelectLandingSite]);

  useEffect(() => {
    const map = mapRef.current;
    const group = routeGroupRef.current;
    if (!map || !group) return;

    group.clearLayers();

    const routeConfig: Record<string, { color: string; dashArray?: string; weight: number; opacity: number }> = {
      Shortest: { color: '#f59e0b', dashArray: '6 5', weight: 2.5, opacity: 0.9 },
      Safest: { color: '#10b981', weight: 2.5, opacity: 0.9 },
      'Science-Aware': { color: '#00f0ff', weight: 3.5, opacity: 1.0 },
    };

    Object.entries(routeConfig).forEach(([strategy, style]) => {
      if (!activeRoverStrategies.includes(strategy)) return;
      const route = mission.rover_routes[strategy];
      if (!route?.path_found || !route.waypoints?.length) return;

      const latlngs: [number, number][] = route.waypoints.map((wp) => gridToPixel(wp.x, wp.y));

      const polyline = L.polyline(latlngs, {
        color: style.color,
        weight: style.weight,
        opacity: style.opacity,
        dashArray: style.dashArray,
        lineJoin: 'round',
        lineCap: 'round',
      }).addTo(group);

      if (strategy === 'Science-Aware') {
        L.polyline(latlngs, {
          color: style.color,
          weight: style.weight + 6,
          opacity: 0.15,
          lineJoin: 'round',
          lineCap: 'round',
        }).addTo(group);
      }

      polyline.bindTooltip(
        `<span style="font-family:monospace;font-size:10px;color:${style.color}">${strategy} Route · ${route.total_distance_km?.toFixed(1) ?? '?'} km</span>`,
        { sticky: true }
      );
    });
  }, [mission, activeRoverStrategies]);

  const handleZoomIn = useCallback(() => mapRef.current?.zoomIn(), []);
  const handleZoomOut = useCallback(() => mapRef.current?.zoomOut(), []);
  const handleReset = useCallback(() => {
    mapRef.current?.fitBounds(IMAGE_BOUNDS);
  }, []);

  const isRealData = mission.selected_crater.is_real_data || mission.data_mode === 'REAL';

  return (
    <div className="flex flex-col bg-slate-900/90 rounded-xl border border-slate-800 p-4 shadow-2xl backdrop-blur-md">
      <div className="mb-3">
        <span
          className={`text-[10px] font-mono font-bold px-2.5 py-1 rounded inline-flex items-center gap-1.5 border ${isRealData
            ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
            : 'bg-amber-500/15 text-amber-300 border-amber-500/40'
            }`}
        >
          {(mission.radar as any)?.data_source_tag ||
            (isRealData
              ? `REAL DATA — Chandrayaan-2 SAR · ${mission.selected_crater.product_id || 'ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18'} · ${mission.selected_crater.observed_date || '2020-08-08'}`
              : 'Simulated placeholder — pending real data')}
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 mb-3 pb-3 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <span className="font-semibold text-slate-300 uppercase tracking-wider">Layer:</span>
          <select
            value={activeLayer}
            onChange={(e) => setActiveLayer(e.target.value)}
            className="bg-slate-900 text-cyan-300 font-medium px-3 py-1.5 rounded-lg border border-slate-700 focus:outline-none focus:border-cyan-500 text-xs shadow-inner"
          >
            <option value="hillshade">Hillshade (Shaded Relief)</option>
            <option value="dem_elevation">DEM Elevation (LOLA)</option>
            <option value="illumination">Grazing Solar Illumination</option>
            <option value="psr_mask">PSR Permanent Shadow Mask</option>
            <option value="cpr_heatmap">DFSAR CPR (Circular Polarisation Ratio)</option>
            <option value="dop_heatmap">DFSAR DOP (Degree of Polarisation)</option>
            <option value="ml_likelihood">ML Ice Likelihood P(ice)</option>
            <option value="hazard_map">Terrain Hazard Index</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">Routes:</span>
          {(['Shortest', 'Safest', 'Science-Aware'] as const).map((s) => {
            const active = activeRoverStrategies.includes(s);
            const colours: Record<string, string> = {
              Shortest: active
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-[0_0_8px_rgba(245,158,11,0.2)]'
                : 'bg-slate-800/60 text-slate-500 border-slate-700',
              Safest: active
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-[0_0_8px_rgba(16,185,129,0.2)]'
                : 'bg-slate-800/60 text-slate-500 border-slate-700',
              'Science-Aware': active
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/60 shadow-[0_0_12px_rgba(6,182,212,0.3)] font-bold'
                : 'bg-slate-800/60 text-slate-500 border-slate-700',
            };
            const dot: Record<string, string> = {
              Shortest: 'bg-amber-400',
              Safest: 'bg-emerald-400',
              'Science-Aware': 'bg-cyan-400',
            };
            return (
              <button
                key={s}
                onClick={() => toggleRoverStrategy(s)}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 border transition ${colours[s]}`}
              >
                <div className={`w-2 h-2 rounded-full ${dot[s]} ${s === 'Science-Aware' && active ? 'animate-pulse' : ''}`} />
                {s}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-1 bg-slate-900 rounded-lg p-1 border border-slate-700 shadow-sm">
          <button onClick={handleZoomIn} className="px-2.5 py-1 text-slate-300 hover:text-cyan-400 transition font-bold text-sm" title="Zoom In">+</button>
          <button onClick={handleZoomOut} className="px-2.5 py-1 text-slate-300 hover:text-cyan-400 transition font-bold text-sm" title="Zoom Out">−</button>
          <button onClick={handleReset} className="px-2 py-1 text-slate-300 hover:text-cyan-400 transition" title="Reset Map View">
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="relative rounded-lg overflow-hidden border border-slate-800" style={{ height: '540px' }}>
        <div
          ref={mapContainerRef}
          className="absolute inset-0"
          style={{ background: '#020617' }}
        />

        <div
          className="absolute top-3 left-3 z-[1000] rounded-lg overflow-hidden border border-cyan-500/40 shadow-lg"
          style={{ width: 180, height: 140 }}
        >
          <div ref={locatorContainerRef} className="w-full h-full" />
          <div className="absolute bottom-0 left-0 right-0 bg-slate-900/80 text-[9px] font-mono text-cyan-300 px-2 py-0.5">
            REAL LUNAR SURFACE · USGS
          </div>
        </div>

        <div className="absolute bottom-3 left-3 z-[1000] pointer-events-none">
          <div className="bg-slate-900/90 border border-cyan-500/40 rounded-lg px-3 py-2 text-[11px] font-mono text-cyan-300 backdrop-blur-md shadow-lg">
            <div className="flex items-center gap-1.5 text-slate-400 font-semibold mb-1">
              <Crosshair className="w-3 h-3 text-cyan-400" />
              INTERACTIVE MAP · Leaflet.js
            </div>
            <div id="leaflet-coord-readout" className="text-slate-300">
              Hover to see coordinates
            </div>
            <div className="text-slate-400 mt-0.5">
              Layer: {activeLayer.replace(/_/g, ' ').toUpperCase()} · {mission.selected_crater.name}
            </div>
          </div>
        </div>

        <div className="absolute top-3 right-3 z-[1000] w-[270px] bg-slate-950/92 border border-cyan-500/30 rounded-xl p-3 backdrop-blur-md shadow-2xl space-y-2.5 text-xs pointer-events-auto">
          <div className="flex items-center justify-between gap-2 pb-1.5 border-b border-slate-800">
            <div className="flex items-center gap-1.5 font-bold text-[11px] text-cyan-300">
              <ZoomIn className="w-3.5 h-3.5 text-cyan-400" />
              <span>NATIVE TILE PYRAMID</span>
            </div>
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
              Zoom {currentZoom} / {Math.min(currentZoom, 3)} native
            </span>
          </div>

          {LAYER_LEGENDS[activeLayer] && (
            <div className="space-y-1.5">
              <div className="text-[11px] font-bold text-slate-100 flex items-center gap-1">
                <Info className="w-3 h-3 text-cyan-400 flex-shrink-0" />
                <span className="truncate">{LAYER_LEGENDS[activeLayer].title}</span>
              </div>
              <div
                className="h-2.5 w-full rounded-full border border-slate-700 shadow-inner"
                style={{ background: LAYER_LEGENDS[activeLayer].gradient }}
              />
              <div className="flex justify-between text-[9px] font-mono text-slate-400">
                <span>{LAYER_LEGENDS[activeLayer].lowLabel}</span>
                <span>{LAYER_LEGENDS[activeLayer].highLabel}</span>
              </div>
              <p className="text-[10px] text-slate-300 leading-snug pt-0.5">
                {LAYER_LEGENDS[activeLayer].description}
              </p>
            </div>
          )}

          <div className="pt-1.5 border-t border-slate-800/80 flex items-center justify-between text-[9px] text-slate-400 font-mono">
            <span>Source: 2048² Swath</span>
            <span className="text-emerald-400 font-semibold">Max Native: z3</span>
          </div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-slate-800 flex flex-wrap items-center justify-between text-[11px] text-slate-400 gap-2">
        <div className="flex items-center gap-4">
          <span className="font-semibold text-slate-300">Legend:</span>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block" />
            <span>Candidate Ice Target</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-sky-500 inline-block" />
            <span>Recommended Landing Site</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-5 h-0.5 bg-amber-400 inline-block" />
            <span>Shortest</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-5 h-0.5 bg-emerald-400 inline-block" />
            <span>Safest</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-5 h-0.5 bg-cyan-400 inline-block shadow-[0_0_6px_#00f0ff]" />
            <span>Science-Aware</span>
          </div>
        </div>
        <div className="font-mono text-[10px] text-slate-500">
          Scale: {mission.grid_dimensions.pixel_scale_m}m/px · Domain: {((mission.grid_dimensions.pixel_scale_m * MAP_SIZE) / 1000).toFixed(0)} km × {((mission.grid_dimensions.pixel_scale_m * MAP_SIZE) / 1000).toFixed(0)} km
        </div>
      </div>
    </div>
  );
};