# Assumptions & Scientific Limitations

## Mission Assumptions (Centralized Configuration)
1. **Radar Polarimetry Baseline**:
   - `CPR_THRESHOLD = 1.00`: Minimum circular polarization ratio indicating CBOE scattering.
   - `DOP_THRESHOLD = 0.13`: Maximum degree of polarization indicating diffuse volume depolarization.
2. **Volumetric Model Parameters**:
   - Assumed Depth: 2.0m (Conservative), 5.0m (Expected), 10.0m (Upper Bound).
   - Ice Volume Fraction: 5% (Conservative), 15% (Expected), 30% (Upper Bound).
   - Water Ice Density: 930 kg/m³.
   - Regolith Bulk Density: 1500 kg/m³.
3. **Rover Mechanics & Power**:
   - Mass: 30 kg (Pragyan-class micro-rover).
   - Nominal Speed: 0.05 m/s (180 m/hr).
   - Base Electrical Load: 25.0 W.
   - Peak Solar Generation: 50.0 W under normal incidence.
   - Maximum Slope Limit: 20.0° operational / 22.0° impassable cliff barrier.
4. **Reproducibility**:
   - Random Seed: 42. Fixed deterministic execution guarantees identical outputs across platforms.

## Scientific Limitations
- Radar anomalies do NOT constitute definitive proof of water ice; ground truth confirmation requires surface drilling or gamma-ray/neutron spectroscopy.
- ML likelihood estimates are research prototypes trained on synthetic physical response curves and must not be cited as empirical field accuracy.
- Volume figures represent computational ranges ("Estimated Ice-Equivalent Volume", never "Measured").
