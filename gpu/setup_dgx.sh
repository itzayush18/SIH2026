#!/usr/bin/env bash
# One-time environment setup on the DGX. Run from the repo root after cloning.
#   ssh <you>@<dgx>
#   git clone <repo-url> oiltrace && cd oiltrace
#   bash gpu/setup_dgx.sh
set -euo pipefail

echo "== GPUs on this box =="
nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv || {
  echo "nvidia-smi failed — are you on a GPU node? (on a DGX Slurm cluster you may need: srun --gres=gpu:1 --pty bash)"; exit 1; }

CUDA_TAG="${1:-cu121}"   # override: bash gpu/setup_dgx.sh cu124   (match nvidia-smi CUDA)
echo "== creating venv (torch wheel: $CUDA_TAG) =="
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip wheel

# core repo deps (numpy/scipy/pillow/fastapi/uvicorn) + training deps
pip install -r requirements.txt
pip install "torch" "torchvision" --index-url "https://download.pytorch.org/whl/${CUDA_TAG}"
pip install segmentation-models-pytorch pillow tqdm

echo "== verify CUDA is visible to torch =="
python - <<'PY'
import torch
ok = torch.cuda.is_available()
print("cuda available:", ok)
if ok:
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        print(f"  GPU {i}: {p.name}  {p.total_memory//(1024**3)} GB")
else:
    print("!! torch can't see the GPU — wrong CUDA wheel or not on a GPU node.")
PY
echo "== done. Next: bash gpu/get_zenodo.sh  then  bash gpu/train.sh =="
