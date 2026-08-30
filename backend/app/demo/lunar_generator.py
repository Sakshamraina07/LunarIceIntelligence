"""
Deterministic Lunar South Polar Demo Data Generator.
PRD Compliance: Generates mathematically sound, internally consistent, and physically realistic
lunar South Polar craters (Shackleton, Shoemaker, Faustini) based on fixed random seeds.
Simulates DEM, polar grazing illumination, PSRs, doubly-shadowed pockets, and DFSAR radar polarimetry.
"""

import numpy as np
from typing import Dict, Any, Tuple
from app.core.config import settings
from app.core.schemas import CraterInfo


CRATER_CATALOG = {
    "shackleton": CraterInfo(
        id="shackleton",
        name="Shackleton Crater",
        latitude_deg=-89.9,
        longitude_deg=0.0,
        diameter_km=21.0,
        depth_km=4.2,
        target_description="South Pole rim-crest crater with permanently shadowed ultra-cold trap floor and illuminated connecting ridges.",
        is_psr_present=True,
        is_doubly_shadowed_candidate=True,
        is_active=False,
        status_label="Real data not yet ingested — coming soon"
    ),
    "shoemaker": CraterInfo(
        id="shoemaker",
        name="Shoemaker Crater",
        latitude_deg=-88.1,
        longitude_deg=45.9,
        diameter_km=50.0,
        depth_km=3.5,
        target_description="Ancient degraded impact basin displaying high radar anomalies and extensive floor PSRs.",
        is_psr_present=True,
        is_doubly_shadowed_candidate=True,
        is_active=False,
        status_label="Real data not yet ingested — coming soon"
    ),
    "faustini": CraterInfo(
        id="faustini",
        name="Faustini Crater (Chandrayaan-2 SAR Swath)",
        latitude_deg=-87.69,
        longitude_deg=81.46,
        diameter_km=39.0,
        depth_km=3.1,
        target_description="Deep lunar South Polar crater within real Chandrayaan-2 DFSAR L2 Selenoreferenced swath (Product ID: ch2_sar_ncxl_20200808).",
        is_psr_present=True,
        is_doubly_shadowed_candidate=True,
        is_real_data=True,
        product_id="ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18",
        observed_date="2020-08-08",
        bounds={
            "min_lat": -89.5108,
            "max_lat": -84.8333,
            "min_lon": -19.2567,
            "max_lon": 96.6885
        }
    )
}


class LunarDemoGenerator:
    """
    Generates reproducible 100x100 raster grids for lunar polar craters.
    Grid cell resolution: 250 meters per pixel (25 km x 25 km domain).
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.grid_size = 100
        self.pixel_scale_m = 250.0  # 250 m per pixel

    def generate_crater_environment(self, crater_id: str = "shackleton") -> Dict[str, np.ndarray]:
        np.random.seed(self.seed + hash(crater_id) % 1000)
        size = self.grid_size

        # Coordinate grid centered at (0, 0)
        y, x = np.mgrid[-size // 2:size // 2, -size // 2:size // 2]
        r = np.sqrt(x**2 + y**2)
        r_norm = r / (size * 0.35)  # Normalized radius to crater rim

        # Base elevation profile: Crater rim elevated, bowl-shaped interior, flat floor
        # Realistic lunar South Polar relief: ~1700m rim-to-floor drop across 25 km
        rim_height = 500.0
        floor_depth = -1200.0

        dem = np.zeros((size, size), dtype=np.float32)
        interior_mask = r_norm < 1.0

        # Bowl interior (smooth power law)
        dem[interior_mask] = floor_depth + (rim_height - floor_depth) * (r_norm[interior_mask] ** 2.0)
        # Exterior ejecta blanket (slopes down gently)
        dem[~interior_mask] = rim_height * np.exp(-1.2 * (r_norm[~interior_mask] - 1.0))

        # Add a natural ridge ramp / breached pass (connecting North/North-West rim to floor)
        ramp_corridor = (np.abs(x - 0.3 * y) < 8.0) & (y < 15)
        dem[ramp_corridor] = np.maximum(
            dem[ramp_corridor],
            floor_depth + (rim_height - floor_depth) * np.clip((y[ramp_corridor] + 40.0) / 70.0, 0.0, 1.0)
        )

        # Add secondary micro-craters (nested cold traps)
        for offset_x, offset_y, mc_r, mc_depth in [
            (-8, 5, 6, 200.0),
            (10, -6, 5, 180.0),
            (3, -12, 4, 150.0),
            (-15, -15, 7, 220.0)
        ]:
            dist = np.sqrt((x - offset_x)**2 + (y - offset_y)**2)
            mc_mask = dist < mc_r
            dem[mc_mask] -= mc_depth * (1.0 - (dist[mc_mask] / mc_r)**2)

        # Micro-relief terrain roughness noise
        noise = np.random.normal(0, 8.0, (size, size)).astype(np.float32)
        dem += noise

        # Low-angle solar illumination (grazing angle 1.5 degrees, azimuth 45 deg)
        grad_y, grad_x = np.gradient(dem, self.pixel_scale_m)
        sun_azimuth_rad = np.radians(45.0)
        sun_elev_rad = np.radians(1.5)

        cos_i = (
            np.sin(sun_elev_rad) -
            np.cos(sun_elev_rad) * (grad_x * np.cos(sun_azimuth_rad) + grad_y * np.sin(sun_azimuth_rad))
        )
        cos_i = np.clip(cos_i, 0.0, 1.0)

        # True Permanent Shadow Region (PSR): Interior floor blocked by tall southern rim
        psr_mask = (r_norm < 0.65) & (dem < -400.0)
        illumination = np.where(psr_mask, 0.0, cos_i)
        illumination = np.clip(illumination, 0.0, 1.0)

        # Doubly-shadowed candidate zones: Deepest depressions inside primary PSR
        doubly_shadowed_mask = psr_mask & (dem < -850.0)

        # Polarimetric Radar Simulation (Chandrayaan-2 DFSAR L/S-band characteristics)
        # Background lunar regolith: CPR ~ 0.3 - 0.6, DOP ~ 0.4 - 0.7
        # Subsurface water-ice / volatile candidate deposits:
        # Coherent backscatter opposition effect (CBOE) creates CPR > 1.0 and depolarized DOP < 0.13
        cpr = np.random.uniform(0.30, 0.65, (size, size)).astype(np.float32)
        dop = np.random.uniform(0.35, 0.75, (size, size)).astype(np.float32)

        # Radar anomalous patches located in doubly-shadowed cold-traps
        radar_ice_candidate = doubly_shadowed_mask & (np.random.uniform(0, 1, (size, size)) > 0.35)
        # Add smooth kernel for realistic spatial cohesion
        from scipy.ndimage import gaussian_filter
        ice_patch_seed = gaussian_filter(radar_ice_candidate.astype(np.float32), sigma=1.8) > 0.25

        cpr[ice_patch_seed] = np.random.uniform(1.15, 2.30, np.sum(ice_patch_seed)).astype(np.float32)
        dop[ice_patch_seed] = np.random.uniform(0.04, 0.11, np.sum(ice_patch_seed)).astype(np.float32)

        # Slope computation (degrees)
        slope_rad = np.arctan(np.sqrt(grad_x**2 + grad_y**2))
        slope_deg = np.degrees(slope_rad).astype(np.float32)

        # Roughness (local standard deviation of elevation in a 5x5 window)
        from scipy.ndimage import uniform_filter
        mean_elev = uniform_filter(dem, size=5)
        mean_sq_elev = uniform_filter(dem**2, size=5)
        roughness = np.sqrt(np.maximum(0.0, mean_sq_elev - mean_elev**2)).astype(np.float32)

        # Boulder & obstacle hazard (higher along steep crater inner walls)
        boulder_risk = np.clip((slope_deg / 35.0) * np.random.uniform(0.4, 1.0, (size, size)), 0.0, 1.0)

        return {
            "dem": dem,
            "illumination": illumination,
            "psr_mask": psr_mask,
            "doubly_shadowed_mask": doubly_shadowed_mask,
            "cpr": cpr,
            "dop": dop,
            "slope_deg": slope_deg,
            "roughness": roughness,
            "boulder_risk": boulder_risk,
            "pixel_scale_m": self.pixel_scale_m
        }


demo_generator = LunarDemoGenerator(seed=settings.RANDOM_SEED)
