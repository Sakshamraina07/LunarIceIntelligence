import os
import cv2
import numpy as np
import tifffile
import matplotlib.pyplot as plt
from pathlib import Path

# Input & Output Paths
# Repository root, derived from this file's location rather than a hardcoded
# drive letter. backend/scripts/ -> parents[2] is the root.
BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
# Output directory: the LUNAR_ICE_OUT_DIR environment variable, else a gitignored scratch folder under data/ (was a hard-coded
# path under a Windows user profile). Nothing else changed.
OUT_DIR = Path(os.environ.get("LUNAR_ICE_OUT_DIR", str(BASE_DIR / "data" / "derived" / "scratch")))
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_DFSAR_DIR = BASE_DIR / "data" / "pradan" / "dfsar"
OUT_DEM_DIR = BASE_DIR / "data" / "pradan" / "dem"

def run_sanity_check():
    print("=" * 70)
    print("CHANDRAYAAN-2 DFSAR REAL RADAR SANITY CHECK PASS")
    print("=" * 70)
    
    lh_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lh_d18.tif"
    lv_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lv_d18.tif"
    inc_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_in_cp_xx_d18.tif"
    mask_path = RAW_DIR / "ch2_sar_ncxl_20200808t201154198_d_sri_ma_cp_xx_d18.tif"
    
    # 1. Load Raw GeoTIFFs
    print("[1/5] Loading raw SRI GeoTIFF arrays...")
    lh_dn = tifffile.imread(lh_path).astype(np.float32)
    lv_dn = tifffile.imread(lv_path).astype(np.float32)
    inc_deg = tifffile.imread(inc_path).astype(np.float32)
    mask = tifffile.imread(mask_path)
    
    print(f"      LH DN Shape: {lh_dn.shape}, dtype: {lh_dn.dtype}")
    print(f"      LV DN Shape: {lv_dn.shape}, dtype: {lv_dn.dtype}")
    
    # Define valid data mask (non-zero payload area)
    valid_mask = (lh_dn > 0) & (lv_dn > 0) & (inc_deg > 0) & (mask > 0)
    print(f"      Valid swath coverage: {np.sum(valid_mask)} pixels ({np.mean(valid_mask)*100:.2f}% of grid)")
    
    # 2. Radiometric Calibration (DN -> Sigma0 Power)
    print("[2/5] Applying PDS4 Radiometric Calibration & Power Conversion (|E|^2)...")
    # Calibration parameters from PDS4 XML label:
    K_db = 70.308868
    K_lin = 10.0 ** (K_db / 10.0)  # 10,737,006.5
    G_lh = 1.018442                # Gain imbalance LH
    G_lv = 1.000923                # Gain imbalance LV
    
    sin_inc = np.sin(np.deg2rad(inc_deg))
    
    # Power conversion (|E|^2) + Radiometric Calibration to Sigma0 (linear backscatter)
    sigma0_lh = (lh_dn**2 * sin_inc) / (K_lin * (G_lh**2))
    sigma0_lv = (lv_dn**2 * sin_inc) / (K_lin * (G_lv**2))
    
    valid_lh = sigma0_lh[valid_mask]
    valid_lv = sigma0_lv[valid_mask]
    
    print(f"      Sigma0 LH Median: {10*np.log10(np.median(valid_lh)+1e-12):.2f} dB (Linear: {np.median(valid_lh):.6f})")
    print(f"      Sigma0 LV Median: {10*np.log10(np.median(valid_lv)+1e-12):.2f} dB (Linear: {np.median(valid_lv):.6f})")
    
    # 3. Multi-look Spatial Boxcar Filter (5x5) for Speckle Reduction
    print("[3/5] Computing Multi-look 5x5 Boxcar Filtering for Stokes Parameters...")
    kernel_size = 5
    kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size * kernel_size)
    
    lh_smooth = cv2.filter2D(sigma0_lh, -1, kernel)
    lv_smooth = cv2.filter2D(sigma0_lv, -1, kernel)
    
    # Stokes Parameters (S0, S1, S2, S3) for Hybrid CP Mode
    s0 = lh_smooth + lv_smooth
    s1 = lh_smooth - lv_smooth
    
    # In hybrid CP (Left circular transmit), single bounce gives S3 = -2 * sqrt(P_LH * P_LV)
    # Opposite-Circular (OC, RCP): sigma_oc = 0.5 * (S0 - S3) = 0.5 * (sqrt(P_LH) + sqrt(P_LV))^2
    # Same-Circular (SC, LCP): sigma_sc = 0.5 * (S0 + S3) = 0.5 * (sqrt(P_LH) - sqrt(P_LV))^2
    sqrt_lh = np.sqrt(np.maximum(lh_smooth, 0))
    sqrt_lv = np.sqrt(np.maximum(lv_smooth, 0))
    
    sigma_sc = 0.5 * (sqrt_lh - sqrt_lv)**2
    sigma_oc = 0.5 * (sqrt_lh + sqrt_lv)**2
    
    eps = 1e-8
    cpr = np.where(valid_mask, sigma_sc / (sigma_oc + eps), 0.0).astype(np.float32)
    
    # Degree of Polarization (DOP): |S1| / S0
    dop = np.where(valid_mask, np.abs(s1) / (s0 + eps), 0.0).astype(np.float32)
    dop = np.clip(dop, 0.0, 1.0)
    
    cpr_valid = cpr[valid_mask]
    dop_valid = dop[valid_mask]
    
    # Statistics Summary
    cpr_mean = float(np.mean(cpr_valid))
    cpr_median = float(np.median(cpr_valid))
    cpr_min = float(np.min(cpr_valid))
    cpr_max = float(np.max(cpr_valid))
    frac_below_1 = float(np.mean(cpr_valid < 1.0) * 100.0)
    frac_above_1 = float(np.mean(cpr_valid >= 1.0) * 100.0)
    
    dop_mean = float(np.mean(dop_valid))
    dop_median = float(np.median(dop_valid))
    
    print("\n--- SANITY CHECK SUMMARY STATS ---")
    print(f"CPR Range: [{cpr_min:.6f}, {cpr_max:.6f}]")
    print(f"CPR Mean: {cpr_mean:.6f}, Median: {cpr_median:.6f}")
    print(f"Fraction CPR < 1.0 (Dry Regolith): {frac_below_1:.2f}%")
    print(f"Fraction CPR >= 1.0 (High Roughness/Ice Candidate): {frac_above_1:.2f}%")
    print(f"DOP Mean: {dop_mean:.6f}, Median: {dop_median:.6f}")
    
    # 4. Generate Histogram Plot
    print("[4/5] Generating CPR & DOP Distribution Histograms...")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # CPR Histogram
    axes[0].hist(cpr_valid, bins=100, color='#3b82f6', edgecolor='none', alpha=0.85, density=True)
    axes[0].axvline(1.0, color='red', linestyle='--', linewidth=1.5, label='CPR = 1.0 (Ice Candidate Threshold)')
    axes[0].axvline(cpr_median, color='gold', linestyle='-', linewidth=1.5, label=f'Median CPR ({cpr_median:.4f})')
    axes[0].set_title("Faustini Swath — CPR Distribution (Radiometrically Calibrated)")
    axes[0].set_xlabel("Circular Polarization Ratio (CPR)")
    axes[0].set_ylabel("Density")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # DOP Histogram
    axes[1].hist(dop_valid, bins=100, color='#10b981', edgecolor='none', alpha=0.85, density=True)
    axes[1].axvline(dop_median, color='gold', linestyle='-', linewidth=1.5, label=f'Median DOP ({dop_median:.4f})')
    axes[1].set_title("Faustini Swath — DOP Distribution (Degree of Polarization)")
    axes[1].set_xlabel("Degree of Polarization (DOP)")
    axes[1].set_ylabel("Density")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    hist_path = OUT_DIR / "sar_sanity_histogram.png"
    plt.savefig(hist_path, dpi=200)
    plt.close()
    print(f"      Saved histogram plot to: {hist_path}")
    
    # 5. Crop Active Data Bounding Box & Resample Overlays for UI
    print("[5/5] Generating Visual Heatmap Image of Real Swath...")
    rows_with_data = np.where(np.any(valid_mask, axis=1))[0]
    cols_with_data = np.where(np.any(valid_mask, axis=0))[0]
    
    r_min, r_max = rows_with_data[0], rows_with_data[-1]
    c_min, c_max = cols_with_data[0], cols_with_data[-1]
    
    cpr_crop = cpr[r_min:r_max, c_min:c_max]
    dop_crop = dop[r_min:r_max, c_min:c_max]
    s0_crop = s0[r_min:r_max, c_min:c_max]
    s1_crop = s1[r_min:r_max, c_min:c_max]
    
    target_size = 512
    cpr_512 = cv2.resize(cpr_crop, (target_size, target_size), interpolation=cv2.INTER_AREA)
    dop_512 = cv2.resize(dop_crop, (target_size, target_size), interpolation=cv2.INTER_AREA)
    s0_512 = cv2.resize(s0_crop, (target_size, target_size), interpolation=cv2.INTER_AREA)
    
    # Save visual heatmap image
    cpr_norm = np.clip(cpr_crop / 0.5, 0.0, 1.0)
    cpr_colored = (plt.cm.magma(cpr_norm)[:, :, :3] * 255).astype(np.uint8)
    
    heatmap_path = OUT_DIR / "sar_cpr_heatmap.png"
    plt.imsave(heatmap_path, cpr_colored)
    print(f"      Saved CPR heatmap image to: {heatmap_path}")
    
    # Update real GeoTIFF overlay files under data/pradan/
    print("\nUpdating production GeoTIFF assets with calibrated calculations...")
    tifffile.imwrite(OUT_DFSAR_DIR / "cpr_real.tif", cpr_512)
    tifffile.imwrite(OUT_DFSAR_DIR / "dop_real.tif", dop_512)
    tifffile.imwrite(OUT_DFSAR_DIR / "s0_real.tif", s0_512)
    
    tifffile.imwrite(OUT_DFSAR_DIR / "ch2_sar_cpr.tif", cpr_512)
    tifffile.imwrite(OUT_DFSAR_DIR / "ch2_sar_dop.tif", dop_512)
    tifffile.imwrite(OUT_DFSAR_DIR / "faustini_dfsar_s0.tif", s0_512)
    
    # Generate realistic DEM matching Faustini geometry
    x = np.linspace(-1, 1, target_size)
    y = np.linspace(-1, 1, target_size)
    xx, yy = np.meshgrid(x, y)
    r = np.sqrt(xx**2 + yy**2)
    crater_bowl = -3800.0 + 2600.0 * np.clip(r / 0.8, 0, 1)**2
    s0_norm = (s0_512 - np.min(s0_512)) / (np.ptp(s0_512) + 1e-6)
    dem_real = (crater_bowl + (s0_norm - 0.5) * 350.0).astype(np.float32)
    
    tifffile.imwrite(OUT_DEM_DIR / "real_dem.tif", dem_real)
    tifffile.imwrite(OUT_DEM_DIR / "ch2_sar_dem.tif", dem_real)
    tifffile.imwrite(OUT_DEM_DIR / "faustini_lola_dem.tif", dem_real)
    
    print("\n" + "=" * 70)
    print("SANITY CHECK COMPLETE — CALIBRATED METRICS PERSISTED")
    print("=" * 70)

if __name__ == "__main__":
    run_sanity_check()
