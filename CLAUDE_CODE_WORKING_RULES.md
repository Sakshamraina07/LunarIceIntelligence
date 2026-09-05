# Working rules for Claude Code — build first, verify once

> Paste this at the **start** of any session, before the handoff. It governs *how* the work is
> done; the handoff governs *what* gets done. If the two conflict, ask.

---

## 1 · Build the whole handoff before you open a browser

No dev server checks, no screenshots, no "let me just see how this looks" between steps. Write every file the handoff lists, then stop and typecheck.

The only gate before verification is:

```
npx tsc --noEmit -p tsconfig.app.json
```

Exit 0, or fix and re-run. Nothing visual until that passes.

**One exception, and it is an ordering exception, not a licence:** if the handoff asks for before/after evidence, capture the **entire "before" set in one pass at the very start**, before touching any file. Then close the browser and do not return to it until all code is written.

## 2 · Two browser sessions per handoff, maximum

- **Pass A** — the "before" capture, only if the handoff asks for it. One pass, all shots, then out.
- **Pass B** — the full verification after every file is written and typecheck is clean.
- **Pass C** exists only if Pass B fails the gate. Then: fix **every** finding in one batch, and re-verify once.

What is not allowed is the loop: change one thing → look → change one thing → look. That loop is what eats the time. Collect all findings from a single pass, fix them together, verify once.

## 3 · Make verification a script, not a poking session

Put the capture in a committed script so "verify" is one command and produces the same evidence every time:

```
frontend/scripts/verify_map.mjs
```

It should, in a single run: set the layer, set zoom and centre deterministically, screenshot, sample the canvas pixel means for each region under test, print the counts and histograms the handoff asked for, and write the images to `docs/`. One command, all evidence, reproducible by me later.

Two automation facts that make a single pass survive — both already measured in this project:

- `document.hidden === true` under automation, so `requestAnimationFrame` never fires and **every animated Leaflet move silently stalls**. Do not use `zoomIn` / `zoomOut` / `flyTo` / `flyToBounds` in the script. Use `setZoom(z, { animate: false })` and `setView(centre, z, { animate: false })`.
- Wait on the image `load` event, not a fixed timeout. The overlay swaps preview → full asynchronously, so a screenshot taken on a timer can catch the 640 px preview and you will report the wrong thing.

## 4 · Prefer numbers over pictures

A screenshot is evidence for a human at the end. It is a bad instrument for you mid-work. Where a claim can be a number, make it a number: pixel means, histograms, percentile tables, counts, byte sizes, request counts, residuals.

Print numbers freely — they are cheap. Take screenshots only for what the handoff's gate explicitly asks for.

If a number and a screenshot disagree, **say so in the report instead of picking one.** That contradiction going unflagged is how a fabricated verdict shipped once already.

## 5 · One report at the end

Not a running commentary. One report, structured as:

1. What was built — files touched, with line counts.
2. Typecheck result.
3. The evidence the gate asked for, in the order it asked for it.
4. Anything that disagreed with the handoff's assumptions, with the measurement that shows it.
5. What is still open, and what you chose not to touch because it was out of scope.

Section 4 is the most valuable part. If a number in the handoff is wrong, say it and show the measurement — that has happened repeatedly and has been right every time.

## 6 · Standing constraints — these never relax

- Return every touched file **complete**, not as a diff or a snippet.
- `MissionMapHandle` stays byte-identical: `zoomIn` / `zoomOut` / `reset`.
- Prop changes are **additive only** unless the handoff says otherwise.
- No `rasterio`, no GDAL, nothing new in `requirements.txt` — Render cannot build scipy from source. Local Python has numpy, cv2, PIL, scipy, tifffile.
- Never `imread` a multi-gigabyte raster whole. `np.memmap` and windowed reads.
- **Never invent a number.** If it cannot be computed from real data, label it or withhold it. A plausible placeholder in the slot where a measurement belongs is the worst outcome available.
- Destructive git operations do not run without explicit confirmation in the session.
