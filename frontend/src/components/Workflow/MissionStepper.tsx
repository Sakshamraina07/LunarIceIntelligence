import React, { useEffect } from 'react';
import {
  Orbit,
  Sun,
  Radio,
  Sparkles,
  Mountain,
  Target,
  Navigation,
  Box,
  Sliders,
  FlaskConical,
  HelpCircle,
  FileText,
  ChevronRight,
  ChevronLeft
} from 'lucide-react';

interface MissionStepperProps {
  currentStep: number;
  onSelectStep: (step: number) => void;
}

const STEPS = [
  { id: 1, label: 'Target Crater', icon: Orbit, desc: 'South Polar catalog', cat: 'SITE' },
  { id: 2, label: 'Shadow & PSR', icon: Sun, desc: 'Illumination & traps', cat: 'OPTICAL' },
  { id: 3, label: 'DFSAR Radar', icon: Radio, desc: 'CPR & DOP screening', cat: 'RADAR' },
  { id: 4, label: 'Ice Intelligence', icon: Sparkles, desc: 'Continuous P(ice)', cat: 'AI' },
  { id: 5, label: 'Terrain Hazards', icon: Mountain, desc: 'Slope & roughness', cat: 'SAFETY' },
  { id: 6, label: 'Landing Sites', icon: Target, desc: 'Algorithmic ranking', cat: 'LANDING' },
  { id: 7, label: 'Rover Traverse', icon: Navigation, desc: 'A* & Science route', cat: 'ROVER' },
  { id: 8, label: 'Volume Estimate', icon: Box, desc: '3-tier ice bounds', cat: 'VOLUME' },
  { id: 9, label: 'Sensitivity Studio', icon: Sliders, desc: 'Parameter sweep', cat: 'SWEEP' },
  { id: 10, label: 'Research Suite', icon: FlaskConical, desc: 'Ablation study', cat: 'RESEARCH' },
  { id: 11, label: 'Viva Rationale', icon: HelpCircle, desc: 'Defense arguments', cat: 'DEFENSE' },
  { id: 12, label: 'Mission Report', icon: FileText, desc: 'PDF / JSON summary', cat: 'REPORT' },
];

export const MissionStepper: React.FC<MissionStepperProps> = ({ currentStep, onSelectStep }) => {
  // Support Left/Right arrow keyboard navigation across workflow steps
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') return;
      if (e.key === 'ArrowRight' && currentStep < 12) {
        onSelectStep(currentStep + 1);
      } else if (e.key === 'ArrowLeft' && currentStep > 1) {
        onSelectStep(currentStep - 1);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentStep, onSelectStep]);

  const progressPercent = Math.round((currentStep / 12) * 100);

  return (
    <div className="relative mb-4 bg-slate-950/95 border border-cyan-500/30 rounded-2xl p-3.5 shadow-[0_10px_30px_rgba(0,0,0,0.5)] backdrop-blur-2xl overflow-hidden transition-all">
      {/* Top progress glow track */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-slate-800">
        <div
          className="h-full bg-gradient-to-r from-cyan-500 via-emerald-400 to-sky-400 transition-all duration-300 shadow-[0_0_12px_rgba(6,182,212,0.9)]"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-2.5 px-1 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
          <span className="text-slate-100 font-extrabold tracking-wider">PERSISTENT MISSION WORKFLOW</span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 text-cyan-400 border border-cyan-900/60 hidden sm:inline">
            ← / → Keys to Navigate
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <button
              onClick={() => currentStep > 1 && onSelectStep(currentStep - 1)}
              disabled={currentStep === 1}
              className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:opacity-30 transition text-xs font-semibold flex items-center gap-1 border border-slate-700"
              title="Previous Step (←)"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Prev</span>
            </button>
            <button
              onClick={() => currentStep < 12 && onSelectStep(currentStep + 1)}
              disabled={currentStep === 12}
              className="px-2.5 py-1 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold transition text-xs flex items-center gap-1 shadow-[0_0_10px_rgba(6,182,212,0.4)]"
              title="Next Step (→)"
            >
              <span>Next</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <span className="text-cyan-300 font-mono font-bold bg-cyan-950/80 border border-cyan-700/60 px-2.5 py-0.5 rounded-lg text-xs shadow-inner">
            STAGE {currentStep} / 12 ({progressPercent}%)
          </span>
        </div>
      </div>

      {/* Grid of Steps */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
        {STEPS.map((step) => {
          const Icon = step.icon;
          const isActive = currentStep === step.id;
          const isPassed = currentStep > step.id;

          return (
            <button
              key={step.id}
              onClick={() => onSelectStep(step.id)}
              className={`group flex items-center gap-2 p-2 rounded-xl text-left transition duration-200 border relative ${
                isActive
                  ? 'bg-cyan-500/20 border-cyan-400 shadow-[0_0_18px_rgba(6,182,212,0.45)] ring-1 ring-cyan-400 text-white'
                  : isPassed
                  ? 'bg-emerald-950/20 border-emerald-500/40 text-slate-200 hover:bg-slate-800/80'
                  : 'bg-slate-900/50 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <div
                className={`p-1.5 rounded-lg flex-shrink-0 transition ${
                  isActive
                    ? 'bg-cyan-400 text-slate-950 font-bold shadow-[0_0_10px_rgba(6,182,212,0.6)] animate-pulse'
                    : isPassed
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-slate-800 text-slate-500 group-hover:text-slate-300'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-[8px] font-mono font-bold tracking-tight text-cyan-400/90">
                    {step.cat}
                  </span>
                  {isActive ? (
                    <span className="text-[8px] font-mono px-1 py-0.2 rounded bg-cyan-500 text-slate-950 font-bold">
                      ACTIVE
                    </span>
                  ) : isPassed ? (
                    <span className="text-[8px] font-mono px-1 py-0.2 rounded bg-emerald-950 text-emerald-400 font-bold border border-emerald-800">
                      ✓ DONE
                    </span>
                  ) : (
                    <span className="text-[8px] font-mono text-slate-500">
                      STEP {step.id}
                    </span>
                  )}
                </div>
                <div className="text-xs font-bold truncate leading-tight mt-0.5">
                  {step.id}. {step.label}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
