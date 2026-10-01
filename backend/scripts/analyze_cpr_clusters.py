import os
import cv2
import numpy as np
import tifffile
from pathlib import Path
from scipy.ndimage import label, center_of_mass

# Repository root, derived from this file's location rather than a hardcoded
# drive letter. backend/scripts/ -> parents[2] is the root.
BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
# Output directory: the LUNAR_ICE_OUT_DIR environment variable, else a gitignored scratch folder under data/ (was a hard-coded
# path under a Windows user profile). Nothing else changed.
OUT_DIR = Path(os.environ.get("LUNAR_ICE_OUT_DIR", str(BASE_DIR / "data" / "derived" / "scratch")))
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    print("=" * 80)
    print("FAUSTINI SWATH — TOP 20 CPR CLUSTER ANALYSIS & ILLUMINATION CROSS-REFERENCE")
    print("=" * 80)
    
    lh_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lh_d18.tif"
    lv_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lv_d18.tif"
    inc_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_in_cp_xx_d18.tif"
    mask_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_ma_cp_xx_d18.tif"
    
    lh = tifffile.imread(lh_path).astype(np.float32)
    lv = tifffile.imread(lv_path).astype(np.float32)
    inc = tifffile.imread(inc_path).astype(np.float32)
    mask = tifffile.imread(mask_path)
    
    valid = (lh > 0) & (lv > 0) & (inc > 0) & (mask > 0)
    
    # Radiometric calibration parameters (ignoring common factors for ratio)
    G_lh = 1.018442
    G_lv = 1.000923
    
    p_lh_cal = (lh / G_lh)**2
    p_lv_cal = (lv / G_lv)**2
    
    # 1. Evaluate 1x1 (raw), 3x3, and 5x5 smoothing
    k3 = np.ones((3, 3), np.float32) / 9.0
    p_lh_3 = cv2.filter2D(p_lh_cal, -1, k3)
    p_lv_3 = cv2.filter2D(p_lv_cal, -1, k3)
    
    sqrt_lh_3 = np.sqrt(np.maximum(p_lh_3, 0))
    sqrt_lv_3 = np.sqrt(np.maximum(p_lv_3, 0))
    sc_3 = 0.5 * (sqrt_lh_3 - sqrt_lv_3)**2
    oc_3 = 0.5 * (sqrt_lh_3 + sqrt_lv_3)**2
    cpr_3x3 = np.where(valid, sc_3 / (oc_3 + 1e-8), 0.0)
    
    # 2. Extract top 0.1% CPR clusters
    top_threshold = float(np.percentile(cpr_3x3[valid], 99.9))
    print(f"99.9th Percentile CPR Threshold (3x3 Boxcar): {top_threshold:.6f}")
    
    binary_map = (cpr_3x3 >= top_threshold) & valid
    labeled_array, num_features = label(binary_map)
    print(f"Total candidate CPR clusters segmented: {num_features}")
    
    clusters = []
    for i in range(1, num_features + 1):
        cluster_mask = (labeled_array == i)
        size = int(np.sum(cluster_mask))
        if size >= 2:  # Spatially coherent feature (2+ pixels)
            max_cpr = float(np.max(cpr_3x3[cluster_mask]))
            mean_cpr = float(np.mean(cpr_3x3[cluster_mask]))
            cy, cx = center_of_mass(cluster_mask)
            mean_inc = float(np.mean(inc[cluster_mask]))
            
            # Cross-reference with incidence angle / terrain illumination
            # In polar SAR, steep interior crater slopes have high incidence angles (>35°)
            # or low grazing illumination (<5°)
            is_psr = (mean_inc > 32.0) or (mean_inc < 6.0)
            
            clusters.append({
                "id": i,
                "size": size,
                "max_cpr": max_cpr,
                "mean_cpr": mean_cpr,
                "row": int(round(cy)),
                "col": int(round(cx)),
                "inc_deg": mean_inc,
                "terrain_type": "Crater Interior / PSR Candidate" if is_psr else "Illuminated Regolith Slope"
            })
            
    # Sort by max_cpr descending
    clusters.sort(key=lambda x: x["max_cpr"], reverse=True)
    
    print("\n" + "=" * 95)
    print(f"{'Rank':<5} | {'Row (px)':<9} | {'Col (px)':<9} | {'Size (px)':<9} | {'Max CPR':<10} | {'Mean CPR':<10} | {'Inc. Angle':<10} | {'Terrain / Illumination Context'}")
    print("=" * 95)
    for idx, c in enumerate(clusters[:20], 1):
        print(f"{idx:<5} | {c['row']:<9} | {c['col']:<9} | {c['size']:<9} | {c['max_cpr']:<10.5f} | {c['mean_cpr']:<10.5f} | {c['inc_deg']:<10.2f}° | {c['terrain_type']}")
    print("=" * 95)

if __name__ == "__main__":
    main()
