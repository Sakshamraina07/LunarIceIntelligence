/**
 * Prov.tsx — the provenance chip, and the two ways a figure is allowed to
 * reach the screen.
 *
 * Defined once. There were three copies of this chip (VerdictCard's `Prov`,
 * MissionControl's `Pv`, and none at all in StepPanel, which is why StepPanel
 * rendered twelve steps of unmarked numbers). Three copies is three chances for
 * one of them to drift into rendering a mark that no longer means what it says.
 *
 * THE RULE THIS FILE ENFORCES: a number reaches the user with a mark, or it
 * does not reach the user. `<Figure>` cannot render a value without also
 * rendering its provenance, and when the value is null it renders an em dash
 * plus the recorded reason — never a substitute, never a bare dash.
 */
import type { AnalysisValue, Provenance } from './analysis';
import { PROV_MARK, isMissing, showValue, showPercent, absenceReason } from './analysis';

/** Short mark rendered next to every value. Blunt on purpose. */
export function Pv({ p }: { p: Provenance }) {
  return <span className={`mc-pv mc-pv--${p.toLowerCase()}`}>{PROV_MARK[p]}</span>;
}

/**
 * One labelled figure with its mark, or one labelled absence with its reason.
 *
 * `sub` is the sub-line shown when the value EXISTS. When it does not, the
 * value's own `reason` is shown instead, because the reason is the thing the
 * reader actually needs and a generic sub-line would bury it.
 */
export function Figure({
  k, v, sub, digits, suffix, percent, fallback,
}: {
  k: string;
  v: AnalysisValue | undefined;
  sub?: string;
  digits?: number;
  suffix?: string;
  /**
   * The stored value is a FRACTION in [0,1] and should be shown as a
   * percentage. The conversion lives here rather than at the call site: passing
   * `suffix=" %"` to a fraction printed "0.897 %" for a surface that is 89.7 %
   * traversable, and a correct number rendered wrong is no better than an
   * invented one.
   */
  percent?: boolean;
  /** Used only if the generator recorded no reason — which it should never do. */
  fallback?: string;
}) {
  const missing = isMissing(v);
  const prov: Provenance = v?.provenance ?? 'UNAVAILABLE';
  const unit = percent ? ' %' : suffix ?? (v?.unit ? ` ${v.unit}` : '');

  return (
    <div className={`mc-metric${missing ? ' mc-metric--na' : ''}`}>
      <div className="mc-metric-k">
        {k}
        <Pv p={prov} />
      </div>
      <div className={`mc-metric-v${missing ? ' mc-metric-v--na' : ''}`}>
        {missing
          ? '—'
          : <>{percent ? showPercent(v, digits ?? 2) : showValue(v, digits)}<small>{unit}</small></>}
      </div>
      <div className="mc-metric-sub">
        {missing
          ? absenceReason(v, fallback ?? 'Not computed in this build.')
          : sub}
      </div>
    </div>
  );
}

/**
 * A whole panel that has nothing to show. Used when a step's declared status is
 * UNAVAILABLE: the step still renders, still says what it would show and why it
 * cannot, and never draws an empty table that reads as "zero results".
 */
export function StepUnavailable({ title, basis }: { title: string; basis: string }) {
  return (
    <div className="mc-na" style={{ marginTop: '0.9rem' }}>
      <span className="mc-na-dash">—</span>
      <span>
        <strong style={{ color: 'var(--mc-text)' }}>{title} is not computed in this build.</strong>{' '}
        {basis}
        <Pv p="UNAVAILABLE" />
      </span>
    </div>
  );
}
