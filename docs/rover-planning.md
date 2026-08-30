# Rover Traverse Planning: Lunar Ice Intelligence v2.0

## 1. Graph Representation
The lunar terrain is modeled as an 8-connected grid graph where nodes represent 250m × 250m surface cells and edges represent orthogonal or diagonal traversals.

## 2. Multi-Objective Traverse Cost Function
$$\text{Cost}(u, v) = w_{\text{dist}} \cdot \text{Dist}(u, v) + w_{\text{hazard}} \cdot \text{Hazard}(v) + w_{\text{energy}} \cdot E(u, v) - w_{\text{science}} \cdot \text{Science}(v)$$
Where:
- $\text{Dist}(u, v)$: Edge physical length (1.0 for orthogonal, $\sqrt{2}$ for diagonal).
- $\text{Hazard}(v)$: Normalized terrain risk ($[0, 1]$).
- $E(u, v)$: Normalized energy expenditure based on slope climbing and roughness.
- $\text{Science}(v)$: Volatile sampling incentive (reduces cost when traversing high-likelihood ice cells).

## 3. Comparison of Three Route Strategies
1. **Shortest Path**: Distance-only minimization ($w_{\text{dist}} = 1.0, \text{others} = 0.0$). Generates the most direct line but frequently cuts across dangerous boulder-strewn slopes.
2. **Safest Path**: Hazard avoidance prioritization ($w_{\text{hazard}} = 0.85, w_{\text{dist}} = 0.15$). Makes extensive detours around slopes, completely missing scientific sampling opportunities.
3. **Science-Aware Path**: Balanced multi-objective optimization. Safely ingresses the crater via natural breached ridge ramps and actively visits candidate ice depots while maintaining battery safety.

## 4. Simplified Engineering Energy Model
- **Rover Class**: Pragyan-class exploration micro-rover ($M = 30\text{ kg}, v = 0.05\text{ m/s}$).
- **Base Power**: $P_{\text{base}} = 25.0\text{ W}$ (avionics, communications, payload heaters).
- **Slope Work**: $P_{\text{climb}} = M \cdot g_{\text{moon}} \cdot v \cdot \sin(\theta)$ with $g_{\text{moon}} = 1.62\text{ m/s}^2$.
- **Roughness Work**: $P_{\text{rough}} = \min(25.0, \text{Roughness} \cdot 0.8)\text{ W}$.
- **Solar Power Generation**: $P_{\text{solar}} = 50.0\text{ W} \times \text{Illumination}$.
- **Net Power Draw**: $P_{\text{net}} = \max(5.0, P_{\text{base}} + P_{\text{climb}} + P_{\text{rough}} - P_{\text{solar}})$.
- **Energy**: $E = P_{\text{net}} \times \Delta t\text{ (Wh)}$.

> **Label:** SIMPLIFIED ENGINEERING ESTIMATE (Does not claim flight-certified dynamic simulation).

## 5. Impassable Terrain & Failure Handling
When continuous cliff walls (> 22.0°) enclose the crater target, the planner returns:
`NO FEASIBLE PATH FOUND: Impassable crater wall gradients (> 22°) obstruct all traversable channels.`
The system never fabricates impossible routes.
