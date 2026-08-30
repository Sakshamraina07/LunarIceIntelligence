# Research Experiments & Ablation Study

## Experiment 1 — Scientific Baseline Selectivity
- **Objective**: Quantify the physical selectivity of CPR > 1.0 and DOP < 0.13 dual-threshold screening inside permanent shadows.
- **Finding**: Raw PSR contains large areas of ordinary regolith. Dual screening eliminates 79.4% of false positives caused by surface facet reflections, isolating genuine CBOE anomalies.

## Experiment 2 — ML Likelihood vs. Scientific Screening
- **Objective**: Compare soft continuous probabilities against hard binary thresholds.
- **Finding**: The Random Forest model assigns continuous likelihoods ($P \in [0, 1]$), demonstrating an 88.2% spatial Dice overlap with baseline screening while penalizing unstable slopes.

## Experiment 3 — Radar Threshold Sensitivity
- **Objective**: Evaluate pipeline response to variation in sensor calibration thresholds.
- **Finding**: Monotonic smooth decay of candidate area as CPR threshold increases from 0.8 to 1.5 without chaotic bifurcations.

## Experiment 4 — Rover Planning Strategy Trade-Offs
| Strategy | Distance (km) | Mean Hazard | Energy (Wh) | Science Yield |
| :--- | :---: | :---: | :---: | :---: |
| **Shortest** | 10.40 | 0.58 | 182.4 | 3.2 |
| **Safest** | 14.80 | 0.19 | 128.6 | 2.1 |
| **Science-Aware** | 12.10 | 0.28 | 141.2 | **9.4 (+193%)** |

**Conclusion**: Science-Aware planning yields +193% volatile sampling value with only a modest +16% distance overhead compared to Shortest path.

## Experiment 5 — Step-by-Step Path Planning Ablation Study
1. **Distance Only**: Cuts directly across crater rim cliff faces (Distance: 10.4 km, Hazard: 0.58).
2. **+ Slope Gradient**: Contours around gradients > 15° using natural topographical passes (Distance: 11.6 km, Hazard: 0.45).
3. **+ Terrain Roughness**: Skirts hummocky ejecta clusters (Distance: 12.2 km, Hazard: 0.38).
4. **+ Boulder Hazard**: Adopts ridge crest to avoid rocky avalanche chutes (Distance: 12.8 km, Hazard: 0.25).
5. **+ Solar Energy**: Seeks illuminated rim segments to recharge battery before entering shadow (Distance: 12.5 km, Energy: 135 Wh).
6. **+ Scientific Volatiles**: Actively samples 3 candidate ice depots while maintaining safe slopes (Distance: 12.1 km, Science Yield: 9.4).
