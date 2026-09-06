/**
 * TraversePanel.tsx — which route, where the rover is on it, and what that cost.
 *
 * WHY IT EXISTS
 * -------------
 * Phase 4 planned five routes and the map drew none of them: the only traverse
 * on screen came from the API's demo-target path. So "it is highly unclear the
 * rover passes through which points" was an accurate description — the points
 * were in `traverse.json` and nothing rendered them.
 *
 * WHAT IT IS HONEST ABOUT
 * -----------------------
 * The PATH is computed — Dijkstra over measured slope, roughness and hazard at a
 * stated 100 m planning resolution, with connectivity established before any
 * distance is quoted. The DESTINATION is a MODELLED cold trap: where ice could
 * persist under the horizon computation, not where ice is. The rover itself is a
 * drawing; there is no vehicle model in this project, which is why the energy
 * figure is per kilogram.
 *
 * Every one of those three statements is on this panel, next to the number it
 * qualifies, rather than in a footnote.
 */
import { Pause, Play, RotateCcw } from 'lucide-react';
import type { Traverse } from './traverse';

interface Props {
  traverse: Traverse | null;
  /** true once the fetch has settled, so "loading" and "absent" stay distinct. */
  settled: boolean;
  selected: number | null;
  onSelect: (rank: number) => void;
  fraction: number;
  onFraction: (f: number) => void;
  playing: boolean;
  onPlaying: (p: boolean) => void;
  /**
   * Render as a card in the intelligence rail rather than as a panel floating
   * over the map.
   *
   * The overlay version covered the top-right quadrant of the map, which is
   * where several of the searched sites are, so the panel describing the sites
   * was hiding them. In the rail it costs the map nothing.
   */
  inRail?: boolean;
}

const ROUTE_COLOUR = ['#4fd1e6', '#6ee7a8', '#f2c14e', '#c084fc', '#fb7185'];

export function TraversePanel({
  traverse, settled, selected, onSelect, fraction, onFraction, playing, onPlaying,
  inRail = false,
}: Props) {
  const routes = traverse?.primary_site_to_cold_trap ?? [];
  const cur = routes.find((r) => r.rank === selected) ?? null;
  const len = cur?.length_m ?? 0;
  const conn = traverse
    ? traverse.connectivity[String(traverse.planning.resolution_m)]
    : undefined;

  return (
    <div className={inRail
      ? 'mc-card mc-traversectl mc-traversectl--rail'
      : 'mc-map-overlay mc-map-panel mc-traversectl'}>
      <div className="mc-probe-head">
        <span className="mc-trv-dot" />
        <span>Traverse · Phase 4</span>
        <span className="mc-trv-res">
          {traverse ? `${traverse.planning.resolution_m} m grid` : ''}
        </span>
      </div>

      {!settled && <div className="mc-probe-empty">Loading the traverse plan…</div>}
      {settled && !traverse && (
        <div className="mc-probe-empty mc-probe-empty--absent">
          No traverse planned on this host. No line is drawn in its place.
          <code>python backend/scripts/plan_traverse.py</code>
        </div>
      )}

      {traverse && (
        <>
          {/* Connectivity BEFORE any distance — the same order plan_traverse.py
              reports in, because "how far" is meaningless until "can it get
              there at all" has an answer. */}
          {conn && (
            <div className="mc-trv-conn">
              {conn.sites_in_largest}/{conn.n_sites} sites in the largest passable
              component ({(conn.passable_fraction * 100).toFixed(1)}% of the frame
              is passable). Connectivity first, distance second.
            </div>
          )}

          <div className="mc-trv-list">
            {routes.map((r) => {
              const c = ROUTE_COLOUR[(r.rank - 1) % ROUTE_COLOUR.length];
              const on = r.rank === selected;
              const reach = r.status === 'REACHABLE';
              return (
                <button
                  key={r.rank}
                  className={`mc-trv-item ${on ? 'mc-trv-item--on' : ''} ${reach ? '' : 'mc-trv-item--un'}`}
                  onClick={() => reach && onSelect(r.rank)}
                  disabled={!reach}
                >
                  <span className="mc-trv-sw" style={{ background: c }} />
                  <span className="mc-trv-name">Site {r.rank}</span>
                  {/* UNREACHABLE prints as UNREACHABLE. A dash or a zero here
                      would read as "no travel needed", the opposite of true. */}
                  <span className="mc-trv-km">
                    {reach ? `${(r.length_m! / 1000).toFixed(2)} km` : 'UNREACHABLE'}
                  </span>
                  <span className="mc-trv-wp">{reach ? `${r.cells} pts` : ''}</span>
                </button>
              );
            })}
          </div>

          {cur && cur.status === 'REACHABLE' && (
            <>
              <div className="mc-trv-scrub">
                <button
                  className="mc-trv-play"
                  onClick={() => onPlaying(!playing)}
                  title={playing ? 'Pause the rover' : 'Drive the rover along this route'}
                >
                  {playing ? <Pause size={12} /> : <Play size={12} />}
                </button>
                <input
                  type="range" min={0} max={1000} value={Math.round(fraction * 1000)}
                  onChange={(e) => { onPlaying(false); onFraction(Number(e.target.value) / 1000); }}
                  aria-label="Position along the selected route"
                />
                <button
                  className="mc-trv-play" onClick={() => { onPlaying(false); onFraction(0); }}
                  title="Back to the landing site"
                >
                  <RotateCcw size={12} />
                </button>
              </div>
              <div className="mc-trv-odo">
                <b>{((fraction * len) / 1000).toFixed(2)} km</b>
                <span> of {(len / 1000).toFixed(2)} km · waypoint{' '}
                  {Math.min(cur.cells!, 1 + Math.round(fraction * (cur.cells! - 1)))} of {cur.cells}
                </span>
              </div>

              <div className="mc-trv-stats">
                <div>
                  <span className="mc-trv-sk">climb</span>
                  <span className="mc-trv-sv">{cur.climb_m} m</span>
                </div>
                <div>
                  <span className="mc-trv-sk">energy</span>
                  <span className="mc-trv-sv">{cur.energy_J_per_kg?.toLocaleString()} J/kg</span>
                </div>
                <div>
                  <span className="mc-trv-sk">quantised</span>
                  <span className="mc-trv-sv">±{(cur.quantisation_m ?? 0) / 2} m</span>
                </div>
              </div>

              {/* Per-kilogram, and the reason is stated where the number is. */}
              <div className="mc-trv-note">
                {traverse.energy_proxy.formula} — <b>per kilogram</b>, so no rover
                mass is invented. µ<sub>roll</sub> = {traverse.energy_proxy.mu_roll} is an
                assumed rolling resistance, not a measurement.
                <span className="mc-trv-prov">{traverse.energy_proxy.provenance}</span>
              </div>

              {/* The destination caveat, read from the route's own field. */}
              <div className="mc-trv-target">{cur.target}</div>
            </>
          )}
        </>
      )}
    </div>
  );
}
