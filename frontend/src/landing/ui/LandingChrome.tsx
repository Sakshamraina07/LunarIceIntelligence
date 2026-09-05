/**
 * LandingChrome.tsx
 * The HTML storytelling layer that floats above the fixed 3D Moon. Sections
 * scroll normally (driving the camera rig via scroll progress); copy is written
 * for a non-technical reader and never leads with jargon (CPR/DOP/PSR live
 * inside the mission app, not here).
 */
import type { LunarTarget } from '../data/targets';
import { NOT_INGESTED_LABEL, UNSCREENED_COLOR, targetColor } from '../data/targets';

interface Props {
  live: boolean;
  selected: LunarTarget | null;
  onSelectClose: () => void;
  onEnterMission: () => void;
}

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
}

export function LandingChrome({ live, selected, onSelectClose, onEnterMission }: Props) {
  return (
    <>
      {/* Top bar */}
      <div className="li-topbar">
        <div className="li-brand">
          <span className="li-brand-dot" />
          Lunar Ice Intelligence
        </div>
        <div className={`li-badge ${live ? 'li-badge--live' : 'li-badge--demo'}`}>
          {/* `live` means at least one target came back with a screening verdict
              from a REAL backend run. The old alternative read "Demo / fallback",
              which named a seeded mode that no longer exists — the honest
              alternative is that nothing has been screened in this build. */}
          {live ? 'Data · Live backend' : 'Data · No swath ingested'}
        </div>
      </div>

      <div className="li-scroll">
        {/* HERO */}
        <section className="li-section" id="li-hero">
          <div className="li-panel">
            <div className="li-eyebrow">Lunar Ice Intelligence</div>
            <h1 className="li-h1">
              Searching the Moon&rsquo;s South Pole
              <br />
              for Possible Water Ice
            </h1>
            <p className="li-lede">
              Some places near the Moon&rsquo;s south pole have sat in permanent darkness
              for billions of years. We explore those hidden regions and weigh the
              evidence for where <span className="li-accent">water ice may be trapped</span>.
            </p>
            <button className="li-cta" onClick={() => scrollToId('li-candidates')}>
              Explore the South Pole →
            </button>
          </div>
        </section>

        {/* SECTION 1 — THE SEARCH */}
        <section className="li-section" id="li-search">
          <div className="li-panel">
            <div className="li-eyebrow">01 · The Search</div>
            <h2 className="li-h2">Where sunlight never reaches</h2>
            <p className="li-lede">
              Near the poles, the Sun barely rises above the horizon. The floors of some
              craters <span className="li-accent">never receive direct sunlight</span> — cold
              traps where volatile ice could survive for aeons.
            </p>
          </div>
        </section>

        {/* SECTION 2 — THE EVIDENCE */}
        <section className="li-section" id="li-evidence">
          <div className="li-panel">
            <div className="li-eyebrow">02 · The Evidence</div>
            <h2 className="li-h2">Reading independent clues</h2>
            <p className="li-lede">
              No single measurement proves ice. We look for several signs that point the
              same way before calling a region promising.
            </p>
            <div className="li-evidence-row">
              <div className="li-chip">
                <span className="li-chip-k">Shadow</span>
                <span className="li-chip-v">Regions that stay permanently dark</span>
              </div>
              <div className="li-chip">
                <span className="li-chip-k">Radar</span>
                <span className="li-chip-v">Echoes consistent with buried ice</span>
              </div>
              <div className="li-chip">
                <span className="li-chip-k">Terrain</span>
                <span className="li-chip-v">Ground a lander could safely reach</span>
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 3 — THE CANDIDATES */}
        <section className="li-section" id="li-candidates">
          <div className="li-panel">
            <div className="li-eyebrow">03 · The Candidates</div>
            <h2 className="li-h2">Ranking the promising regions</h2>
            <p className="li-lede">
              Where the clues line up, we mark a candidate. Hover or tap a marker on the
              Moon to see what makes it interesting. Nothing here is a{' '}
              <span className="li-accent">confirmed</span> ice deposit — only a region worth
              a closer look.
            </p>
          </div>
        </section>

        {/* SECTION 4 — THE MISSION */}
        <section className="li-section" id="li-mission">
          <div className="li-panel">
            <div className="li-eyebrow">04 · The Mission</div>
            <h2 className="li-h2">Could a rover safely reach them?</h2>
            <p className="li-lede">
              For the best candidates we plan a landing site and a route a rover could
              travel — balancing the <span className="li-accent">shortest, safest and most
              scientifically valuable</span> paths across rough polar terrain.
            </p>
          </div>
        </section>

        {/* FINAL CTA */}
        <section className="li-section" id="li-enter" style={{ justifyContent: 'center' }}>
          <div className="li-panel" style={{ textAlign: 'center', maxWidth: '34rem' }}>
            <div className="li-eyebrow" style={{ justifyContent: 'center' }}>
              Enter Mission Control
            </div>
            <h2 className="li-h2">The full picture, region by region</h2>
            <p className="li-lede" style={{ margin: '0 auto' }}>
              Step inside the mission workspace to explore the radar analysis, ice
              likelihood, landing-site selection and rover planning in detail.
            </p>
            <button className="li-cta" onClick={onEnterMission} style={{ marginInline: 'auto' }}>
              Explore Lunar Ice Intelligence →
            </button>
          </div>
        </section>
      </div>

      {/* Selected target detail */}
      {selected && (
        <div className="li-detail">
          <button className="li-detail-close" onClick={onSelectClose} aria-label="Close">
            ✕
          </button>
          <div className="li-detail-name">{selected.name}</div>
          {selected.label ? (
            <>
              <div className="li-detail-label" style={{ color: targetColor(selected) }}>
                {selected.label}
              </div>
              <div className="li-detail-note">{selected.note}</div>
              <div className="li-detail-meta">
                <span>
                  {selected.lat.toFixed(2)}° , {selected.lon.toFixed(2)}°
                </span>
                <span>
                  {selected.psrFraction !== undefined
                    ? `${(selected.psrFraction * 100).toFixed(0)}% in permanent shadow`
                    : 'Live · backend'}
                </span>
              </div>
            </>
          ) : (
            <>
              {/* No swath, no verdict. The tier colour and the screening line are
                  both withheld — the crater is still named and located, because
                  its position is a published fact and not a result of ours. */}
              <div className="li-detail-label" style={{ color: UNSCREENED_COLOR }}>
                {NOT_INGESTED_LABEL}
              </div>
              <div className="li-detail-note">{selected.note}</div>
              <div className="li-detail-meta">
                <span>
                  {selected.lat.toFixed(2)}° , {selected.lon.toFixed(2)}°
                </span>
                <span>{selected.diameterKm} km across · IAU/USGS</span>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
