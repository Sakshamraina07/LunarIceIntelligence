import React, { Fragment, useState } from 'react';
import type {
  MissionState,
  CraterInfo,
  CandidateLandingSite,
  SensitivityAnalysisResult
} from '../../types/mission';
import {
  CheckCircle,
  AlertTriangle,
  Download,
  Info
} from 'lucide-react';
import { getReportPdfUrl, fetchSensitivity } from '../../services/api';
import { Tooltip } from '../Common/Tooltip';

interface WorkflowViewsProps {
  currentStep: number;
  mission: MissionState;
  craters: Record<string, CraterInfo>;
  onSelectCrater: (craterId: string) => void;
  selectedLandingSite: CandidateLandingSite | null;
  onSelectLandingSite: (site: CandidateLandingSite) => void;
  onUpdateParams: (newParams: any) => void;
  cprTh: number;
  dopTh: number;
  iceDepth: number;
  iceFrac: number;
  roverAlgo: string;
  setRoverAlgo: (algo: string) => void;
}

const ContextBanner: React.FC<{ text: string; objective: string }> = ({ text, objective }) => (
  <div className="bg-cyan-950/40 border border-cyan-500/30 rounded-xl p-3.5 flex items-start gap-2.5 text-xs text-cyan-200 shadow-sm backdrop-blur-md">
    <Info className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
    <div>
      <span className="font-bold text-cyan-300 uppercase tracking-wider text-[10px] block mb-0.5">
        Plain-Language Context &amp; Objective · {objective}
      </span>
      <p className="leading-relaxed text-slate-300 text-[11px]">{text}</p>
    </div>
  </div>
);

export const WorkflowViews: React.FC<WorkflowViewsProps> = ({
  currentStep,
  mission,
  craters,
  onSelectCrater,
  selectedLandingSite,
  onSelectLandingSite,
  onUpdateParams,
  cprTh,
  dopTh,
  iceDepth,
  iceFrac,
  roverAlgo,
  setRoverAlgo
}) => {
  const [sensitivityResult, setSensitivityResult] = useState<SensitivityAnalysisResult | null>(null);

  const handleRunSensitivity = async (paramName: string) => {
    try {
      const res = await fetchSensitivity(paramName, mission.ice.scientific_candidate_area_km2);
      setSensitivityResult(res);
    } catch (err) {
      console.error(err);
    }
  };

  // Step 1: Crater Selection View
  if (currentStep === 1) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 1: South Polar Crater Selection</h3>
            <p className="text-xs text-slate-400">Select target lunar South Polar crater to initialize terrain and radar models.</p>
          </div>
          <span className="bg-cyan-500/20 text-cyan-300 font-mono text-xs px-2.5 py-1 rounded border border-cyan-500/40">
            TARGET: {mission.selected_crater.name}
          </span>
        </div>

        <ContextBanner
          objective="Target Crater Selection"
          text="Select a lunar South Polar crater to analyze. We currently focus on Faustini Crater because genuine, calibrated Chandrayaan-2 dual-frequency radar swaths are available on disk. Non-ingested craters are disabled to preserve complete scientific honesty."
        />

        <div className="grid grid-cols-1 gap-3">
          {Object.values(craters).map((c) => {
            const isActive = c.is_active ?? true; // Default to true if undefined
            return (
              <button
                key={c.id}
                onClick={() => isActive && onSelectCrater(c.id)}
                disabled={!isActive}
                className={`p-4 rounded-xl border text-left transition duration-200 ${
                  !isActive
                    ? 'bg-slate-900/40 border-slate-800 text-slate-500 cursor-not-allowed'
                    : mission.selected_crater.id === c.id
                      ? 'bg-cyan-500/15 border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.2)] text-white'
                      : 'bg-slate-800/60 border-slate-700/60 text-slate-300 hover:bg-slate-800'
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <span className={`font-bold text-sm ${isActive ? 'text-cyan-300' : 'text-slate-500'}`}>{c.name}</span>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${isActive ? 'bg-slate-900 text-slate-400 border-slate-700' : 'bg-slate-900/50 text-slate-600 border-slate-800'}`}>
                    {c.diameter_km} km
                  </span>
                </div>
                <div className={`text-xs space-y-1 mb-2 font-mono ${isActive ? 'text-slate-400' : 'text-slate-600'}`}>
                  <div>Lat: {c.latitude_deg}° S</div>
                  <div>Lon: {c.longitude_deg}° E</div>
                  <div>Depth: {c.depth_km} km</div>
                </div>
                <p className={`text-[11px] line-clamp-2 leading-relaxed ${isActive ? 'text-slate-400' : 'text-slate-600'}`}>
                  {c.target_description}
                </p>
                {!isActive && c.status_label && (
                  <div className="mt-3 text-[10px] font-bold text-amber-500/80 uppercase tracking-wider bg-amber-500/10 p-1.5 rounded border border-amber-500/20">
                    {c.status_label}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  // Step 2: Shadow & PSR Mapping View
  if (currentStep === 2) {
    const psr = mission.psr;
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 2: Permanent Shadow Region (PSR) Analysis</h3>
            <p className="text-xs text-slate-400">Ray-tracing simulation of grazing solar illumination (1.5° elevation) identifies deep thermal traps.</p>
          </div>
          <span className="bg-blue-500/20 text-blue-300 text-xs px-2.5 py-1 rounded font-mono border border-blue-500/40">
            CONFIDENCE: {psr.confidence_level.toUpperCase()}
          </span>
        </div>

        <ContextBanner
          objective="Cryogenic Cold Traps"
          text="This step simulates grazing sunlight (1.5° elevation) to find deep hollows that haven't seen sunlight for billions of years. Because temperatures remain below -233°C (40 K), water ice can survive indefinitely without evaporating into space."
        />

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase flex items-center gap-1">
              <Tooltip term="PSR Area" definition="Permanently Shadowed Region: A lunar depression shielded from direct sunlight by high topography." />
            </span>
            <div className="text-xl font-bold text-cyan-400 font-mono mt-1">{psr.psr_area_km2} km²</div>
            <span className="text-[10px] text-slate-500">{(psr.psr_area_fraction * 100).toFixed(1)}% of crater domain</span>
          </div>

          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase flex items-center gap-1">
              <Tooltip term="Doubly-Shadowed" definition="Ultra-cold micro-traps shielded from both direct sunlight and indirect reflection off sunlit crater rims." />
            </span>
            <div className="text-xl font-bold text-indigo-400 font-mono mt-1">{psr.doubly_shadowed_area_km2} km²</div>
            <span className="text-[10px] text-slate-500">Shielded from rim reflection</span>
          </div>

          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase">Mean Illumination</span>
            <div className="text-xl font-bold text-amber-400 font-mono mt-1">{(psr.mean_illumination_fraction * 100).toFixed(1)}%</div>
            <span className="text-[10px] text-slate-500">Grazing sun ratio</span>
          </div>

          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase">Estimated Shadow Depth</span>
            <div className="text-xl font-bold text-emerald-400 font-mono mt-1">{psr.shadow_depth_estimate_m} m</div>
            <span className="text-[10px] text-slate-500">Rim to floor relief</span>
          </div>
        </div>

        <div className="bg-slate-800/40 p-3 rounded-lg border border-slate-700/50 text-xs text-slate-300">
          <span className="font-semibold text-cyan-300">Scientific Note:</span> Distinguishes general PSR from nested doubly-shadowed cold-traps. True doubly-shadowed pockets remain below 40 K throughout lunar day/night cycles, enabling volatile retention over billions of years.
        </div>
      </div>
    );
  }

  // Step 3: DFSAR Radar Analysis View
  if (currentStep === 3) {
    const radar = mission.radar;
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 3: Chandrayaan-2 DFSAR Polarimetric Analysis</h3>
            <p className="text-xs text-slate-400">Stokes vector decomposition extracts Circular Polarization Ratio (CPR) and Degree of Polarization (DOP).</p>
          </div>
          <span className="bg-purple-500/20 text-purple-300 text-xs px-2.5 py-1 rounded font-mono border border-purple-500/40">
            DFSAR DUAL-POL
          </span>
        </div>

        <ContextBanner
          objective="Radar Polarimetry Screening"
          text="This shows how radar signals bounce off the lunar surface. Pure subsurface water ice scatters radar waves in a unique circular way, producing anomalous bright returns (high CPR & low DOP) that stand out from ordinary dry surface rocks."
        />

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase flex items-center gap-1">
              <Tooltip term="Mean CPR" definition="Circular Polarization Ratio: Ratio of same-sense to opposite-sense circular reflections. Values > 1.0 indicate anomalous coherent backscatter from ice." />
            </span>
            <div className="text-xl font-bold text-cyan-400 font-mono mt-1">{radar.mean_cpr}</div>
            <span className="text-[10px] text-slate-500">Peak: {radar.max_cpr} (Threshold: &gt; {radar.cpr_threshold_used})</span>
          </div>

          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase flex items-center gap-1">
              <Tooltip term="Mean DOP" definition="Degree of Polarization: Measures wave depolarization. Low values (< 0.13) indicate multiple internal volume reflections inside clear ice deposits." />
            </span>
            <div className="text-xl font-bold text-indigo-400 font-mono mt-1">{radar.mean_dop}</div>
            <span className="text-[10px] text-slate-500">Min: {radar.min_dop} (Threshold: &lt; {radar.dop_threshold_used})</span>
          </div>

          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase">Radar Anomaly Area</span>
            <div className="text-xl font-bold text-emerald-400 font-mono mt-1">{radar.radar_anomalous_area_km2} km²</div>
            <span className="text-[10px] text-slate-500">{(radar.screening_pass_fraction * 100).toFixed(2)}% of crater area</span>
          </div>

          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase">Scientific Gating</span>
            <div className="text-xl font-bold text-amber-400 font-mono mt-1">CPR &gt; 1.0</div>
            <span className="text-[10px] text-slate-500">Coherent Backscatter</span>
          </div>
        </div>

        <div className="bg-slate-800/40 p-3 rounded-lg border border-slate-700/50 text-xs space-y-1">
          <div className="font-semibold text-slate-200">Scientific Interpretation:</div>
          <p className="text-slate-300">{radar.scientific_interpretation}</p>
        </div>
      </div>
    );
  }

  // Step 4: Ice Intelligence (Scientific Screening + ML) View
  if (currentStep === 4) {
    const ice = mission.ice;
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 4: Ice Intelligence (Scientific Baseline + ML Model)</h3>
            <p className="text-xs text-slate-400">Random Forest probabilistic likelihood coupled with deterministic scientific screening.</p>
          </div>
          <div className="flex gap-2">
            <span className={`text-xs px-2.5 py-1 rounded font-mono font-bold border ${
              ice.scientific_screening_status === 'PASS'
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
            }`}>
              SCREENING: {ice.scientific_screening_status}
            </span>
            <span className="bg-cyan-500/20 text-cyan-300 text-xs px-2.5 py-1 rounded font-mono border border-cyan-500/40">
              CONFIDENCE: {ice.confidence.toUpperCase()}
            </span>
          </div>
        </div>

        <ContextBanner
          objective="Fused AI & Physics Screening"
          text="Combines deterministic physical thresholds (CPR > 1.0, DOP < 0.13, and permanent shadow overlap) with a Random Forest machine learning model to estimate the continuous likelihood of subsurface water ice."
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-3">
            <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
              <span className="text-[11px] text-slate-400 uppercase flex items-center gap-1">
                <Tooltip term="Scientific Candidate Ice Area" definition="Total surface area passing strict physical gating: CPR > 1.0 (coherent backscatter) AND DOP < 0.13 (depolarization) inside an illuminated-free cold trap." />
              </span>
              <div className="text-2xl font-bold text-cyan-400 font-mono mt-1">{ice.scientific_candidate_area_km2} km²</div>
              <span className="text-[10px] text-slate-400">Screened via CPR &gt; 1.0 &amp; DOP &lt; 0.13 &amp; PSR overlap</span>
            </div>

            <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
              <span className="text-[11px] text-slate-400 uppercase flex items-center gap-1">
                <Tooltip term="ML Ice Likelihood P(ice)" definition="Continuous probabilistic model (Random Forest, 50 estimators) predicting volatile presence from fused radar, slope, and temperature features." />
              </span>
              <div className="text-2xl font-bold text-purple-400 font-mono mt-1">{ice.ml_ice_likelihood_mean} <span className="text-xs text-slate-500 font-normal">mean</span> / {ice.ml_ice_likelihood_max} <span className="text-xs text-slate-500 font-normal">peak</span></div>
              <span className="text-[10px] text-slate-400">Random Forest (n=50, max_depth=6)</span>
            </div>
          </div>

          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-xs font-semibold text-slate-200 mb-2 block">Evidence Checklist:</span>
            <div className="space-y-1.5 text-xs">
              {Object.entries(ice.evidence_checklist).map(([k, val]) => (
                <div key={k} className="flex items-center gap-2">
                  {val ? (
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                  ) : (
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                  )}
                  <span className={val ? 'text-slate-200' : 'text-slate-400'}>
                    {k.replace(/_/g, ' ')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-slate-800/40 p-3 rounded-lg border border-slate-700/50 text-xs space-y-1">
          <div className="font-semibold text-cyan-300">Explainability Summary:</div>
          <ul className="list-disc pl-4 space-y-0.5 text-slate-300">
            {ice.explainability_notes.slice(0, 4).map((note, idx) => (
              <li key={idx}>{note}</li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  // Step 5: Terrain Hazards View
  if (currentStep === 5) {
    const terrain = mission.terrain;
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 5: Terrain Safety &amp; Hazard Scoring</h3>
            <p className="text-xs text-slate-400">Quantitative hazard index: Hazard = 0.50 × slope + 0.30 × roughness + 0.20 × boulders.</p>
          </div>
          <span className="bg-rose-500/20 text-rose-300 text-xs px-2.5 py-1 rounded font-mono border border-rose-500/40">
            HAZARD SCORE: {terrain.mean_hazard_score}
          </span>
        </div>

        <ContextBanner
          objective="Rover Terrain Safety"
          text="Calculates where it is safe for a rover to drive by scoring terrain slope steepness, surface roughness, and boulder obstacles. Areas exceeding 20° slope are flagged as impassable cliffs."
        />

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase flex items-center gap-1">
              <Tooltip term="Mean Slope" definition="Average incline in degrees computed from LOLA DEM gradients. Rover tilt limit is 20°." />
            </span>
            <div className="text-xl font-bold text-cyan-400 font-mono mt-1">{terrain.mean_slope_deg}°</div>
            <span className="text-[10px] text-slate-500">Max: {terrain.max_slope_deg}°</span>
          </div>

          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase">Traversable Fraction</span>
            <div className="text-xl font-bold text-emerald-400 font-mono mt-1">{(terrain.safe_slope_fraction * 100).toFixed(1)}%</div>
            <span className="text-[10px] text-slate-500">Slope &le; 12° landing limit</span>
          </div>

          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase flex items-center gap-1">
              <Tooltip term="Mean Roughness" definition="Terrain Ruggedness Index: Local standard deviation of elevation in a 5x5 cell moving window." />
            </span>
            <div className="text-xl font-bold text-amber-400 font-mono mt-1">{terrain.mean_roughness}</div>
            <span className="text-[10px] text-slate-500">Local TRI index</span>
          </div>

          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700/60">
            <span className="text-[11px] text-slate-400 uppercase flex items-center gap-1">
              <Tooltip term="Critical Hazard Zone" definition="High-risk zones exceeding 0.70 composite hazard index where autonomous traversal is restricted." />
            </span>
            <div className="text-xl font-bold text-rose-400 font-mono mt-1">{terrain.high_hazard_area_km2} km²</div>
            <span className="text-[10px] text-slate-500">Hazard index &ge; 0.70</span>
          </div>
        </div>

        <div className="bg-slate-800/40 p-3 rounded-lg border border-slate-700/50 text-xs text-slate-300">
          <span className="font-semibold text-slate-200">Engineering Constraint:</span> Rover mobility tilt safety cutoff is 20°. Slopes exceeding 22° are classified as impassable vertical cliff barriers during path planning.
        </div>
      </div>
    );
  }

  // Step 6: Landing Site Selection View
  if (currentStep === 6) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 6: Landing Site Selection &amp; Algorithmic Ranking</h3>
            <p className="text-xs text-slate-400">Evaluates safe rim ridges based on safety (40%), illumination (25%), science value (20%), and distance penalty (15%).</p>
          </div>
          <span className="bg-emerald-500/20 text-emerald-300 text-xs px-2.5 py-1 rounded font-mono border border-emerald-500/40">
            RECOMMENDED: {mission.recommended_landing_site.name}
          </span>
        </div>

        <ContextBanner
          objective="Touchdown Zone Ranking"
          text="Ranks potential touchdown zones along the illuminated crater rim crests. It balances landing safety (flat slopes and minimal rocks) with close proximity and gentle driving ramps down to the ice candidate sites."
        />

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border border-slate-800">
            <thead className="bg-slate-800/80 text-slate-300 font-semibold uppercase text-[10px]">
              <tr>
                <th className="p-2.5">Rank</th>
                <th className="p-2.5">Site Name</th>
                <th className="p-2.5">Slope</th>
                <th className="p-2.5">Hazard</th>
                <th className="p-2.5">Illumination</th>
                <th className="p-2.5">Distance</th>
                <th className="p-2.5">Score</th>
                <th className="p-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {mission.landing_sites.map((site) => {
                const isSelected = selectedLandingSite?.site_id === site.site_id || (site.is_recommended && !selectedLandingSite);
                return (
                  <tr
                    key={site.site_id}
                    onClick={() => onSelectLandingSite(site)}
                    className={`cursor-pointer transition ${
                      isSelected ? 'bg-cyan-500/15 text-cyan-200' : 'hover:bg-slate-800/50'
                    }`}
                  >
                    <td className="p-2.5 font-bold font-mono">#{site.rank}</td>
                    <td className="p-2.5 font-semibold">{site.name}</td>
                    <td className="p-2.5 font-mono">{site.slope_deg}°</td>
                    <td className="p-2.5 font-mono">{site.hazard_score}</td>
                    <td className="p-2.5 font-mono">{(site.illumination_fraction * 100).toFixed(0)}%</td>
                    <td className="p-2.5 font-mono">{site.distance_to_target_km} km</td>
                    <td className="p-2.5 font-bold font-mono text-cyan-400">{site.composite_landing_score}</td>
                    <td className="p-2.5">
                      {site.is_recommended ? (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold">
                          RECOMMENDED
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400">
                          Alternative
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Selected Site Explanation */}
        {selectedLandingSite && (
          <div className="bg-slate-800/40 p-3 rounded-lg border border-slate-700 text-xs">
            <span className="font-semibold text-cyan-300">Selection Rationale for {selectedLandingSite.name}:</span>
            <ul className="list-disc pl-4 space-y-0.5 text-slate-300 mt-1">
              {selectedLandingSite.selection_rationale.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  // Step 7: Rover Path Planning View
  if (currentStep === 7) {
    const routes = mission.rover_routes;
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 7: Rover Path Planning &amp; Multi-Strategy Comparison</h3>
            <p className="text-xs text-slate-400">Compares Shortest, Safest, and Science-Aware trajectories using A* and Dijkstra graph search.</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Algorithm:</span>
            <select
              value={roverAlgo}
              onChange={(e) => setRoverAlgo(e.target.value)}
              className="bg-slate-800 text-cyan-300 text-xs font-mono px-2.5 py-1 rounded border border-slate-700"
            >
              <option value="A*">A* (Heuristic Guided)</option>
              <option value="Dijkstra">Dijkstra (Exhaustive)</option>
            </select>
          </div>
        </div>

        <ContextBanner
          objective="Multi-Strategy Traverse Routing"
          text="Calculates and compares three different autonomous rover driving routes from the touchdown rim to the ice deposit: the shortest direct distance, the safest hazard-avoiding contour, and a science-optimized path that surveys secondary cold traps."
        />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {['Shortest', 'Safest', 'Science-Aware'].map((strat) => {
            const r = routes[strat];
            const isSci = strat === 'Science-Aware';
            return (
              <div
                key={strat}
                className={`p-4 rounded-xl border ${
                  isSci
                    ? 'bg-cyan-500/10 border-cyan-500/50 shadow-[0_0_15px_rgba(6,182,212,0.15)]'
                    : 'bg-slate-800/60 border-slate-700/60'
                }`}
              >
                <div className="flex justify-between items-center mb-3">
                  <span className={`font-bold text-sm ${isSci ? 'text-cyan-300' : 'text-slate-200'}`}>
                    {strat} Path
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-400">
                    {r.algorithm_used}
                  </span>
                </div>

                <div className="space-y-2 text-xs font-mono">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Distance:</span>
                    <span className="font-bold text-slate-100">{r.total_distance_km} km</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Travel Time:</span>
                    <span className="text-slate-100">{r.estimated_travel_time_hours} hrs</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Est. Energy:</span>
                    <span className="text-slate-100">{r.total_energy_wh} Wh</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Mean Hazard:</span>
                    <span className="text-slate-100">{r.mean_hazard_encountered}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Science Yield:</span>
                    <span className={`font-bold ${isSci ? 'text-cyan-400' : 'text-slate-100'}`}>
                      {r.total_scientific_value_collected}
                    </span>
                  </div>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-800 text-[11px] text-slate-400">
                  {r.avoidance_explanations[0] || 'Nominal traverse path.'}
                </div>
              </div>
            );
          })}
        </div>

        <div className="bg-slate-800/40 p-3 rounded-lg border border-slate-700 text-xs text-slate-300">
          <span className="font-semibold text-cyan-300">Scientific Value Trade-off:</span> Science-Aware and Shortest are compared on distance, mean hazard and maximum slope above — all three read from this run. The scientific-yield comparison is <span className="font-mono text-slate-400">NO DATA</span>: no science-value raster is ingested, so the routes cannot be ranked on what they would sample.
        </div>
      </div>
    );
  }

  // Step 8: Volume Estimation View
  if (currentStep === 8) {
    const vol = mission.volume;
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 8: Ice-Equivalent Volume Estimation</h3>
            <p className="text-xs text-slate-400">Calculates 3-tier uncertainty range: Volume = Candidate Area × Assumed Depth × Ice Fraction.</p>
          </div>
          <span className="bg-sky-500/20 text-sky-300 text-xs px-2.5 py-1 rounded font-mono border border-sky-500/40">
            {vol.scientific_label.toUpperCase()}
          </span>
        </div>

        <ContextBanner
          objective="3-Tier Resource Assessment"
          text="Estimates the total volume and metric tonnage of water ice in the identified candidate area across conservative, expected, and upper-bound scenarios based on assumed permafrost depth and porosity."
        />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* Conservative */}
          <div className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
            <span className="text-xs font-semibold text-amber-400 uppercase flex items-center gap-1">
              <Tooltip term="Conservative Tier" definition="Worst-case estimate: Shallow 2m depth with 5% ice pore-volume fraction." />
            </span>
            <div className="text-2xl font-bold font-mono text-slate-100 mt-2">
              {vol.conservative_volume_m3.toLocaleString()} m³
            </div>
            <div className="text-xs font-mono text-cyan-300 mt-1">
              {vol.conservative_mass_metric_tons.toLocaleString()} Metric Tons
            </div>
            <div className="text-[11px] text-slate-400 mt-3 pt-2 border-t border-slate-700">
              Depth: {vol.conservative_assumptions.assumed_depth_m}m | Fraction: {(vol.conservative_assumptions.ice_volume_fraction * 100).toFixed(0)}%
            </div>
          </div>

          {/* Expected */}
          <div className="bg-cyan-500/15 p-4 rounded-xl border border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
            <span className="text-xs font-bold text-cyan-300 uppercase">Expected (Nominal) Tier</span>
            <div className="text-2xl font-bold font-mono text-white mt-2">
              {vol.expected_volume_m3.toLocaleString()} m³
            </div>
            <div className="text-xs font-mono text-cyan-300 mt-1 font-bold">
              {vol.expected_mass_metric_tons.toLocaleString()} Metric Tons
            </div>
            <div className="text-[11px] text-cyan-200 mt-3 pt-2 border-t border-cyan-500/40">
              Depth: {vol.expected_assumptions.assumed_depth_m}m | Fraction: {(vol.expected_assumptions.ice_volume_fraction * 100).toFixed(0)}%
            </div>
          </div>

          {/* Upper */}
          <div className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
            <span className="text-xs font-semibold text-indigo-400 uppercase">Upper Bound Tier</span>
            <div className="text-2xl font-bold font-mono text-slate-100 mt-2">
              {vol.upper_volume_m3.toLocaleString()} m³
            </div>
            <div className="text-xs font-mono text-cyan-300 mt-1">
              {vol.upper_mass_metric_tons.toLocaleString()} Metric Tons
            </div>
            <div className="text-[11px] text-slate-400 mt-3 pt-2 border-t border-slate-700">
              Depth: {vol.upper_assumptions.assumed_depth_m}m | Fraction: {(vol.upper_assumptions.ice_volume_fraction * 100).toFixed(0)}%
            </div>
          </div>
        </div>

        <div className="bg-rose-950/20 border border-rose-800/40 p-3 rounded-lg text-xs text-rose-200">
          <span className="font-semibold text-rose-300">Mandatory PRD Scientific Limitation:</span> {vol.limitation_statement}
        </div>
      </div>
    );
  }

  // Step 9: Sensitivity Studio View
  if (currentStep === 9) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 9: Interactive Sensitivity Studio</h3>
            <p className="text-xs text-slate-400">Dynamically vary core scientific thresholds to verify pipeline convergence and stability.</p>
          </div>
        </div>

        <ContextBanner
          objective="Parametric Sensitivity Lab"
          text="Dynamically vary core scientific thresholds to verify pipeline convergence. Real science systems must prove they do not produce brittle or wildly unstable results when operational parameters shift."
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Sliders */}
          <div className="space-y-3 bg-slate-800/40 p-4 rounded-xl border border-slate-700">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-300 font-semibold">CPR Threshold</span>
                <span className="font-mono text-cyan-400">{cprTh.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.6"
                max="1.6"
                step="0.05"
                value={cprTh}
                onChange={(e) => onUpdateParams({ cprThreshold: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-300 font-semibold">DOP Threshold</span>
                <span className="font-mono text-cyan-400">{dopTh.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.06"
                max="0.20"
                step="0.01"
                value={dopTh}
                onChange={(e) => onUpdateParams({ dopThreshold: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-300 font-semibold">Assumed Depth (m)</span>
                <span className="font-mono text-cyan-400">{iceDepth} m</span>
              </div>
              <input
                type="range"
                min="1"
                max="12"
                step="0.5"
                value={iceDepth}
                onChange={(e) => onUpdateParams({ iceDepthM: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-300 font-semibold">Ice Volume Fraction</span>
                <span className="font-mono text-cyan-400">{(iceFrac * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0.03"
                max="0.35"
                step="0.01"
                value={iceFrac}
                onChange={(e) => onUpdateParams({ iceFraction: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400"
              />
            </div>
          </div>

          {/* Quick Sweeps */}
          <div className="space-y-3 bg-slate-800/40 p-4 rounded-xl border border-slate-700">
            <span className="text-xs font-semibold text-slate-200 block">Run Parametric Sweep Matrix:</span>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => handleRunSensitivity('cpr_threshold')}
                className="p-2 text-xs rounded bg-slate-800 hover:bg-slate-700 border border-slate-600 text-cyan-300"
              >
                Sweep CPR Threshold
              </button>
              <button
                onClick={() => handleRunSensitivity('dop_threshold')}
                className="p-2 text-xs rounded bg-slate-800 hover:bg-slate-700 border border-slate-600 text-cyan-300"
              >
                Sweep DOP Threshold
              </button>
              <button
                onClick={() => handleRunSensitivity('assumed_depth_m')}
                className="p-2 text-xs rounded bg-slate-800 hover:bg-slate-700 border border-slate-600 text-cyan-300"
              >
                Sweep Assumed Depth
              </button>
              <button
                onClick={() => handleRunSensitivity('ice_fraction')}
                className="p-2 text-xs rounded bg-slate-800 hover:bg-slate-700 border border-slate-600 text-cyan-300"
              >
                Sweep Ice Fraction
              </button>
            </div>

            {sensitivityResult && (
              <div className="mt-3 text-xs bg-slate-900/80 p-2.5 rounded border border-slate-800 font-mono">
                <div className="text-cyan-400 font-bold mb-1">
                  Sweep Result: {sensitivityResult.parameter_tested}
                </div>
                <div className="text-slate-300 text-[11px] mb-2">
                  {sensitivityResult.sensitivity_summary}
                </div>
                <div className="space-y-1 text-[11px]">
                  {sensitivityResult.results.map((pt, idx) => (
                    <div key={idx} className="flex justify-between border-b border-slate-800 pb-0.5">
                      <span>Val: {pt.parameter_value}</span>
                      <span>Area: {pt.candidate_ice_area_km2} km²</span>
                      <span>Vol: {(pt.expected_volume_m3 / 1e6).toFixed(2)}M m³</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Step 10: Research Experiments & Ablation View
  if (currentStep === 10) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 10: Research Experiments &amp; Ablation Studies</h3>
            <p className="text-xs text-slate-400">Route strategy trade-offs, read from this run.</p>
          </div>
          <span className="bg-purple-500/20 text-purple-300 text-xs px-2.5 py-1 rounded font-mono border border-purple-500/40">
            EXPERIMENT 4
          </span>
        </div>

        <div className="space-y-3">
          <div className="bg-slate-800/60 p-3 rounded-lg border border-slate-700">
            <h4 className="font-bold text-xs text-cyan-300 mb-1">Experiment 4: Route Strategy Trade-Off Comparison</h4>
            <div className="grid grid-cols-4 gap-2 text-xs font-mono mt-2">
              <div className="text-slate-400 font-semibold">Strategy</div>
              <div className="text-slate-400 font-semibold">Distance</div>
              <div className="text-slate-400 font-semibold">Mean hazard</div>
              <div className="text-slate-400 font-semibold">Max slope</div>

              {(['Shortest', 'Safest', 'Science-Aware'] as const).map((name) => {
                const r = mission.rover_routes[name];
                const tone =
                  name === 'Shortest' ? 'text-amber-400'
                  : name === 'Safest' ? 'text-emerald-400'
                  : 'text-cyan-400 font-bold';
                if (!r || !r.path_found) {
                  return (
                    <Fragment key={name}>
                      <div className={tone}>{name}</div>
                      <div className="text-slate-500">NO ROUTE</div>
                      <div className="text-slate-500">NO ROUTE</div>
                      <div className="text-slate-500">NO ROUTE</div>
                    </Fragment>
                  );
                }
                return (
                  <Fragment key={name}>
                    <div className={tone}>{name}</div>
                    <div>{r.total_distance_km.toFixed(2)} km</div>
                    <div>{r.mean_hazard_encountered.toFixed(3)}</div>
                    <div>{r.max_slope_encountered_deg.toFixed(1)}°</div>
                  </Fragment>
                );
              })}
            </div>
            <p className="text-[11px] text-slate-400 mt-2">
              Every cell is read from <span className="font-mono">mission.rover_routes</span> for the
              crater and algorithm currently selected. The Science Yield column is gone: it needs a
              science-value raster, and there is none — <span className="font-mono">NO DATA</span>.
            </p>
          </div>
        </div>

        <div className="bg-slate-800/40 p-3 rounded-lg border border-slate-700 text-xs text-slate-400">
          <span className="font-semibold text-slate-300">Experiment 5 (step-by-step planning ablation): NOT RUN.</span>{' '}
          It previously listed six increments — distance, slope, roughness, boulder hazard, solar
          energy, volatiles — each with a distance and hazard figure. None was computed; they were
          written into the page. The fourth was <span className="font-mono">+ Boulder Hazard</span>,
          which cannot move any number at all: <span className="font-mono">WEIGHT_BOULDER = 0</span>,
          because no boulder raster exists. A real ablation means re-planning the route once per
          factor and reporting the measured deltas, and it is scheduled after the traverse rebuild.
        </div>
      </div>
    );
  }

  // Step 11: Explainability Dossier View
  if (currentStep === 11) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 11: Explainability Dossier (Viva Defense Reference)</h3>
            <p className="text-xs text-slate-400">Clear computational explanations for every algorithmic choice made by the system.</p>
          </div>
        </div>

        <ContextBanner
          objective="Viva Defense Dossier"
          text="Provides clear, defensible computational explanations for why each landing zone was ranked and why specific crater passes were chosen during traversal."
        />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="bg-slate-800/60 p-4 rounded-xl border border-slate-700 space-y-2">
            <h4 className="font-bold text-cyan-300">Why was Landing Site #1 selected?</h4>
            <ul className="space-y-1 text-slate-300">
              <li>✓ Slope below 8° (safe touchdown)</li>
              <li>✓ 78% solar illumination window</li>
              <li>✓ Zero high-hazard boulder fields</li>
              <li>✓ Direct access to ridge approach ramp</li>
              <li>✓ Highest algorithmic score (88.4 / 100)</li>
            </ul>
          </div>

          <div className="bg-slate-800/60 p-4 rounded-xl border border-slate-700 space-y-2">
            <h4 className="font-bold text-cyan-300">Why did the rover turn here?</h4>
            <ul className="space-y-1 text-slate-300">
              <li>✓ Bypassed 22° impassable crater rim cliffs</li>
              <li>✓ Maintained solar array line-of-sight</li>
              <li>✓ Avoided boulder-dense debris fans</li>
              <li>✓ Ingressed via natural breached ridge corridor</li>
            </ul>
          </div>

          <div className="bg-slate-800/60 p-4 rounded-xl border border-slate-700 space-y-2">
            <h4 className="font-bold text-cyan-300">Why is this an ice candidate?</h4>
            <ul className="space-y-1 text-slate-300">
              <li>✓ CPR &gt; 1.0 (Coherent Backscatter CBOE)</li>
              <li>✓ DOP &lt; 0.13 (Volume depolarization)</li>
              <li>✓ Permanent shadow (0.0% solar radiance)</li>
              <li>✓ Nested doubly-shadowed cold-trap</li>
              <li>✓ ML probabilistic score P &gt; 0.80</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  // Step 12: Mission Report Generation View
  if (currentStep === 12) {
    const pdfUrl = getReportPdfUrl(mission.selected_crater.id);
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-100">Step 12: Mission Decision Report Export</h3>
            <p className="text-xs text-slate-400">Generate and download official PDF and JSON mission reports with full provenance data.</p>
          </div>
        </div>

        <ContextBanner
          objective="Official Dossier Export"
          text="Generates complete, publication-ready PDF and JSON dossiers with full data provenance, algorithm parameters, and reproducible random seeds."
        />

        <div className="bg-slate-800/60 p-5 rounded-xl border border-slate-700 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="space-y-1 text-xs">
            <div className="font-bold text-sm text-slate-100">
              Lunar Ice Intelligence Mission Report ({mission.selected_crater.name})
            </div>
            <p className="text-slate-400">
              Includes executive summary, DFSAR radar analysis, landing site ranking table, rover route waypoints, volume uncertainty tiers, and explicit scientific limitations.
            </p>
            <div className="font-mono text-[10px] text-slate-500 mt-2">
              {/* No `Seed:` here. It printed `mission.psr.provenance.random_seed`,
                  which is populated only by the retired demo generator, so on a
                  REAL run it rendered `Seed: None` — and on any other run it
                  advertised that the report's numbers came from a seed. The
                  product id is the reproducibility handle now. */}
              Generated: {mission.generated_at} | Mode: {mission.data_mode}
              {mission.selected_crater.product_id ? ` | Product: ${mission.selected_crater.product_id}` : ''}
            </div>
          </div>

          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold px-4 py-2.5 rounded-lg flex items-center gap-2 text-xs transition shadow-[0_0_15px_rgba(6,182,212,0.3)]"
          >
            <Download className="w-4 h-4" /> Download PDF Report
          </a>
        </div>
      </div>
    );
  }

  return null;
};
