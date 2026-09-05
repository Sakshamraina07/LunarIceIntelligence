/**
 * Root.tsx
 * Lightweight hash-based entry switch (no router dependency):
 *   - default route  -> the cinematic Lunar Ice Intelligence landing page
 *   - #mission        -> the Mission Control workspace (mission/MissionControl.tsx)
 *
 * The landing page is the visual entry point to the whole product; its final
 * CTA navigates to #mission, which mounts the full mission workspace unchanged.
 *
 * These two are the only routes, and MissionControl is the only mission surface.
 * An earlier App.tsx shell was removed in PRD Phase 0 after an import trace from
 * main.tsx proved it unreachable; see docs/handoffs/ for the superseded design.
 */
import { useEffect, useState } from 'react';
import MissionControl from './mission/MissionControl';
import { LandingPage } from './landing/LandingPage';

function isMissionRoute(): boolean {
  return window.location.hash.replace(/^#\/?/, '') === 'mission';
}

export default function Root() {
  const [mission, setMission] = useState<boolean>(isMissionRoute());

  useEffect(() => {
    const onHash = () => setMission(isMissionRoute());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  if (mission) return <MissionControl />;

  return (
    <LandingPage
      onEnterMission={() => {
        window.location.hash = 'mission';
        window.scrollTo(0, 0);
      }}
    />
  );
}
