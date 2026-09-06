# Rover Traverse Planning — SUPERSEDED

**This described a planner on 250 m cells with a science-value term, and both are
gone.**

The 250 m figure was not the spacing of any grid in this project — it was a
default that multiplied both axes alike, on a frame whose real spacings are
27.56 m per line and 80.79 m per sample. The `science` term double-counted
distance, which had already been subtracted.

PRD Phase 4 replaced it. The current planner and its results are in
**`METHODS.md` §10**: connectivity reported before any distance, Dijkstra at a
stated 100 m planning resolution with lengths quantised to it, an energy proxy
marked DERIVED and reported per kilogram so no rover mass is invented, and
`UNREACHABLE` as an explicit state rather than a distance of zero.

The artifact is `docs/traverse.json`.
