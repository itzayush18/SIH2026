# GPU kit — train the U-Net oil-spill segmenter on the DGX

This is the one GPU task worth doing: train a real U-Net on the **Zenodo
Sentinel-1 oil-spill dataset** so detection moves from the simulated-scene
logistic baseline (test AUC 1.000, which won't survive real data) to an honest
~0.85 IoU number on real SAR. Everything else in the pipeline runs on CPU.

Nothing here has been run yet — the scripts are built to the real interfaces
(`scripts/train_unet.py`, `scripts/fetch/zenodo.py`) but the Zenodo archive's
exact folder layout and mask encoding are unverified until you extract it, which
is exactly what the `--inspect` step (STEP 1 below) checks before you burn GPU
hours.

## 0. Get onto the DGX and get the code there
```bash
ssh <you>@<dgx-host>
# on a Slurm-managed DGX you may need an interactive GPU allocation first:
#   srun --gres=gpu:1 --cpus-per-task=8 --mem=64G --pty bash

git clone https://github.com/itzayush18/SIH2026.git oiltrace && cd oiltrace
git checkout oiltrace-realdata-dg      # the branch with all the current work
```

## 1. Set up the environment (one time)
```bash
nvidia-smi                              # note the CUDA version (top-right)
bash gpu/setup_dgx.sh                   # defaults to the cu121 torch wheel
# if nvidia-smi shows CUDA 12.4+, instead run:  bash gpu/setup_dgx.sh cu124
```
It ends by printing whether torch sees the GPU. If it says `cuda available: False`,
stop and fix that (wrong wheel / not on a GPU node) before going further.

## 2. Download + extract the dataset (~40 GB — use tmux)
```bash
tmux new -s data          # so an SSH disconnect doesn't kill the download
bash gpu/get_zenodo.sh
# detach anytime: Ctrl-b then d      reattach: tmux attach -t data
```
The download is resumable — if it dies, just re-run `bash gpu/get_zenodo.sh`.

## 3. Inspect, then train (use tmux)
```bash
tmux new -s train
bash gpu/train.sh
```
STEP 1 (inspect) prints how many image/mask pairs it found and the unique pixel
values in sample masks, then asks you to confirm before training. Read it:
- **pairs = 0** → the file extension or subfolder is different. Re-run with the
  right extension: `bash gpu/train.sh data/zenodo/part1 png`
- **masks show ~{0,255}** → binary, default is correct, just confirm.
- **masks show several distinct classes** (e.g. 0/1/2/3/4) → note which id means
  oil and pass it: `MASK_VALUES=1 bash gpu/train.sh`

Tuning (env vars): `EPOCHS=25 BATCH=16 SIZE=512`. On an A100/H100 80 GB, `BATCH=16`
at `SIZE=512` is comfortable; if you hit CUDA OOM, drop to `BATCH=8`. Watch the
first epoch's `val IoU` — if it's ~0 after epoch 1, stop and re-check STEP 1
rather than letting it run for hours on a bad label mapping.

## 4. Bring the trained model back
```bash
# best checkpoint is saved to data/models/unet_v1.pt on the DGX
scp <you>@<dgx-host>:$(pwd)/data/models/unet_v1.pt ./data/models/
```

## What this does NOT do yet (be honest)
- The checkpoint is a standalone U-Net; **wiring it in as the pipeline's
  `DetectionModel`** (so `detect.detect` uses it instead of the logistic
  classifier) is a separate follow-up, not done here.
- Don't chase foundation models (Prithvi/SatMAE/Clay) or PINNs — per the plan
  they need 24-80 GB VRAM, aren't trained on SAR oil signatures, and add nothing
  measurable over U-Net for this problem. One U-Net pass is the win.

## A note on "a new place for our work"
This `gpu/` folder is the dedicated home for DGX work. If you want a fully
separate Conductor workspace for it (isolated branch/checkout), start a new
workspace from Conductor and point it at this repo/branch — I can't open one for
you, but the branch `oiltrace-realdata-dg` already has everything to clone.
