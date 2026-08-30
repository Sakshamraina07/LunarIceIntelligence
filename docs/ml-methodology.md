# Machine Learning Methodology: Lunar Ice Intelligence v2.0

## 1. Objective
The ML component estimates the continuous posterior probability:
$$P(\text{candidate ice} \mid \text{available features}) \in [0, 1]$$
rather than returning an unexplainable binary output.

## 2. Model Architecture
- **Algorithm**: Random Forest Classifier (`sklearn.ensemble.RandomForestClassifier`).
- **Hyperparameters**: `n_estimators = 50`, `max_depth = 6`, `random_state = 42`.
- **Rationale**: Random Forests provide robust non-linear feature interaction, guard against overfitting in low-sample regimes, and allow direct feature importance evaluation.

## 3. Feature Vectors
For every grid cell, the feature vector consists of:
1. **CPR**: Circular Polarization Ratio ($\sigma_{SC} / \sigma_{OC}$).
2. **DOP**: Degree of Polarization ($\sqrt{S_1^2 + S_2^2 + S_3^2} / S_0$).
3. **Slope**: Local gradient in degrees derived from DEM.
4. **Roughness**: Terrain Ruggedness Index (TRI / local variance).
5. **Illumination**: Grazing solar irradiance ratio ($[0, 1]$).
6. **PSR Membership**: Binary indicator of permanent shadow.

## 4. PRD Data Limitation Rule Adherence
> **Critical Rule:** In the absence of validated direct in-situ ground truth for polar subsurface ice across large areas, **NO FABRICATED ACCURACY, PRECISION, RECALL, OR ROC-AUC METRICS ARE REPORTED.**
> The ML model functions as a research prototype demonstrating multi-sensor data fusion. The deterministic scientific baseline remains the primary screening gate.

## 5. Explainability & Confidence
- **High Confidence**: Requires CPR $\gg 1.0$, DOP $\ll 0.13$, spatial overlap with a doubly-shadowed cold-trap, and mean ML likelihood $> 0.70$.
- **Medium Confidence**: Meets baseline screening criteria with ML likelihood $> 0.50$.
- **Low Confidence**: Peripheral radar anomalies in marginal shadow.
