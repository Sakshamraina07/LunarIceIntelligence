# Working rules for this repository

**The specification is `PRD.md` at the repository root. Read that first.** It is
the only active spec; `docs/handoffs/` holds nine superseded ones that
contradict each other and are kept only for traceability.

This file previously contained a single line, `@AGENTS.md`, importing a block of
Next.js agent rules that `next dev` wrote into the repository. The Next.js
scaffold was removed in PRD Phase 1E — it was v0.dev boilerplate whose only page
redirected to a hardcoded `localhost:5173`, and nothing in the product imported
it. Those rules described a framework this project does not use.

## Layout

```
frontend/     Vite + React. The application. `npm run dev` from the root proxies here.
backend/      FastAPI + numpy/scipy. `npm run backend`.
backend/scripts/  The offline producers: ingest, build_analysis, render_layers.
data/         Raw and derived rasters. Gitignored; ~9 GB of Chandrayaan-2 SAR + LOLA.
docs/         Provenance, methods, verification evidence, superseded handoffs.
```

## The rule that matters most

Every number that reaches a screen carries a provenance mark — `MEASURED`,
`DERIVED`, `MODELLED` or `NO DATA` — and resolves to a raster read or an
explicit absent state. `np.zeros_like` is not an absent state, and a plausible
placeholder in the slot where a measurement belongs is the worst outcome
available. A measured zero is a result and is presented as one.

`docs/PROVENANCE.md` is generated, not written: `python backend/scripts/emit_provenance.py`
fails the build if any value reaches the UI unmarked. See PRD §2 for the rest.
