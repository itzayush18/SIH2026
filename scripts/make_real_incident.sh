#!/usr/bin/env bash
# One command: fetch a real Sentinel-1 scene + MATCHING ocean (CMEMS currents +
# ERA5 wind) for the SAME AOI/date, then run the full pipeline so drift uses real
# forcing (no more wind 0.0). Result appears on the map on next server start.
#
# Needs credentials loaded first:   set -a; source .env; set +a
# (CDS_UID/CDS_KEY for ERA5, CMEMS_USER/CMEMS_PASSWORD for currents — CDSE is not
#  needed here because the SAR comes from Microsoft Planetary Computer.)
#
# Usage:
#   scripts/make_real_incident.sh <name> <bbox w,s,e,n> <s1_start> <s1_end> <epoch_iso>
#
# Ennore / Chennai 2017 spill (the shipped example):
#   scripts/make_real_incident.sh ennore 80.0,12.8,80.6,13.5 \
#       2017-01-28 2017-02-15 2017-01-29T00:31:45
set -euo pipefail

NAME="${1:?name}"; BBOX="${2:?bbox w,s,e,n}"
S1_START="${3:?s1 start YYYY-MM-DD}"; S1_END="${4:?s1 end YYYY-MM-DD}"
EPOCH="${5:?epoch ISO, e.g. 2017-01-29T00:31:45}"
PY=.venv/bin/python
ENV_DIR="data/env/${NAME}"
SCENE="data/scenes/spill_${NAME}.tif"

echo "== 1/3  Sentinel-1 (MPC RTC, calibrated dB) =="
$PY scripts/fetch/sentinel1_mpc.py --bbox "$BBOX" \
    --start "$S1_START" --end "$S1_END" --out "$SCENE" --size 1024

echo "== 2/3  matching ocean: CMEMS currents + ERA5 wind for the same AOI =="
# CMEMS/ERA5 want a day range; use the SAR window (a couple of days spanning the drift).
$PY scripts/fetch/cmems_era5.py --bbox "$BBOX" \
    --start "$S1_START" --end "$S1_END" --out "$ENV_DIR"

# Optional: real satellite AIS (covers India, unlike aisstream). Uses whichever
# provider key is set — VesselAPI (free tier) preferred, else Data Docked.
AIS_CSV=""
if [ -n "${VESSELAPI_KEY:-}" ]; then
  echo "== 2b  real AIS snapshot from VesselAPI (India-covered) =="
  AIS_CSV="data/ais/${NAME}_ais.csv"
  $PY scripts/fetch/vesselapi.py --bbox "$BBOX" --epoch "$EPOCH" --out "$AIS_CSV" \
    || { echo "  (VesselAPI fetch failed — falling back to synthetic vessels)"; AIS_CSV=""; }
elif [ -n "${DATADOCKED_KEY:-}" ]; then
  echo "== 2b  real AIS snapshot from Data Docked (India-covered, 10 credits) =="
  AIS_CSV="data/ais/${NAME}_ais.csv"
  $PY scripts/fetch/datadocked.py --bbox "$BBOX" --epoch "$EPOCH" --out "$AIS_CSV" \
    || { echo "  (Data Docked fetch failed — falling back to synthetic vessels)"; AIS_CSV=""; }
else
  echo "== 2b  no AIS provider key set — using synthetic candidate vessels =="
fi

echo "== 3/3  run the full pipeline with REAL forcing =="
$PY - "$NAME" "$SCENE" "$ENV_DIR" "$EPOCH" "$AIS_CSV" <<'PY'
import sys; sys.path.insert(0, ".")
from oiltrace import incidents
name, scene, envd, epoch, ais_csv = sys.argv[1:6]
rep = incidents.run_real(
    scene_path=scene,
    currents_nc=f"{envd}/cmems_currents.nc",
    winds_nc=f"{envd}/era5_wind.nc",
    epoch_iso=epoch, outdir_root="data/out",
    ais_csv=(ais_csv or None), synth_vessels=True, p_threshold=0.5, n_particles=4000)
o = rep["oiltrace"]; d = rep["detections"][0]
src = rep.get("source", {})
print(f"\nOK {o['incident_id']} | {len(rep['detections'])} det | top {d['area_km2']:.1f} km2 "
      f"| coast {o['nearest_coast']['km']:.0f} km {o['nearest_coast']['name']} "
      f"| inversion fit IoU {src.get('iou','?')}")
PY

echo
echo "Done. Restart the server to see it on the map:"
echo "  pkill -f oiltrace.server; set -a; source .env; set +a"
echo "  .venv/bin/python -m oiltrace.server --port 8000 --no-warm"
