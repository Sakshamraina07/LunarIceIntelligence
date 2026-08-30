/**
 * LandingPage.tsx
 * Top-level orchestrator for the Lunar Ice Intelligence landing experience.
 * Owns lightweight React state (target catalogue, selection, backend liveness)
 * and wires scroll progress into the fixed 3D scene. The camera/animation loop
 * reads a ref (not state), so scrolling never triggers React re-renders.
 */
import { useEffect, useMemo, useState } from 'react';
import { LunarScene } from './scene/LunarScene';
import { LandingChrome } from './ui/LandingChrome';
import { useScrollProgress } from './hooks/useScrollProgress';
import { SOUTH_POLE_TARGETS, type LunarTarget } from './data/targets';
import { loadTargets } from './services/missionData';
import './landing.css';

const SECTION_COUNT = 6;

interface Props {
  onEnterMission: () => void;
}

export function LandingPage({ onEnterMission }: Props) {
  const { progress, section } = useScrollProgress(SECTION_COUNT);
  const [targets, setTargets] = useState<LunarTarget[]>(SOUTH_POLE_TARGETS);
  const [live, setLive] = useState(false);
  const [ready, setReady] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Enrich targets from the backend if it's reachable (never blocks the scene).
  useEffect(() => {
    let cancelled = false;
    loadTargets()
      .then(({ targets: t, live: l }) => {
        if (cancelled) return;
        setTargets(t);
        setLive(l);
      })
      .finally(() => !cancelled && setReady(true));
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(
    () => targets.find((t) => t.id === selectedId) ?? null,
    [targets, selectedId]
  );

  const handleSelect = (t: LunarTarget) => setSelectedId((cur) => (cur === t.id ? null : t.id));

  return (
    <div className="li-root">
      <div className="li-stage">
        <LunarScene
          progress={progress}
          targets={targets}
          selectedId={selectedId}
          onSelect={handleSelect}
        />
      </div>
      <div className="li-vignette" />

      <LandingChrome
        live={live}
        selected={selected}
        onSelectClose={() => setSelectedId(null)}
        onEnterMission={onEnterMission}
      />

      {/* Scroll hint fades out once the descent begins */}
      <div className="li-scrollhint" style={{ opacity: section === 0 ? 1 : 0 }}>
        Scroll to descend
        <span />
      </div>

      {!ready && (
        <div className="li-loading">
          <div className="li-loading-ring" />
          Initialising lunar reconnaissance
        </div>
      )}
    </div>
  );
}
