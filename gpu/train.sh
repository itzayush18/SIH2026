#!/usr/bin/env bash
# Inspect then train the U-Net oil/no-oil segmenter on the Zenodo dataset.
# Run inside tmux (training is long-ish even on an A100):
#   tmux new -s train ; bash gpu/train.sh
set -euo pipefail
source .venv/bin/activate

# Corporate/faculty clusters often can't verify TLS certs -> point Python + curl
# at certifi's CA bundle so encoder-weight / dataset downloads work.
CERT="$(python -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
if [ -n "$CERT" ]; then export SSL_CERT_FILE="$CERT" REQUESTS_CA_BUNDLE="$CERT" CURL_CA_BUNDLE="$CERT"; fi

DATA="${1:-data/zenodo/part1}"
EPOCHS="${EPOCHS:-25}"
BATCH="${BATCH:-16}"     # A100 40GB handles 16 at size 512; drop to 8 if OOM
SIZE="${SIZE:-512}"
OUT="${OUT:-data/models/unet_v1.pt}"

if [ ! -d "$DATA/images" ] || [ -z "$(find "$DATA/images" -type f 2>/dev/null | head -1)" ]; then
  echo "!! No data in $DATA/images — run the DOWNLOAD first:  bash gpu/get_zenodo.sh"
  exit 1
fi

# Auto-detect the dominant image/mask file extensions (jpg/png/tif) so you don't
# have to guess. Override with arg 2 (e.g. bash gpu/train.sh data/zenodo/part1 png).
_ext(){ find "$1" -type f 2>/dev/null | sed 's/.*\.//' | tr 'A-Z' 'a-z' \
        | grep -Ei 'jpg|jpeg|png|tif|tiff|bmp' | sort | uniq -c | sort -rn \
        | head -1 | awk '{print $2}'; }
IEXT="${2:-$(_ext "$DATA/images")}"; IEXT="${IEXT:-jpg}"
MEXT="$(_ext "$DATA/masks")"; MEXT="${MEXT:-$IEXT}"
echo "detected image ext: .$IEXT   mask ext: .$MEXT"

IMG="$DATA/images/**/*.$IEXT"
MSK="$DATA/masks/**/*.$MEXT"

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
