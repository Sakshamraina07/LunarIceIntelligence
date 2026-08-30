import React, { useState, useEffect } from 'react';
import {
  fetchCraters,
  fetchMissionState,
  getReportPdfUrl
} from './services/api';
import type { MissionState, CraterInfo, CandidateLandingSite } from './types/mission';
import { GISMapViewer } from './components/Map/GISMapViewer';
import { MissionStepper } from './components/Workflow/MissionStepper';
import { WorkflowViews } from './components/Views/WorkflowViews';
import {
  Radio,
  Download,
  RefreshCw,
  AlertCircle,
  Activity,
  SlidersHorizontal,
  Compass
} from 'lucide-react';

export const App: React.FC = () => {
  const [craters, setCraters] = useState<Record<string, CraterInfo>>({});
  const [selectedCraterId, setSelectedCraterId] = useState<string>('faustini');
  const [dataMode] = useState<string>('REAL');
  const [mission, setMission] = useState<MissionState | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Workflow & View States
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [activeLayer, setActiveLayer] = useState<string>('cpr_heatmap');
  const [showLandingSites, setShowLandingSites] = useState<boolean>(true);
  const [activeRoverStrategies, setActiveRoverStrategies] = useState<string[]>([
    'Shortest',
    'Safest',
    'Science-Aware',
  ]);
  const [selectedLandingSite, setSelectedLandingSite] = useState<CandidateLandingSite | null>(null);


  const LOADING_MESSAGES = [
    'Ingesting Chandrayaan-2 DFSAR L2 calibrated Stokes vectors...',
    'Decomposing circular polarization (CPR & DOP) on 2048² swath...',
    'Computing grazing solar illumination (1.5°) & cryogenic PSR traps...',
    'Evaluating composite terrain safety (slope, roughness, cliffs)...',
    'Executing Random Forest ice probability inference P(ice)...',
    'Ranking optimal touchdown ridges & plotting rover trajectories...',
  ];
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);

  useEffect(() => {
    if (!loading) return;
    const timer = setInterval(() => {
      setLoadingMessageIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
    }, 1800);
    return () => clearInterval(timer);
  }, [loading]);

  // Tunable Parameters
  const [cprThreshold, setCprThreshold] = useState<number>(1.0);
  const [dopThreshold, setDopThreshold] = useState<number>(0.13);
  const [iceDepthM, setIceDepthM] = useState<number>(5.0);
  const [iceFraction, setIceFraction] = useState<number>(0.15);
  const [roverAlgorithm, setRoverAlgorithm] = useState<string>('A*');

  // Load initial crater list
  useEffect(() => {
    fetchCraters()
      .then((data) => setCraters(data))
      .catch((err) => {
        console.error(err);
        setError('Failed to connect to Lunar Intelligence backend. Make sure FastAPI server is running on port 8000.');
      });
  }, []);

  // Fetch or update mission state
  const loadMissionData = (craterId: string = selectedCraterId) => {
    setLoading(true);
    setError(null);
    fetchMissionState(craterId, {
      dataMode,
      cprThreshold,
      dopThreshold,
      iceDepthM,
      iceFraction,
      algorithm: roverAlgorithm,
    })
      .then((data) => {
        setMission(data);
        setSelectedLandingSite(data.recommended_landing_site);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Mission execution error');
        setLoading(false);
      });
  };

  useEffect(() => {
    loadMissionData(selectedCraterId);
  }, [selectedCraterId, dataMode, cprThreshold, dopThreshold, iceDepthM, iceFraction, roverAlgorithm]);

  const handleSelectCrater = (craterId: string) => {
    setSelectedCraterId(craterId);
  };

  const toggleRoverStrategy = (strategy: string) => {
    setActiveRoverStrategies((prev) =>
      prev.includes(strategy) ? prev.filter((s) => s !== strategy) : [...prev, strategy]
    );
  };

  const handleUpdateParams = (newParams: any) => {
    if (newParams.cprThreshold !== undefined) setCprThreshold(newParams.cprThreshold);
    if (newParams.dopThreshold !== undefined) setDopThreshold(newParams.dopThreshold);
    if (newParams.iceDepthM !== undefined) setIceDepthM(newParams.iceDepthM);
    if (newParams.iceFraction !== undefined) setIceFraction(newParams.iceFraction);
  };

  // Sync active map layer when stepping through workflow
  const handleStepChange = (step: number) => {
    setCurrentStep(step);
    if (step === 2) setActiveLayer('illumination');
    else if (step === 3) setActiveLayer('cpr_heatmap');
    else if (step === 4) setActiveLayer('ml_likelihood');
    else if (step === 5) setActiveLayer('hazard_map');
    else if (step === 6) setActiveLayer('dem_elevation');
    else if (step === 7) setActiveLayer('hillshade');
  };

  // Quick preset application
  const applyPreset = (presetName: string) => {
    if (presetName === 'baseline') {
      setCprThreshold(1.0);
      setDopThreshold(0.13);
      setIceDepthM(5.0);
      setIceFraction(0.15);
    } else if (presetName === 'strict') {
      setCprThreshold(1.2);
      setDopThreshold(0.10);
      setIceDepthM(3.0);
      setIceFraction(0.10);
    } else if (presetName === 'permissive') {
      setCprThreshold(0.8);
      setDopThreshold(0.18);
      setIceDepthM(8.0);
      setIceFraction(0.20);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-cyan-500 selection:text-black relative bg-lunar-grid">
      {/* Planetary Mission Control Header */}
      <header className="border-b border-slate-800 bg-slate-950/90 backdrop-blur-xl sticky top-0 z-50 px-4 py-3 shadow-2xl">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/50 flex items-center justify-center text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.35)]">
              <Radio className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-extrabold text-base tracking-wider text-slate-100 uppercase">
                  Lunar Ice Intelligence
                </h1>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold">
                  v2.0 GIS MOC
                </span>
              </div>
              <p className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                <span>Chandrayaan-2 Radar Analysis</span>
                <span>•</span>
                <span>South Polar Traverse Control</span>
              </p>
            </div>
          </div>

          {/* Quick Presets & Controls */}
          <div className="flex items-center gap-2 text-xs font-mono">
            <div className="hidden md:flex items-center gap-1 bg-slate-900 p-1 rounded-lg border border-slate-800 text-[11px]">
              <SlidersHorizontal className="w-3.5 h-3.5 text-cyan-400 ml-1" />
              <span className="text-slate-400 text-[10px] uppercase font-bold mr-1">Presets:</span>
              <button
                onClick={() => applyPreset('baseline')}
                className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 transition"
              >
                Baseline
              </button>
              <button
                onClick={() => applyPreset('strict')}
                className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 transition"
              >
                Strict
              </button>
              <button
                onClick={() => applyPreset('permissive')}
                className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-300 border border-slate-700 transition"
              >
                Permissive
              </button>
            </div>

            {/* DATA MODE INDICATOR (PRD Non-Negotiable) */}
            <div className="px-3 py-1.5 rounded-lg font-bold flex items-center gap-1.5 border shadow-sm bg-emerald-500/15 text-emerald-300 border-emerald-500/40">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span>MODE: REAL</span>
            </div>
            <a
              href={getReportPdfUrl(selectedCraterId)}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold flex items-center gap-1.5 transition shadow-[0_0_12px_rgba(6,182,212,0.4)]"
            >
              <Download className="w-3.5 h-3.5" /> PDF
            </a>
          </div>
        </div>
      </header>

      {/* Main Mission Control Body */}
      <main className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
        {/* System Error Alert */}
        {error && (
          <div className="bg-rose-950/50 border border-rose-700 rounded-2xl p-4 flex items-start gap-3 text-rose-200 text-xs shadow-xl">
            <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Backend Connection Alert:</span> {error}
            </div>
          </div>
        )}

        {/* 12-Step Guided Mission Stepper */}
        <MissionStepper currentStep={currentStep} onSelectStep={handleStepChange} />

        {/* Loading Indicator */}
        {/* Dynamic Pipeline Processing State (PRD Part B #4) */}
        {loading && (
          <div className="py-8 px-6 flex flex-col items-center justify-center space-y-4 bg-slate-900/90 rounded-2xl border border-cyan-500/40 shadow-[0_0_30px_rgba(6,182,212,0.15)] backdrop-blur-2xl">
            <div className="relative">
              <RefreshCw className="w-10 h-10 text-cyan-400 animate-spin" />
              <div className="absolute inset-0 rounded-full bg-cyan-400/20 blur-md animate-pulse" />
            </div>
            <div className="text-center space-y-1.5 max-w-md">
              <p className="text-base font-bold text-cyan-200 tracking-wide">
                {LOADING_MESSAGES[loadingMessageIndex]}
              </p>
              <p className="text-xs text-slate-400 font-mono">
                Real-Time Computational Pipeline · Step {loadingMessageIndex + 1} of {LOADING_MESSAGES.length}
              </p>
            </div>
          </div>
        )}

        {/* Dashboard Main Grid */}
        {mission && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Interactive GIS Map Viewer (7 Cols) */}
            <div className="lg:col-span-7 space-y-4">
              <GISMapViewer
                mission={mission}
                activeLayer={activeLayer}
                setActiveLayer={setActiveLayer}
                showLandingSites={showLandingSites}
                setShowLandingSites={setShowLandingSites}
                activeRoverStrategies={activeRoverStrategies}
                toggleRoverStrategy={toggleRoverStrategy}
                selectedLandingSite={selectedLandingSite}
                onSelectLandingSite={setSelectedLandingSite}
              />
            </div>

            {/* Right Column: Active Workflow Step View & Metrics (5 Cols) */}
            <div className="lg:col-span-5 space-y-4">
              <WorkflowViews
                currentStep={currentStep}
                mission={mission}
                craters={craters}
                onSelectCrater={handleSelectCrater}
                selectedLandingSite={selectedLandingSite}
                onSelectLandingSite={setSelectedLandingSite}
                onUpdateParams={handleUpdateParams}
                cprTh={cprThreshold}
                dopTh={dopThreshold}
                iceDepth={iceDepthM}
                iceFrac={iceFraction}
                roverAlgo={roverAlgorithm}
                setRoverAlgo={setRoverAlgorithm}
              />
            </div>
          </div>
        )}

        {/* Bottom Real-Time Mission Telemetry Stream */}
        {mission && (
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 shadow-2xl backdrop-blur-xl">
            <div className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-400 animate-pulse" />
                <span className="text-slate-200 font-bold">Real-Time Mission Control Summary Telemetry</span>
              </div>
              <span className="text-slate-400 font-mono text-[10px]">
                UPDATED: {new Date().toLocaleTimeString()}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 text-xs font-mono">
              <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 shadow-sm">
                <span className="text-[10px] text-slate-400 block font-sans">TARGET CRATER</span>
                <span className="font-bold text-slate-100 truncate block mt-0.5">
                  {mission.selected_crater.name}
                </span>
              </div>

              <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 shadow-sm">
                <span className="text-[10px] text-slate-400 block font-sans">ICE LIKELIHOOD</span>
                <span className="font-bold text-cyan-400 block mt-0.5">
                  {mission.ice.ml_ice_likelihood_mean} (P &gt; 0)
                </span>
              </div>

              <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 shadow-sm">
                <span className="text-[10px] text-slate-400 block font-sans">CONFIDENCE</span>
                <span className="font-bold text-emerald-400 block mt-0.5">
                  {mission.ice.confidence.toUpperCase()}
                </span>
              </div>

              <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 shadow-sm">
                <span className="text-[10px] text-slate-400 block font-sans">ICE VOLUME (EXP)</span>
                <span className="font-bold text-indigo-400 block mt-0.5">
                  {(mission.volume.expected_volume_m3 / 1e6).toFixed(2)}M m³
                </span>
              </div>

              <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 shadow-sm">
                <span className="text-[10px] text-slate-400 block font-sans">BEST LANDING SITE</span>
                <span className="font-bold text-sky-400 block mt-0.5 truncate">
                  Site #{mission.recommended_landing_site.rank} ({mission.recommended_landing_site.composite_landing_score})
                </span>
              </div>

              <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 shadow-sm">
                <span className="text-[10px] text-slate-400 block font-sans">ROVER DISTANCE</span>
                <span className="font-bold text-amber-400 block mt-0.5">
                  {mission.rover_routes['Science-Aware']?.total_distance_km} km
                </span>
              </div>

              <div className="bg-slate-800/60 p-3 rounded-xl border border-slate-700/60 shadow-sm">
                <span className="text-[10px] text-slate-400 block font-sans">EST. ENERGY</span>
                <span className="font-bold text-purple-400 block mt-0.5">
                  {mission.rover_routes['Science-Aware']?.total_energy_wh} Wh
                </span>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Henry AI Copilot removed for now */}
      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-6 px-6 text-center text-xs text-slate-400">
        <div className="flex items-center justify-center gap-2 mb-1 text-slate-300 font-semibold">
          <Compass className="w-4 h-4 text-cyan-400" />
          <span>Lunar Ice Intelligence &amp; Traverse Planning System v2.0</span>
        </div>
        <p className="text-[11px] text-slate-400">
          Chandrayaan-2 Remote Sensing Architecture · Henry Labs Intelligence Enabled · S-band / L-band Polarimetry
        </p>
      </footer>
    </div>
  );
};

export default App;
