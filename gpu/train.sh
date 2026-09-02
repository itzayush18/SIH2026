#!/usr/bin/env bash
# Inspect then train the U-Net oil/no-oil segmenter on the Zenodo dataset.
# Run inside tmux (training is long-ish even on an A100):
#   tmux new -s train ; bash gpu/train.sh
set -euo pipefail
source .venv/bin/activate

DATA="${1:-data/zenodo/part1}"
EXT="${2:-jpg}"          # change to png/tif if --inspect shows a different extension
EPOCHS="${EPOCHS:-25}"
BATCH="${BATCH:-16}"     # A100/H100 80GB handles 16+ at size 512; drop to 8 if OOM
SIZE="${SIZE:-512}"
OUT="${OUT:-data/models/unet_v1.pt}"

IMG="$DATA/images/**/*.$EXT"
MSK="$DATA/masks/**/*.$EXT"

echo "=========================================================="
echo " STEP 1  INSPECT  (pairs files + prints mask pixel values)"
echo " If pairs=0, fix EXT (arg 2) or the images/masks subpaths."
echo " If masks show many classes, note the oil class id for --mask-values."
echo "=========================================================="
python scripts/train_unet.py --images "$IMG" --masks "$MSK" --inspect

echo
read -r -p "Layout looks right? Start training ${EPOCHS} epochs? [y/N] " ok
[ "$ok" = "y" ] || { echo "aborted — adjust EXT/paths and re-run"; exit 0; }

echo "== training: epochs=$EPOCHS batch=$BATCH size=$SIZE -> $OUT =="
python scripts/train_unet.py \
  --images "$IMG" --masks "$MSK" \
  --epochs "$EPOCHS" --batch-size "$BATCH" --size "$SIZE" \
  --out "$OUT" \
  ${MASK_VALUES:+--mask-values "$MASK_VALUES"}

echo "== done. Best checkpoint -> $OUT =="
echo "Copy it back to your laptop with:  scp <dgx>:$(pwd)/$OUT ./data/models/"
