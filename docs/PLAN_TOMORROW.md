# OILTRACE — GPU day plan (2026-09-02, college GPU + Kioxia SSD)

Written 2026-09-01 night. Source material: `.context/attachments/.../pasted_text_2026-09-01_20-55-57.txt`
(a deep-research read of the "OceanSentry AI" blueprint). That doc is honest about
itself — "~40% is name-drop LLM-slop" — and one of its own numbers turned out to
be exactly that. Corrected below.

## The correction that changes tonight's plan

The blueprint says the Zenodo Sentinel-1 oil-spill dataset is **"Free, 2 GB total."**
I hit the actual Zenodo API (`https://zenodo.org/api/records/<id>`) to check. Real sizes:

| Part | Record | Contents | Real size |
|---|---|---|---|
| I | 8346860 | train/val oil images + masks | 40.7 GB + 6 MB |
| II | 8253899 | train/val no-oil + look-alike | 45.9 GB |
| III | 13761290 | test | 9.9 GB |
| **Total** | | | **~96.5 GB** |

That's ~48x the claimed size. Plan accordingly: **Part I only** for tomorrow (it's
the T1-essential one anyway — Parts II/III are "useful" and "test-only", skip
until Part I actually trains something). Even Part I alone is a real download,
not a coffee-break one.

**Also found:** this Claude Code sandbox's own network egress is capped at
~200 KB/s (measured — a live download here showed a 52+ hour ETA for the 37.9 GB
Part I image archive). That is almost certainly a sandbox restriction, not your
real connection — **run the actual download commands below from a normal
Terminal window on your Mac, not by asking me to do it**, or it'll crawl.

**Also found:** your Kioxia SSD (`/Volumes/KIOXIA`, 808 GB free) was already
plugged into this Mac. I copied the current code (this repo, minus `.venv`/
`.git`/`data/out`) to `/Volumes/KIOXIA/oiltrace-data/code/port-vila/` so it's on
the drive regardless of what happens to this workspace. It's a plain file copy,
not a git clone — `git` on your college machine won't work from it as-is (see
"getting the code onto the GPU machine" below).

## What I built tonight (in this repo, now also on the SSD copy)

Three new scripts, all syntax-checked; `train_unet.py`'s data-loading path was
smoke-tested end-to-end against fake images (pairing, --inspect, resize, mask
thresholding). None have touched real Zenodo/Sentinel-1/CMEMS data — they can't
be fully proven correct until you run them against the real thing tomorrow.

- **`scripts/fetch/zenodo.py`** — resumable (`curl -C -`) downloader for a
  Zenodo record's files, resolved via the API rather than guessed filenames.
- **`scripts/run_real.py`** — runs detect → characterise → hindcast/forecast →
  invert → attribute on a real Sentinel-1 scene + real CMEMS/ERA5 + real AIS,
  instead of the synthetic scenario `scripts/run_demo.py` always uses. Skips
  the validation block (no ground truth exists for a real scene — that's
  correct behaviour, not a missing feature).
- **`scripts/train_unet.py`** — U-Net (`segmentation_models_pytorch`, resnet34
  encoder) trainer for oil/no-oil segmentation on Zenodo Part I. Has an
  `--inspect` mode: pairs images/masks by filename and prints what it found
  *before* you commit to a multi-hour run. This matters because nobody has
  opened the actual archive yet — directory layout and mask pixel encoding
  (binary vs multi-class palette) are unverified. Also already found one real
  bug this way: JPEG-compressed masks carry compression noise at edges (a
  synthetic test mask that should have had 2 pixel values had 19), so the
  default oil threshold is `pixel > 127`, not `pixel > 0`.

Already in the repo before tonight (verified by reading, not written by me):
`scripts/fetch/sentinel1.py` (CDSE), `scripts/fetch/cmems_era5.py` (CMEMS +
ERA5), `scripts/fetch/aishub.py`, `scripts/fetch/all.py` (orchestrator). The
blueprint's roadmap items 1–2 ("fetch real S1 scene", "fetch real CMEMS/ERA5")
are mostly *already built* — they just need credentials and one command each.

## Tonight (before you sleep) — do these, they gate tomorrow

Registration can involve email verification / manual approval delay, so don't
leave it for the morning:

1. **Register** (all free):
   - CDSE — https://dataspace.copernicus.eu/ → `CDSE_USER` / `CDSE_PASSWORD`
   - CMEMS — https://marine.copernicus.eu/ → `CMEMS_USER` / `CMEMS_PASSWORD`
   - CDS (ERA5) — https://cds.climate.copernicus.eu/api-how-to → `CDS_UID` / `CDS_KEY`
   - (optional) AISHub — https://www.aishub.net/ → `AISHUB_USER`, free with a receiver contribution
   - (optional) an Anthropic API key, if you want the LLM narrative panel (item 4 below)
2. Fill `.env` (copy from `.env.example`) with whatever you get tonight; leave
   the rest blank, `scripts/fetch/all.py` skips anything without credentials.
3. **Kick off the Part I download from a normal Terminal** (not through me —
   see the network cap note above), onto the SSD:
   ```
   cd ~/conductor/workspaces/dert/port-vila   # or wherever this repo actually lives on your Mac
   python3 scripts/fetch/zenodo.py --record 8346860 --out /Volumes/KIOXIA/oiltrace-data/zenodo/part1
   ```
   It's resumable — if it's not done by morning, unplug the SSD, take it to
   college, plug it back in, run the exact same command again, it continues
   from where it stopped (`curl -C -`). Don't `rm` a partial file.
4. Note: `git remote -v` shows an `oiltrace` remote
   (`github.com/DG10911/oiltrace.git`) that currently returns "repository not
   found" — private/renamed/deleted, unclear which. Didn't touch it. If you
   want this branch (`sih26143`) pushed somewhere reachable from college,
   say so explicitly and where.

## Tomorrow at college — commands, in order

**0. Get the code onto the GPU machine.** The SSD has a plain copy at
`oiltrace-data/code/port-vila/` (no `.git`). Simplest: just work from that
directory on the SSD directly (or `cp -r` it to local disk first — training
will thrash a slow/USB SSD less if the *code* is local and only the *dataset*
stays on the SSD).

**1. Check the GPU and match torch to it:**
```
nvidia-smi                     # note the CUDA version in the top-right corner
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# pick ONE, matching nvidia-smi's CUDA version (12.1 shown here — check yours):
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install segmentation-models-pytorch pillow
python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
If `torch.cuda.is_available()` is `False`, stop and fix that before anything
else — training on CPU is not a 3-hour job anymore.

**2. Finish/verify the dataset, extract it (it's `.7z`, not `.zip`):**
```
sudo apt install p7zip-full    # or brew install p7zip on macOS
DATA=/Volumes/KIOXIA/oiltrace-data
7z x "$DATA/zenodo/part1/01_Train_Val_Oil_Spill_images.7z" -o"$DATA/zenodo/part1/images"
7z x "$DATA/zenodo/part1/01_Train_Val_Oil_Spill_mask.7z"   -o"$DATA/zenodo/part1/masks"
```

**3. Inspect before training — this is the step that catches a wrong assumption
in 30 seconds instead of after a 3-hour run:**
```
python3 scripts/train_unet.py \
    --images "$DATA/zenodo/part1/images/**/*.jpg" \
    --masks  "$DATA/zenodo/part1/masks/**/*.jpg" \
    --inspect
```
Read the printed mask unique-values. If it's basically `{0, 255}` (small
in-between values are JPEG noise, already handled), proceed as-is. If you see
more than ~2 real classes, pass `--mask-values <id(s) that mean oil>` on the
train command below — see the script's own docstring for the exact flag.

**4. Train:**
```
python3 scripts/train_unet.py \
    --images "$DATA/zenodo/part1/images/**/*.jpg" \
    --masks  "$DATA/zenodo/part1/masks/**/*.jpg" \
    --epochs 20 --batch-size 8 --out "$DATA/models/unet_v1.pt"
```
~3-4h on a T4-class GPU per the blueprint's own estimate; watch the first
epoch's `val IoU` — if it's near 0 after epoch 1, stop and re-check step 3
rather than let it run for hours on a bad label mapping.

**5. Real Sentinel-1 + CMEMS/ERA5 + AIS through the actual pipeline** (kills
the "SIMULATION" banner honestly, not just cosmetically):
```
# pick a real AOI + date range you know had a documented spill or heavy traffic
BBOX=71.4,19.0,72.1,19.7
python3 scripts/fetch/sentinel1.py --bbox $BBOX --start 2026-03-13T00:00 --end 2026-03-15T00:00 --out data/scenes/s1.tif
python3 scripts/fetch/cmems_era5.py --bbox $BBOX --start 2026-03-13 --end 2026-03-15 --out data/env
python3 scripts/fetch/aishub.py --bbox $BBOX --out data/ais/aishub.csv

python3 scripts/run_real.py --scene data/scenes/s1.tif \
    --currents data/env/cmems_currents.nc --winds data/env/era5_wind.nc \
    --ais data/ais/aishub.csv --epoch 2026-03-14T06:00:00 --out data/out/real
```
If `detect.detect` finds nothing, retry with `--p-threshold 0.3` — the
classifier was trained on simulated scenes and may be under-confident on real
SAR until it's retrained on Zenodo (step 4).

**6. If steps 1-5 land with time left — SAM click-to-refine (no local GPU
needed, HuggingFace inference endpoint):**
```
pip install segment-anything
# checkpoint from Meta's own SAM repo (official, not guessed):
# https://github.com/facebookresearch/segment-anything#model-checkpoints
```
This is a UI feature (click a point on the slick, SAM refines the polygon) —
wiring it into `web/index.html` / `oiltrace/server.py` is real work, not a
one-liner; budget it as its own session rather than squeezing it in.

**7. LLM narrative panel — no GPU, can genuinely be done from anywhere,
including right now tonight if you want it built in this session instead of
tomorrow.** Needs an Anthropic API key in `.env`. Say the word and I'll wire it
into the Overview tab now rather than adding it to tomorrow's list.

## What NOT to burn GPU hours on tomorrow (the blueprint agrees with itself here)

Skip: Prithvi / SatMAE / Clay / FourCastNet / Pangu / GraphCast (24-80 GB VRAM,
trained on optical not SAR, no measurable gain for this problem), PINN drift
(the Lagrangian RK2 + source inversion is already better for this specific
attribution task), Mask R-CNN / YOLO (detection, not segmentation — wrong tool
for slick masks), ensemble-of-5 architectures, Kafka streaming, oil-type
classification from SAR alone (not credible without optical + a reference
library). None of these move the needle enough to be worth a GPU day at college.

## Honest state of "done" after today

- Real data adapters (`load_geotiff`, `NetCDFOcean`, `ais.load_csv`) already
  existed and are unmodified — they were the load-bearing 30% of the blueprint
  that was already true.
- Fetch scripts for Sentinel-1/CMEMS/ERA5/AIS already existed. Added Zenodo.
- U-Net trainer and a real-data pipeline runner are new tonight, syntax-checked
  and logic-smoke-tested on fake data, **not yet run against anything real** —
  that's tomorrow's actual first test.
- Dataset download did not meaningfully progress tonight (sandbox network cap)
  — it depends on you running it from a real terminal on real bandwidth.
