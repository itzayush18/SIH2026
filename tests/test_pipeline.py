"""Fast checks on the parts that are easy to break silently.

Run with:  python -m pytest tests -q      (or plain `python tests/test_pipeline.py`)
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sagar.core import ais, characterize, detect, drift, geoutil, inversion, scenario
from sagar.core.environment import SyntheticOcean
from sagar.core.geoutil import Origin

ORIGIN = Origin(19.35, 71.80)


def test_geo_roundtrip():
    for lat, lon in [(19.4, 71.9), (18.9, 72.4), (20.1, 71.2)]:
        x, y = ORIGIN.to_xy(lat, lon)
        la, lo = ORIGIN.to_ll(x, y)
        assert abs(la - lat) < 1e-9 and abs(lo - lon) < 1e-9


def test_geo_vectorised():
    x, y = ORIGIN.to_xy(np.array([19.4, 19.5]), np.array([71.9, 72.0]))
    assert x.shape == (2,)


def test_bearing_and_angdiff():
    assert abs(geoutil.bearing(0, 0, 1, 0) - 0.0) < 1e-6
    assert abs(geoutil.bearing(0, 0, 0, 1) - 90.0) < 1e-6
    assert abs(geoutil.angdiff(350, 10) - 20.0) < 1e-9


def test_lee_filter_preserves_mean():
    rng = np.random.default_rng(0)
    img = rng.gamma(4.4, 1 / 4.4, (128, 128))
    out = detect.lee_filter(img, looks=4.4)
    assert abs(out.mean() - img.mean()) < 0.05
    assert out.std() < img.std()          # speckle actually suppressed


def test_drift_backward_reverses_advection():
    """With diffusion and windage off, forward-then-backward must return home."""
    ocean = SyntheticOcean(ORIGIN, seed=1)
    saved = drift.K_DIFF
    drift.K_DIFF = 0.0
    try:
        f = drift.integrate(ocean, np.array([0.0]), np.array([0.0]), 0.0,
                            6 * 3600.0, dt=60.0, windage=False)
        b = drift.integrate(ocean, f.x[-1], f.y[-1], 6 * 3600.0, 6 * 3600.0,
                            dt=60.0, backward=True, windage=False)
        err = math.hypot(float(b.x[-1][0]), float(b.y[-1][0]))
        assert err < 200.0, f"round-trip error {err:.0f} m"
    finally:
        drift.K_DIFF = saved


def test_thickness_monotonic_in_contrast():
    prev = 0.0
    for c in (1.0, 4.0, 6.5, 9.0, 13.0):
        t = characterize.thickness_from_contrast(c)["thickness_m"]
        assert t > prev
        prev = t


def test_ais_gap_detection_and_interpolation():
    v = ais.Vessel("1", "T", 80, 200, 10, [
        ais.Ping(0, 19.0, 71.0, 12, 90), ais.Ping(600, 19.0, 71.1, 12, 90),
        ais.Ping(4200, 19.0, 71.5, 12, 90)])
    assert v.gaps() == [(600.0, 4200.0)]
    assert v.position_at(-10) is None            # no extrapolation before coverage
    lat, lon, sog, cog, _ = v.position_at(300)
    assert abs(lon - 71.05) < 1e-6 and abs(lat - 19.0) < 1e-9


def test_ais_csv_roundtrip(tmp_path=None):
    import tempfile
    d = tmp_path or tempfile.mkdtemp()
    path = os.path.join(str(d), "ais.csv")
    vessels = ais.synthesize(ORIGIN, (-9000.0, -13000.0), -13 * 3600.0, seed=5)
    ais.write_csv(path, vessels)
    back = ais.load_csv(path, epoch_iso="2026-03-14T06:00:00")
    assert set(back) == set(vessels)
    assert sum(len(v.pings) for v in back.values()) == \
        sum(len(v.pings) for v in vessels.values())


def test_detection_recovers_slick():
    scene, _, _ = scenario.build(ORIGIN, seed=11, size=512, pixel_m=90.0)
    dets, lab = detect.detect(scene)
    assert dets, "no detection"
    m = detect.evaluate(lab == dets[0].mask_index, scene.truth_mask)
    assert m["iou"] > 0.5, m


def test_source_track_match_rejects_wrong_time():
    """A vessel on the right line six hours late must not score."""
    hyp = inversion.SourceHypothesis(t_start=-13 * 3600.0, duration=3600.0,
                                     course_deg=312.0, speed_kn=6.0,
                                     x0=-9000.0, y0=-13000.0)
    ts, xs, ys = hyp.track_xy(25)
    on_time, late = [], []
    for t, x, y in zip(ts, xs, ys):
        lat, lon = ORIGIN.to_ll(x, y)
        on_time.append(ais.Ping(float(t), float(lat), float(lon), 6, 312))
        late.append(ais.Ping(float(t) + 6 * 3600.0, float(lat), float(lon), 6, 312))
    good = ais.Vessel("A", "on time", 80, 200, 10, on_time)
    bad = ais.Vessel("B", "six hours late", 80, 200, 10, late)
    sg, _ = inversion.source_track_match(good, hyp, ORIGIN)
    sb, _ = inversion.source_track_match(bad, hyp, ORIGIN)
    assert sg > 0.8 and sb == 0.0, (sg, sb)





def test_oiltrace_jurisdiction_arabian_sea():
    from oiltrace.jurisdictions import classify
    j = classify(19.35, 71.80)
    assert j.kind in ("SPECIAL_AREA", "EEZ")
    assert "Oman" in j.name or "India" in j.name


def test_oiltrace_alerts_derive():
    from oiltrace import alerts, incidents
    r = incidents.run("arabian-tanker", "data/out")
    kinds = {a["kind"] for a in r["oiltrace"]["alerts"]}
    assert "NEW_SPILL" in kinds
    assert any(a["severity"] in ("CRITICAL", "HIGH") for a in r["oiltrace"]["alerts"])


def test_oiltrace_evidence_files_written():
    import os
    from oiltrace import incidents
    r = incidents.run("arabian-tanker", "data/out")
    p = r["oiltrace"]["evidence_pack"]
    for k in ("json", "geojson", "csv"):
        assert os.path.exists(os.path.join(p["outdir"], p[k])), k


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
