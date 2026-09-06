/**
 * probe.ts — the measured field, readable at a point.
 *
 * WHAT THIS IS FOR
 * ----------------
 * The Ice Criteria screen states a verdict — 0.00 km² — and lists the criteria
 * behind it. Until now there was no way to point at a place and ask what those
 * criteria say THERE. That is the difference between a conclusion and an
 * instrument.
 *
 * WHAT IT IS NOT
 * --------------
 * It is not a predictor, and there is nothing to predict. Candidate area in this
 * frame is 0.0000 km² and METHODS §1 proves the screen is empty BY CONSTRUCTION,
 * not by chance: with CPR built from amplitude alone, `DOP < 0.13` caps CPR at
 * 0.0042610, so no pixel can satisfy both criteria whatever the terrain. A tool
 * that answered "ice is here" would be inventing the one number this project
 * exists not to invent. What it answers is "here is what was measured here, and
 * here is how far short of each threshold it falls" — everywhere, including in
 * the 84 % of the frame where the radar returned nothing at all.
 *
 * WHY A SEPARATE BINARY
 * ---------------------
 * The rendered layers are colourised .webp. Values cannot be recovered from
 * them: the colour map is not injective, it is clipped at vmin/vmax, and the
 * file is lossy. Reading pixels back off the canvas would produce a number that
 * looked measured and was not — the exact failure this project spends its
 * effort preventing. So the numbers are shipped as numbers.
 *
 * The header states the decimation and the readout repeats it. Every value is a
 * BLOCK MEAN over `decimation²` native 25 m pixels, taken over measured pixels
 * only, and it is labelled as one. NaN means no measured radar in the cell —
 * an absent state, not a zero.
 */

export interface ProbeHeader {
  schema: string;
  generated_utc: string;
  generator: string;
  shape: [number, number];
  channels: string[];
  dtype: string;
  decimation: number;
  cell_metres: number;
  native_metres: number;
  native_shape: [number, number];
  nan_means: string;
  decimation_note: string;
  thresholds: { cpr: number; dop: number };
  /** The closed-form cap DOP puts on CPR, recomputed by the emitter from the
   *  configured threshold — not a literal that could outlive the gate. */
  algebraic_ceiling: {
    cpr_cap: number; under_dop_below: number;
    identity: string; note: string; source: string;
  };
  not_a_predictor: string;
  detection_floor: {
    value: number; confidence: number; looks: number;
    source: string; note: string; caveat: string;
  };
  candidate_area: {
    area_km2: number; ci_km2: [number, number];
    confidence: number; method: string;
  };
}

export interface ProbeGrid {
  header: ProbeHeader;
  /** channel-major, then row-major: [c][gy][gx] flattened. */
  data: Float32Array;
  ny: number;
  nx: number;
  /** channel name -> plane offset in `data` */
  offset: Record<string, number>;
}

/** One reading. Every field is either a measured number or `null`; nothing is
 *  substituted, and the caller renders `null` as an explicit absence. */
export interface ProbeSample {
  /** fractional native raster coordinates of the click */
  line: number;
  sample: number;
  /** the probe cell actually read */
  cell: { gy: number; gx: number };
  latDeg: number | null;
  lonDeg: number | null;
  cpr: number | null;
  dop: number | null;
  amplitudeFraction: number;
  pointedFraction: number;
  psrFraction: number;
  illumination: number;
  elevationM: number;
  /** which of the three measured states this cell is in */
  coverage: 'measured' | 'pointed-no-return' | 'never-observed';
}

const SCHEMA = 'probe_grid/1';

let probePromise: Promise<ProbeGrid | null> | null = null;

/**
 * Fetch the probe grid, once, lazily.
 *
 * ~6.5 MB, so it is NOT fetched on page load — only when the probe is switched
 * on. A reader who never opens the instrument never pays for it. Absent is a
 * real state: without `emit_probe_grid.py` having been run on this host the
 * probe says so and offers no numbers, rather than reading them off the colour
 * map.
 */
export function loadProbeGrid(): Promise<ProbeGrid | null> {
  if (probePromise) return probePromise;
  probePromise = (async () => {
    const base = import.meta.env.BASE_URL;
    let header: ProbeHeader;
    try {
      const hr = await fetch(`${base}analysis/probe_grid.json`, { cache: 'force-cache' });
      if (!hr.ok) throw new Error(`HTTP ${hr.status}`);
      header = (await hr.json()) as ProbeHeader;
    } catch (err) {
      console.warn(`[probe] no probe_grid.json (${err}). `
        + 'Run: python backend/scripts/emit_probe_grid.py');
      return null;
    }
    // A wrong schema is treated as absent, exactly as analysis.ts does. Half-
    // understood channels would render numbers under the wrong labels.
    if (header?.schema !== SCHEMA) {
      console.error(`[probe] probe_grid.json schema is "${header?.schema}", expected "${SCHEMA}"`);
      return null;
    }
    let buf: ArrayBuffer;
    try {
      const br = await fetch(`${base}analysis/probe_grid.bin`, { cache: 'force-cache' });
      if (!br.ok) throw new Error(`HTTP ${br.status}`);
      buf = await br.arrayBuffer();
    } catch (err) {
      console.error(`[probe] probe_grid.bin missing or unreadable (${err})`);
      return null;
    }
    const [ny, nx] = header.shape;
    const expect = header.channels.length * ny * nx * 4;
    if (buf.byteLength !== expect) {
      // Silently reading a short buffer would give plausible values from the
      // wrong channel. Refuse instead.
      console.error(`[probe] probe_grid.bin is ${buf.byteLength} bytes, header `
        + `declares ${expect} (${header.channels.length} x ${ny} x ${nx} x 4). Refusing to read it.`);
      return null;
    }
    const offset: Record<string, number> = {};
    header.channels.forEach((c, i) => { offset[c] = i * ny * nx; });
    return { header, data: new Float32Array(buf), ny, nx, offset };
  })();
  return probePromise;
}

/** One channel at one cell, or NaN when the channel is absent from this file. */
function at(g: ProbeGrid, ch: string, gy: number, gx: number): number {
  const o = g.offset[ch];
  return o === undefined ? NaN : g.data[o + gy * g.nx + gx];
}

/**
 * Read the grid at fractional native raster coordinates.
 *
 * Returns `null` only when the point is off the raster entirely — inside it,
 * every cell has an answer, and "no radar here" is one of the answers rather
 * than a failure to produce one.
 */
export function probeAt(
  g: ProbeGrid,
  line: number,
  sample: number,
  latlon: { lat: number; lon: number } | null,
): ProbeSample | null {
  const [L, S] = g.header.native_shape;
  if (line < 0 || line >= L || sample < 0 || sample >= S) return null;
  const k = g.header.decimation;
  const gy = Math.min(g.ny - 1, Math.max(0, Math.floor(line / k)));
  const gx = Math.min(g.nx - 1, Math.max(0, Math.floor(sample / k)));

  const cpr = at(g, 'cpr', gy, gx);
  const dop = at(g, 'dop', gy, gx);
  const amp = at(g, 'amplitude_fraction', gy, gx);
  const pointed = at(g, 'pointed_fraction', gy, gx);

  // Three states, and they are not the same claim. `amplitude > 0` is measured
  // radar. `pointed > 0` with no amplitude is ground the beam was aimed at that
  // returned literal integer zero — 56.11 % of ISRO's own sri_ma swath. Neither
  // is "never observed", and collapsing the middle case into either end would
  // lose the distinction the two-mask model exists to carry.
  const coverage = amp > 0 ? 'measured'
    : pointed > 0 ? 'pointed-no-return'
      : 'never-observed';

  return {
    line, sample, cell: { gy, gx },
    latDeg: latlon ? latlon.lat : null,
    lonDeg: latlon ? latlon.lon : null,
    cpr: Number.isFinite(cpr) ? cpr : null,
    dop: Number.isFinite(dop) ? dop : null,
    amplitudeFraction: amp,
    pointedFraction: pointed,
    psrFraction: at(g, 'psr_fraction', gy, gx),
    illumination: at(g, 'illumination', gy, gx),
    elevationM: at(g, 'elevation_m', gy, gx),
    coverage,
  };
}
