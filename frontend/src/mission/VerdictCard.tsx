/**
 * VerdictCard.tsx — the always-on, non-technical-first summary at the top of
 * the intelligence rail. Answers, in plain language and in this order:
 *   WHERE are we looking? · WHAT did we find? · WHY is it promising? · CAN we reach it?
 *
 * Every number is the honest, backend-computed value. We deliberately never
 * print "confirmed water ice": the headline is the PEAK modelled P(ice) and the
 * tier label is gated on the pipeline's own screening verdict, so a FAIL crater
 * reads as inconclusive rather than a success.
 */
import { Check, X, MapPin, ArrowRight } from 'lucide-react';
import type { MissionState } from '../types/mission';

/** Prettify an evidence_checklist key like "cpr_anomaly_present" → "CPR anomaly present". */
function labelKey(k: string): string {
  return k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

interface Tier { cls: string; label: string; }
function tierFor(status: string, peak: number): Tier {
  if (status === 'PASS') return { cls: 'mc-tier--promising', label: 'Promising Candidate' };
  if (peak >= 0.6) return { cls: 'mc-tier--candidate', label: 'Evidence Consistent With Possible Ice' };
  if (peak >= 0.3) return { cls: 'mc-tier--weak', label: 'Weak / Inconclusive Signal' };
  return { cls: 'mc-tier--fail', label: 'No Significant Ice Evidence' };
}

export function VerdictCard({ mission }: { mission: MissionState }) {
  const { ice, selected_crater: crater, recommended_landing_site: site } = mission;
  const peak = ice.ml_ice_likelihood_max ?? 0;
  const tier = tierFor(ice.scientific_screening_status, peak);
  const science = mission.rover_routes['Science-Aware'];
  const reachable = site && science?.path_found;

  const checks = Object.entries(ice.evidence_checklist ?? {});

  return (
    <div className="mc-card mc-card--accent mc-fadein">
      <div className="mc-eyebrow">Where are we looking</div>
      <div className="mc-answer" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <MapPin size={16} style={{ color: 'var(--mc-accent)', flex: '0 0 auto' }} />
        {crater.name}
      </div>
      <div className="mc-ask" style={{ marginTop: '-0.6rem', marginBottom: '0.9rem' }}>
        {crater.latitude_deg.toFixed(2)}° · {crater.longitude_deg.toFixed(2)}° — {crater.target_description}
      </div>

      <div className="mc-ask">What did we find — peak modelled P(ice)</div>
      <div className="mc-verdict">
        <span className="mc-verdict-pct" style={{ color: 'var(--mc-accent)' }}>
          {Math.round(peak * 100)}<small>%</small>
        </span>
        <span className={`mc-tier ${tier.cls}`}>{tier.label}</span>
      </div>
      <div className="mc-ask" style={{ marginTop: '0.5rem', textTransform: 'none', letterSpacing: 0 }}>
        Mean P(ice) {ice.ml_ice_likelihood_mean.toFixed(2)} · model confidence {ice.confidence} ·
        screening {ice.scientific_screening_status === 'PASS' ? 'PASSED' : 'NOT PASSED'}
      </div>

      <div className="mc-details">
        <div className="mc-details-k">Why — evidence checklist</div>
        <ul className="mc-why">
          {checks.map(([k, v]) => (
            <li key={k}>
              {v
                ? <Check size={14} className="mc-why-ico mc-why-yes" />
                : <X size={14} className="mc-why-ico mc-why-no" />}
              <span style={{ color: v ? 'var(--mc-text)' : 'var(--mc-text-mute)' }}>{labelKey(k)}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mc-details">
        <div className="mc-details-k">Can we reach it</div>
        {reachable ? (
          <div className="mc-why" style={{ marginTop: 0 }}>
            <li>
              <ArrowRight size={14} className="mc-why-ico mc-why-yes" />
              <span style={{ color: 'var(--mc-text)' }}>
                Site #{site.rank} — {site.slope_deg.toFixed(1)}° slope, {science.total_distance_km.toFixed(1)} km traverse
              </span>
            </li>
          </div>
        ) : (
          <div className="mc-ask" style={{ textTransform: 'none', letterSpacing: 0 }}>
            No safe touchdown + traverse solution under current constraints.
          </div>
        )}
      </div>
    </div>
  );
}
