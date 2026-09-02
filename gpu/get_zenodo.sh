#!/usr/bin/env bash
# Download + extract the Zenodo Sentinel-1 oil-spill dataset (Part I = train/val).
# ~40 GB image archive — run inside tmux so an SSH drop doesn't kill it:
#   tmux new -s data           (detach: Ctrl-b d   reattach: tmux attach -t data)
#   bash gpu/get_zenodo.sh
set -euo pipefail
source .venv/bin/activate 2>/dev/null || true
CERT="$(python -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
if [ -n "$CERT" ]; then export SSL_CERT_FILE="$CERT" REQUESTS_CA_BUNDLE="$CERT" CURL_CA_BUNDLE="$CERT"; fi

DATA="${1:-data/zenodo/part1}"
mkdir -p "$DATA"

echo "== downloading Part I (record 8346860): ~40 GB images + 6 MB masks (resumable) =="
python scripts/fetch/zenodo.py --record 8346860 --out "$DATA"

echo "== extracting .7z archives =="
if ! command -v 7z >/dev/null 2>&1; then
  echo "installing p7zip ..."
  (sudo apt-get update && sudo apt-get install -y p7zip-full) \
    || conda install -y -c conda-forge p7zip \
    || { echo "install p7zip manually, then re-run"; exit 1; }
fi
7z x "$DATA/01_Train_Val_Oil_Spill_images.7z" -o"$DATA/images" -y
7z x "$DATA/01_Train_Val_Oil_Spill_mask.7z"   -o"$DATA/masks"  -y

echo "== extracted. Sample layout: =="
find "$DATA/images" -maxdepth 3 -type f | head -3
find "$DATA/masks"  -maxdepth 3 -type f | head -3
echo "== done. Next: bash gpu/train.sh $DATA =="
