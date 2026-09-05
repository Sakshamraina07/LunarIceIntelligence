"""
horizon.py -- terrain horizon angles, and the illumination they imply.

THE QUANTITY
------------
For a point p and an azimuth `az`, the horizon is the elevation angle of the
highest terrain seen along that ray:

    horizon(p, az) = max over r > 0 of  atan( (h(p + r*u_az) - h(p)) / r )

p is lit for a sun at `(az, el)` when `el > horizon(p, az)`. A permanently
shadowed region is a point for which that is false for every `(az, el)` the Sun
ever occupies.

This module returns the TANGENT of the horizon angle rather than the angle,
because every comparison it feeds is against `tan(el)` and the arctangent would
be computed only to be undone.

WHY NOT A RUNNING MAXIMUM
-------------------------
The obvious implementation -- sweep along the ray keeping a running maximum of
`(h - h0) / r` -- is wrong in a way that is easy to miss, because `r` is
different for every pair. A running maximum of elevation is not a running
maximum of slope: a low ridge nearby can subtend a larger angle than a high one
far away, and vice versa, so the maximising point is not the highest point.

`horizon_forward()` implements the standard O(n) skyline scan (Dozier, Bruno &
Downey 1981, as corrected by Dozier & Frew 1990). Sweeping backwards, the set of
points that can ever be a horizon for anything behind them forms a structure
where the candidate for `j` is reached by hopping along the candidates already
found. The hops are amortised O(1), and `horizon_forward_reference()` is the
O(n^2) brute force kept beside it so the fast one can be proved right rather
than believed.

VECTORISED OVER ROWS, NOT OVER COLUMNS
--------------------------------------
The scan is inherently sequential along the ray, so the loop over `j` cannot be
removed. It CAN be run for every row at once: each step is a handful of numpy
operations on a column vector. That turns an O(rows x cols) Python loop into an
O(cols) one, which is the difference between hours and minutes on a 2534^2 grid.
"""
from __future__ import annotations

import numpy as np

__all__ = [
    "horizon_forward",
    "horizon_forward_reference",
    "horizon_both_directions",
]


def horizon_forward_reference(h: np.ndarray, dx: float) -> np.ndarray:
    """
    Brute-force O(n^2) horizon in the +index direction, for ONE 1-D profile.

    Kept as the definition of correctness. `horizon_forward` must agree with it
    to floating-point tolerance on random terrain, and there is a test that says
    so. Never call this on real data -- it is here to check the fast path.
    """
    n = h.size
    out = np.zeros(n, dtype=np.float64)
    for j in range(n - 1):
        k = np.arange(j + 1, n)
        out[j] = np.max((h[j + 1:] - h[j]) / ((k - j) * dx))
    out[n - 1] = -np.inf
    return out


def horizon_forward(h: np.ndarray, dx: float, *, return_index: bool = False):
    """
    Horizon slope (tan of the angle) in the +column direction, for every row.

    `h` is (rows, cols) elevation in metres; `dx` is the ground spacing between
    adjacent columns, in metres. Returns (rows, cols) of
    `max over k>j of (h[k] - h[j]) / ((k - j) * dx)`, and `-inf` in the last
    column, where nothing lies ahead.

    NaN handling: NaN is terrain we have no data for, not terrain of height
    zero. A NaN anywhere in a row would poison every comparison, so NaNs are
    replaced by -inf before the scan -- an unknown cell then never occludes
    anything, which is the conservative direction for a SHADOW map. It makes a
    pixel more likely to be called lit, so a PSR reported here is not an
    artefact of missing data. The caller is told how many cells that affected.
    """
    if h.ndim != 2:
        raise ValueError(f"horizon_forward expects (rows, cols), got {h.shape}")
    rows, n = h.shape
    if n < 2:
        return np.full_like(h, -np.inf, dtype=np.float32)

    hh = np.where(np.isfinite(h), h, -np.inf).astype(np.float64, copy=True)

    # skyline[i, j] = index of the point that forms the horizon for (i, j).
    skyline = np.empty((rows, n), dtype=np.int32)
    skyline[:, n - 1] = n - 1
    idx = np.arange(rows)

    # -inf arithmetic is expected here, not exceptional: a no-data cell is -inf,
    # and (-inf) - (-inf) is nan whose comparisons are all False, which correctly
    # stops the hop. Warnings would be printed millions of times for a case the
    # algorithm handles by construction.
    err = np.errstate(invalid="ignore", divide="ignore")
    err.__enter__()
    for j in range(n - 2, -1, -1):
        k = np.full(rows, j + 1, dtype=np.int32)
        hj = hh[:, j]

        # Hop along the already-computed skyline until the candidate `k` beats
        # the candidate `k` itself points at. Amortised O(1) hops per column, so
        # this while loop runs a small number of times overall -- but it is a
        # genuine `while`, not a fixed unroll, because a pathological profile can
        # need many hops and silently truncating them would give a wrong horizon
        # that still looks plausible.
        active = k < (n - 1)
        while np.any(active):
            a = idx[active]
            ka = k[active]
            nxt = skyline[a, ka]
            # slope from j to k, and from j to where k points
            s_k = (hh[a, ka] - hj[active]) / ((ka - j) * dx)
            s_n = (hh[a, nxt] - hj[active]) / ((nxt - j) * dx)
            hop = s_k < s_n
            if not np.any(hop):
                break
            moving = a[hop]
            k[moving] = nxt[hop]
            active = np.zeros(rows, dtype=bool)
            active[moving] = k[moving] < (n - 1)

        skyline[:, j] = k
    err.__exit__(None, None, None)

    # The stored skyline gives the maximising index; evaluate the slope there.
    cols = np.arange(n)[None, :]
    dist = (skyline - cols) * dx
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (np.take_along_axis(hh, skyline, axis=1) - hh) / dist
    out[:, n - 1] = -np.inf
    # A row whose own cell is -inf (no data) has no meaningful horizon.
    out[~np.isfinite(hh)] = -np.inf
    if return_index:
        # The index of the crest that BOUNDS the view in this direction. Pass 2
        # of the illumination computation needs it to ask whether that crest is
        # itself permanently shadowed, which is the difference between a
        # singly-shadowed floor and a doubly-shadowed one.
        return out.astype(np.float32), skyline
    return out.astype(np.float32)


def horizon_both_directions(h: np.ndarray, dx: float, *, return_index: bool = False):
    """
    Horizon in the +column and -column directions from one rotation.

    Azimuth `az` and `az + 180` are the same line scanned in opposite senses, so
    every rotation of the DEM yields two azimuths. That halves the number of
    rotations, which is the dominant cost of the whole computation.

    With `return_index`, also returns the crest indices, with the backward pass's
    indices mapped back into the original column numbering.
    """
    if not return_index:
        fwd = horizon_forward(h, dx)
        bwd = horizon_forward(h[:, ::-1], dx)[:, ::-1]
        return fwd, bwd

    n = h.shape[1]
    fwd, fwd_i = horizon_forward(h, dx, return_index=True)
    bwd_r, bwd_i_r = horizon_forward(h[:, ::-1], dx, return_index=True)
    # Un-reverse both the values and the indices the reversed scan produced.
    bwd = bwd_r[:, ::-1]
    bwd_i = (n - 1 - bwd_i_r)[:, ::-1]
    return (fwd, fwd_i), (bwd, bwd_i)
