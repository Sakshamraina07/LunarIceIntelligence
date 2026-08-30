# Scientific Methodology: Lunar Ice Intelligence v2.0

## 1. Permanent Shadow & Doubly-Shadowed Cold-Traps (Module A)
- **Grazing Angle Solar Ray-Tracing**: At lunar polar latitudes (> 85°S), the Sun hovers between 1.0° and 2.0° above the local horizon. Deep impact craters intercept direct sunlight, creating Permanent Shadow Regions (PSRs).
- **Distinction Between PSR and Doubly-Shadowed Traps**:
  - *Primary PSR*: Regions receiving zero direct solar irradiance, but potentially illuminated by secondarily scattered photons from warm sunlit crater rims.
  - *Doubly-Shadowed Pockets*: Micro-craters and steep-walled nested depressions within the primary PSR floor that are geometrically shielded from both primary solar radiation and secondary rim reflection. Equilibrium temperatures remain < 40 K, permitting the stable preservation of volatile water ice over geologic timescales.

## 2. Polarimetric Radar Physics (Module B)
- **Circular Polarization Ratio (CPR)**:
  $$\text{CPR} = \frac{\sigma_{SC}}{\sigma_{OC}}$$
  where $\sigma_{SC}$ is same-sense circular backscatter and $\sigma_{OC}$ is opposite-sense circular backscatter.
  - *Dry Regolith*: Dominated by single-bounce specular reflections, resulting in $\sigma_{OC} > \sigma_{SC}$ ($\text{CPR} \sim 0.3 - 0.6$).
  - *Volatile Ice Deposits*: Low-loss dielectric ice structures trigger the **Coherent Backscatter Opposition Effect (CBOE)**, causing constructive multi-bounce interference that reverses circular polarization, producing anomalously high CPR ($\text{CPR} > 1.0$).
- **Degree of Polarization (DOP)**:
  $$\text{DOP} = \frac{\sqrt{S_1^2 + S_2^2 + S_3^2}}{S_0}$$
  derived from Stokes parameters $(S_0, S_1, S_2, S_3)$. Multiple subsurface volume scattering depolarizes the return signal, driving $\text{DOP} < 0.13$.

## 3. Scientific Screening Baseline (Module C)
A grid cell qualifies as a **Candidate Ice-Bearing Region** if and only if:
$$\text{CPR} > \tau_{\text{CPR}} \quad \land \quad \text{DOP} < \tau_{\text{DOP}} \quad \land \quad \text{PSR Overlap}$$
Default thresholds: $\tau_{\text{CPR}} = 1.00$, $\tau_{\text{DOP}} = 0.13$.

> **Mandatory Scientific Limitation:** Radar anomalies meeting these criteria are strictly categorized as **"Radar signatures consistent with potential ice-bearing regions"** and never as definitive confirmation of water ice without in-situ verification.

## 4. Multi-Criteria Terrain Hazard Scoring (Module D)
Terrain hazard combines slope gradient, surface roughness, and boulder risk:
$$\text{Hazard} = \frac{w_1 \cdot \text{SlopeRisk} + w_2 \cdot \text{RoughnessRisk} + w_3 \cdot \text{BoulderRisk}}{w_1 + w_2 + w_3} \in [0, 1]$$
Default weights: $w_1 = 0.50$, $w_2 = 0.30$, $w_3 = 0.20$. Rover maximum tilt safety threshold is 20.0°; slopes exceeding 22.0° represent impassable barriers.

## 5. Volumetric Uncertainty Ranges (Module G)
Ice volume is estimated as a three-tier range:
$$\text{Volume} = \text{Area} \times \text{Assumed Depth} \times \text{Ice Volumetric Fraction}$$
- **Conservative Tier**: Depth = 2.0 m, Fraction = 5% (isolated cryo-grains).
- **Expected Tier**: Depth = 5.0 m, Fraction = 15% (LCROSS-consistent permafrost mix).
- **Upper Bound Tier**: Depth = 10.0 m, Fraction = 30% (thick ice-cemented regolith lenses).
- **Mass Calculation**: Mass = $\text{Volume} \times \rho_{\text{ice}}$ where $\rho_{\text{ice}} = 930\text{ kg/m}^3$.
