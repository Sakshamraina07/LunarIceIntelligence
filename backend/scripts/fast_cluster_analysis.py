import cv2
import numpy as np
import tifffile
from pathlib import Path

# Repository root, derived from this file's location rather than a hardcoded
# drive letter. backend/scripts/ -> parents[2] is the root.
BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"

def main():
    print("=" * 95)
    print("FAUSTINI CH2 DFSAR — FAST TOP 20 CPR CLUSTER EXTRACTION & ILLUMINATION ANALYSIS")
    print("=" * 95)
    
    lh_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lh_d18.tif"
    lv_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lv_d18.tif"
    inc_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_in_cp_xx_d18.tif"
    mask_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_ma_cp_xx_d18.tif"
    
    lh = tifffile.imread(lh_path).astype(np.float32)
    lv = tifffile.imread(lv_path).astype(np.float32)
    inc = tifffile.imread(inc_path).astype(np.float32)
    mask = tifffile.imread(mask_path)
    
    valid = (lh > 0) & (lv > 0) & (inc > 0) & (mask > 0)
    
    G_lh = 1.018442
    G_lv = 1.000923
    p_lh_cal = (lh / G_lh)**2
    p_lv_cal = (lv / G_lv)**2
    
    # 3x3 multi-look boxcar filter for fast spatial coherence
    k3 = np.ones((3, 3), np.float32) / 9.0
    p_lh_3 = cv2.filter2D(p_lh_cal, -1, k3)
    p_lv_3 = cv2.filter2D(p_lv_cal, -1, k3)
    
    sqrt_lh_3 = np.sqrt(np.maximum(p_lh_3, 0))
    sqrt_lv_3 = np.sqrt(np.maximum(p_lv_3, 0))
    sc_3 = 0.5 * (sqrt_lh_3 - sqrt_lv_3)**2
    oc_3 = 0.5 * (sqrt_lh_3 + sqrt_lv_3)**2
    cpr_3x3 = np.where(valid, sc_3 / (oc_3 + 1e-8), 0.0)
    
    # Also raw 1x1 CPR
    sc_1 = 0.5 * (np.sqrt(p_lh_cal) - np.sqrt(p_lv_cal))**2
    oc_1 = 0.5 * (np.sqrt(p_lh_cal) + np.sqrt(p_lv_cal))**2
    cpr_1x1 = np.where(valid, sc_1 / (oc_1 + 1e-8), 0.0)
    
    # Extract top 0.1% CPR pixels
    threshold = float(np.percentile(cpr_3x3[valid], 99.9))
    print(f"99.9th Percentile CPR Threshold (3x3 Boxcar): {threshold:.6f}")
    
    binary = ((cpr_3x3 >= threshold) & valid).astype(np.uint8)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, 8)
    
    print(f"Total candidate CPR clusters segmented: {num_labels - 1}")
    
    clusters = []
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= 2:  # 2+ pixels
            cluster_mask = (labels == i)
            max_cpr_3 = float(np.max(cpr_3x3[cluster_mask]))
            max_cpr_1 = float(np.max(cpr_1x1[cluster_mask]))
            mean_cpr_3 = float(np.mean(cpr_3x3[cluster_mask]))
            cx, cy = centroids[i]
            mean_inc = float(np.mean(inc[cluster_mask]))
            
            # High incidence angle (>32°) indicates steep crater rim / interior slope (shadow candidate)
            is_psr = (mean_inc > 32.0) or (mean_inc < 6.0)
            
            clusters.append({
                "area": area,
                "max_cpr_3x3": max_cpr_3,
                "max_cpr_1x1": max_cpr_1,
                "mean_cpr_3x3": mean_cpr_3,
                "row": int(round(cy)),
                "col": int(round(cx)),
                "inc_deg": mean_inc,
                "context": "Crater Slope / PSR Candidate" if is_psr else "Illuminated Regolith"
            })
            
    clusters.sort(key=lambda x: x["max_cpr_3x3"], reverse=True)
    
    print("\n" + "=" * 105)
    print(f"{'Rank':<5} | {'Row (px)':<9} | {'Col (px)':<9} | {'Area (px)':<9} | {'Max CPR (3x3)':<14} | {'Raw CPR (1x1)':<14} | {'Inc. Angle':<10} | {'Terrain / Illumination Context'}")
    print("=" * 105)
    for idx, c in enumerate(clusters[:20], 1):
        print(f"{idx:<5} | {c['row']:<9} | {c['col']:<9} | {c['area']:<9} | {c['max_cpr_3x3']:<14.5f} | {c['max_cpr_1x1']:<14.5f} | {c['inc_deg']:<10.2f}° | {c['context']}")
    print("=" * 105)

if __name__ == "__main__":
    main()
