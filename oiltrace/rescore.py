"""Model-lab attribution re-scoring — spec §47-48.

Same attribution mechanism, different weights. Given a report and a new set of
axis weights, we recompute the six-term logistic against the *already-computed*
per-vessel terms, so the operator sees the ranking rearrange in real time
without waiting for the drift/inversion stages to re-run.
"""
from __future__ import annotations

import math

DEFAULT_WEIGHTS = dict(source_match=3.2, spatiotemporal=2.4, alignment=1.0,
                       behaviour=1.6, dark=1.2, prior=0.7)
DEFAULT_BIAS = -3.4


def rescore(suspects, weights=None, bias=None):
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    b = DEFAULT_BIAS if bias is None else bias
    out = []
    for s in suspects:
        t = s["terms"]
        z = b + sum(w[k] * t.get(k, 0.0) for k in w)
        z = max(-40.0, min(40.0, z))
        p = 1.0 / (1.0 + math.exp(-z))
        r = dict(s)
        r["score"] = float(p)
        r["_z"] = float(z)
        out.append(r)
    out.sort(key=lambda x: -x["score"])
    return out
