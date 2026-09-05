import numpy as np
import tifffile
from pathlib import Path

# Repository root, derived from this file's location rather than a hardcoded
# drive letter. backend/scripts/ -> parents[2] is the root.
BASE_DIR = Path(__file__).resolve().parents[2]
raw = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"

def inspect_sri_channels():
    print("--- Inspecting SRI L-band Channels ---")
    lh_path = raw / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lh_d18.tif"
    lv_path = raw / "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lv_d18.tif"
    in_path = raw / "ch2_sar_ncxl_20200808t201154198_d_sri_in_cp_xx_d18.tif"
    ma_path = raw / "ch2_sar_ncxl_20200808t201154198_d_sri_ma_cp_xx_d18.tif"
    
    lh = tifffile.imread(lh_path).astype(np.float32)
    lv = tifffile.imread(lv_path).astype(np.float32)
    inc = tifffile.imread(in_path).astype(np.float32)
    mask = tifffile.imread(ma_path)
    
    print(f"LH shape: {lh.shape}, min: {lh.min()}, max: {lh.max()}, mean: {lh.mean()}")
    print(f"LV shape: {lv.shape}, min: {lv.min()}, max: {lv.max()}, mean: {lv.mean()}")
    print(f"IN shape: {inc.shape}, min: {inc.min()}, max: {inc.max()}, mean: {inc.mean()}")
    print(f"Mask shape: {mask.shape}, unique: {np.unique(mask)}")
    
    # Valid data area (mask > 0 or non-zero pixels)
    valid = (lh > 0) & (lv > 0)
    print(f"Valid pixels: {np.sum(valid)} ({np.sum(valid)/valid.size*100:.2f}%)")
    
    lh_v = lh[valid]
    lv_v = lv[valid]
    print(f"LH valid mean: {lh_v.mean():.2f}, median: {np.median(lh_v):.2f}, std: {lh_v.std():.2f}")
    print(f"LV valid mean: {lv_v.mean():.2f}, median: {np.median(lv_v):.2f}, std: {lv_v.std():.2f}")
    
    # Calculate CPR directly on valid pixels
    # In hybrid CP mode with LH (Left-Hand Circular transmit, H receive) and LV (Left-Hand Circular transmit, V receive):
    # Intensity powers: I_LH = LH^2, I_LV = LV^2 or DN values
    # In ISRO DFSAR L2 product, DN values represent calibrated amplitude.
    # Power = DN^2 (or normalized backscatter sigma_0)
    p_lh = lh ** 2
    p_lv = lv ** 2
    
    # S0 = p_lh + p_lv
    # S1 = p_lh - p_lv
    # Relative phase delta (if in_path is phase or incidence):
    # Let's check incidence values
    print("Incidence valid sample:", inc[valid][:10])
    
    # CPR computation
    # For m-chi decomposition / Stokes or direct power ratio:
    cpr = (p_lv) / (p_lh + 1e-6)
    valid_cpr = cpr[valid]
    print(f"Direct Power CPR valid min: {valid_cpr.min():.4f}, max: {valid_cpr.max():.4f}, mean: {valid_cpr.mean():.4f}, median: {np.median(valid_cpr):.4f}")
    
    # Check Stokes with delta phase
    # delta_phi = inc (if inc is relative phase)
    # Let's inspect inc range
    print(f"IN valid min: {inc[valid].min()}, max: {inc[valid].max()}, mean: {inc[valid].mean()}")

if __name__ == "__main__":
    inspect_sri_channels()
