# LUNAR ICE INTELLIGENCE (Version 2.0)
### Chandrayaan-2 Based Subsurface Ice Detection, Landing-Site Selection & Science-Aware Rover Traverse Planning

**Project Type:** Final Year Engineering Capstone Project  
**Domain:** Planetary Remote Sensing · Radar Polarimetry · GIS · Machine Learning · Optimization & Rover Navigation  
**Architecture:** Python FastAPI Backend + React TypeScript GIS Mission Control  

---

## 1. System Overview
The **Lunar Ice Intelligence System** is an end-to-end scientific decision-support prototype designed for lunar South Polar exploration. It answers the complete mission chain:
1. **Where are the permanent and doubly-shadowed cold-traps?** (Module A)
2. **Which regions show radar characteristics consistent with potential ice?** (Module B: CPR > 1.0 & DOP < 0.13)
3. **What is the machine learning ice likelihood and confidence?** (Module C: Explainable Random Forest)
4. **Which surrounding terrain is safe for landing?** (Module D: Hazard Index combining slope, roughness, boulders)
5. **Where is the optimal landing site?** (Module E: Multi-criteria algorithmic ranking)
6. **What route should a rover take to safely reach the ice?** (Module F: Multi-objective A* vs Dijkstra comparing Shortest, Safest, and Science-Aware strategies)
7. **How much ice-equivalent material might exist?** (Module G: 3-tier uncertainty range: Conservative, Expected, Upper)
8. **What are the scientific limitations?** (Transparent reporting without fabricated ground truth)

---

## 2. Quick Start Guide

### Prerequisites
- Python 3.10+ (Installed: Python 3.13.1)
- Node.js 18+ & npm (Installed: Node v22.13.0, npm 10.9.2)

### One-Click Launch (All Services)
Simply run the launcher script from the project root:
```powershell
.\run.bat
```
This automatically boots both the FastAPI backend (port 8000) and the unified GIS Mission Control (port 5173), and opens `http://localhost:5173/` in your browser.

---

### Manual Step-by-Step Launch

### 1. Launch Backend (FastAPI)
```powershell
cd d:\FYP\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- API Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 2. Launch Frontend (GIS Mission Control)
Run from the root or frontend folder:
```powershell
npm run dev
```
- Dashboard URL: [http://localhost:5173/](http://localhost:5173/)

### 3. Run Automated Pytest Suite
```powershell
cd d:\FYP\backend
python -m pytest -v tests/
```

---

## 3. Scientific First & Engineering Reliability
- **Dual Mode Operation**:
  - `DATA MODE: DEMO`: Powered by deterministic synthetic South Polar lunar terrain models (Shackleton, Shoemaker, Faustini) using fixed random seed (42).
  - `DATA MODE: REAL`: Ingests user-supplied Chandrayaan-2 DFSAR, OHRC, and LOLA/DEM GeoTIFF rasters.
- **Explainable AI**: The Random Forest model provides soft continuous probability $P(\text{ice} \mid \text{features}) \in [0, 1]$ and explicit explainability notes without replacing scientific screening.
- **PRD Data Limitation Compliance**: In the absence of validated direct in-situ ground truth for polar subsurface ice, **NO FAKE ACCURACY OR ROC-AUC NUMBERS ARE REPORTED**.

---

## 4. Documentation Index
Detailed technical documentation is available in the [`docs/`](file:///d:/FYP/docs) directory:
- [System Architecture](file:///d:/FYP/docs/architecture.md)
- [Scientific Methodology](file:///d:/FYP/docs/scientific-methodology.md)
- [Machine Learning Methodology](file:///d:/FYP/docs/ml-methodology.md)
- [Rover Path Planning & Energy Model](file:///d:/FYP/docs/rover-planning.md)
- [Research Experiments & Ablation Study](file:///d:/FYP/docs/experiments.md)
- [Assumptions & Scientific Limitations](file:///d:/FYP/docs/assumptions.md)
- [Testing & Verification Guide](file:///d:/FYP/docs/testing.md)
