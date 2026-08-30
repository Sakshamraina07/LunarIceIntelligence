"""
Generate Multi-Resolution Tile Pyramid from Real 2048x2048 Chandrayaan-2 Data.
Creates TMS/XYZ Slippy Map tiles for Leaflet:
Output structure: backend/tiles/faustini/{layer}/{z}/{x}/{y}.png
Zoom levels:
  z=0: 256x256 (1x1 tile)
  z=1: 512x512 (2x2 tiles)
  z=2: 1024x1024 (4x4 tiles)
  z=3: 2048x2048 (8x8 tiles - 100% native resolution from 1782x6605 raw swath)
"""

import os
import cv2
import numpy as np
import tifffile
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
TILES_DIR = BASE_DIR / "tiles" / "faustini"
PRADAN_DIR = Path("d:/FYP/data/pradan")

def array_to_rgba_tile(slice_data: np.ndarray, colormap: int = None, is_solid: bool = True) -> np.ndarray:
    """Converts a 2D float array slice into an RGBA 256x256 image.
    If is_solid is True, alpha is 100% solid (255) across the entire tile rectangle.
    If is_solid is False (for science overlays like CPR), pixels with data get alpha=235 and 0s are transparent.
    """
    h, w = slice_data.shape

    if is_solid:
        # Solid base layers: normalize across the slice (or valid finite values)
        valid = np.isfinite(slice_data)
        if not np.any(valid):
            return np.full((h, w, 4), 255, dtype=np.uint8)
            
        vmin = np.percentile(slice_data[valid], 1)
        vmax = np.percentile(slice_data[valid], 99)
        if vmax <= vmin:
            vmax = vmin + 1.0
            
        norm = np.clip((slice_data - vmin) / (vmax - vmin), 0.0, 1.0)
        norm_u8 = (norm * 255.0).astype(np.uint8)
        
        if colormap is not None:
            bgr = cv2.applyColorMap(norm_u8, colormap)
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        else:
            rgb = cv2.cvtColor(norm_u8, cv2.COLOR_GRAY2RGB)
            
        alpha = np.full((h, w), 255, dtype=np.uint8)
        return np.dstack([rgb, alpha])
    else:
        # Semi-transparent science layer (e.g. CPR or DOP over base terrain)
        valid = np.isfinite(slice_data) & (slice_data > 0.005)
        if not np.any(valid):
            return np.zeros((h, w, 4), dtype=np.uint8)
            
        vmin = np.percentile(slice_data[valid], 2)
        vmax = np.percentile(slice_data[valid], 98)
        if vmax <= vmin:
            vmax = vmin + 1.0
            
        norm = np.clip((slice_data - vmin) / (vmax - vmin), 0.0, 1.0)
        norm_u8 = (norm * 255.0).astype(np.uint8)
        
        bgr = cv2.applyColorMap(norm_u8, colormap if colormap is not None else cv2.COLORMAP_TURBO)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        alpha = np.where(valid, 230, 0).astype(np.uint8)
        return np.dstack([rgb, alpha])

def compute_hillshade(dem: np.ndarray, altitude_deg: float = 30.0, azimuth_deg: float = 315.0) -> np.ndarray:
    """Analytical Horn hillshade for 2048x2048 DEM."""
    rad_alt = np.radians(altitude_deg)
    rad_az = np.radians(azimuth_deg)
    
    # Gradients with 250m cell size
    dy, dx = np.gradient(dem, 250.0)
    slope = np.pi / 2.0 - np.arctan(np.sqrt(dx**2 + dy**2))
    aspect = np.arctan2(-dx, dy)
    
    shaded = np.sin(rad_alt) * np.sin(slope) + np.cos(rad_alt) * np.cos(slope) * np.cos(rad_az - aspect)
    return np.clip((shaded + 1.0) / 2.0, 0.0, 1.0).astype(np.float32)

def generate_layer_tiles(layer_name: str, full_data: np.ndarray, colormap: int = None, is_solid: bool = True, max_zoom: int = 3):
    print(f"\n[+] Tiling layer '{layer_name}' (Native Resolution: {full_data.shape[1]}x{full_data.shape[0]}, Solid: {is_solid})...")
    layer_dir = TILES_DIR / layer_name
    layer_dir.mkdir(parents=True, exist_ok=True)
    
    for z in range(max_zoom + 1):
        zoom_dim = 256 * (2 ** z)
        # Resample full array to the target zoom dimension
        if full_data.shape != (zoom_dim, zoom_dim):
            resampled = cv2.resize(full_data, (zoom_dim, zoom_dim), interpolation=cv2.INTER_AREA if zoom_dim < full_data.shape[0] else cv2.INTER_LINEAR)
        else:
            resampled = full_data
            
        num_tiles = 2 ** z
        for x in range(num_tiles):
            x_dir = layer_dir / str(z) / str(x)
            x_dir.mkdir(parents=True, exist_ok=True)
            for y in range(num_tiles):
                tile_y_start = y * 256
                tile_y_end = (y + 1) * 256
                tile_x_start = x * 256
                tile_x_end = (x + 1) * 256
                
                tile_slice = resampled[tile_y_start:tile_y_end, tile_x_start:tile_x_end]
                rgba = array_to_rgba_tile(tile_slice, colormap=colormap, is_solid=is_solid)
                
                tile_path = x_dir / f"{y}.png"
                Image.fromarray(rgba).save(tile_path, format="PNG", optimize=True)

    print(f"    Done tiling '{layer_name}' for zooms 0..{max_zoom} ({sum(4**z for z in range(max_zoom+1))} tiles generated).")

def main():
    print("=" * 60)
    print("GENERATING NATIVE 2048x2048 CHANDRAYAAN-2 TILE PYRAMID")
    print("=" * 60)
    
    # 1. Load real 2048x2048 data
    cpr_path = PRADAN_DIR / "dfsar" / "cpr_real.tif"
    dop_path = PRADAN_DIR / "dfsar" / "dop_real.tif"
    dem_path = PRADAN_DIR / "dem" / "real_dem.tif"
    
    assert cpr_path.exists(), f"Missing {cpr_path}"
    assert dop_path.exists(), f"Missing {dop_path}"
    assert dem_path.exists(), f"Missing {dem_path}"
    
    cpr = tifffile.imread(cpr_path).astype(np.float32)
    dop = tifffile.imread(dop_path).astype(np.float32)
    dem = tifffile.imread(dem_path).astype(np.float32)
    hillshade = compute_hillshade(dem)
    
    print(f"Loaded Real CPR shape: {cpr.shape} (values {np.min(cpr):.3f} to {np.max(cpr):.3f})")
    print(f"Loaded Real DOP shape: {dop.shape} (values {np.min(dop):.3f} to {np.max(dop):.3f})")
    print(f"Loaded Real DEM shape: {dem.shape} (elev {np.min(dem):.1f}m to {np.max(dem):.1f}m)")
    
    # 2. Compute illumination & hazard map at 2048x2048
    from scipy.ndimage import uniform_filter
    dy, dx = np.gradient(dem, 250.0)
    slope_deg = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))
    mean_elev = uniform_filter(dem, size=5)
    mean_sq_elev = uniform_filter(dem**2, size=5)
    roughness = np.sqrt(np.maximum(0.0, mean_sq_elev - mean_elev**2))
    hazard = np.clip(0.6 * (slope_deg / 25.0) + 0.4 * (roughness / 40.0), 0.0, 1.0).astype(np.float32)
    illumination = np.clip(hillshade * ((dem - np.min(dem)) / (np.ptp(dem) + 1e-6))**1.2, 0.0, 1.0).astype(np.float32)

    # 3. Generate tiles for all core science layers
    # Base terrain relief is 100% solid (is_solid=True) so it completely fills the rectangular map
    generate_layer_tiles("hillshade", hillshade, colormap=None, is_solid=True, max_zoom=3)
    generate_layer_tiles("dem_elevation", dem, colormap=cv2.COLORMAP_VIRIDIS, is_solid=True, max_zoom=3)
    generate_layer_tiles("hazard_map", hazard, colormap=cv2.COLORMAP_JET, is_solid=True, max_zoom=3)
    generate_layer_tiles("illumination", illumination, colormap=cv2.COLORMAP_HOT, is_solid=True, max_zoom=3)

    # Radar science layers are semi-transparent overlays (is_solid=False)
    generate_layer_tiles("cpr_heatmap", cpr, colormap=cv2.COLORMAP_TURBO, is_solid=False, max_zoom=3)
    generate_layer_tiles("dop_heatmap", dop, colormap=cv2.COLORMAP_CIVIDIS, is_solid=False, max_zoom=3)
    
    print("\nAll tile pyramids successfully generated in:", TILES_DIR)

if __name__ == "__main__":
    main()
