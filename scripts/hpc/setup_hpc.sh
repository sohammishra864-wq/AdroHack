#!/bin/bash
# Runs ON THE HPC LOGIN NODE (it has internet; compute nodes do not). Normally started from
# the laptop with:  bash scripts/hpc/hpc.sh setup
# Creates $SCRATCH/claimshield/.venv and downloads the generator weights (~57 GB) into
# $SCRATCH/models/hf. Safe to re-run: pip and huggingface-cli skip what is already there.
# Env: CUDA_WHL (default cu121 — match `nvidia-smi` on a GPU node). If a repo is gated
# (Flux may be), run `huggingface-cli login` once on the login node before this script.
set -euo pipefail
: "${SCRATCH:?SCRATCH is not set on this cluster — export SCRATCH=/path/to/your/scratch first}"
cd "$SCRATCH/claimshield"
mkdir -p logs data "$SCRATCH/models/hf"

module load python/3.11 2>/dev/null || module load python 2>/dev/null || true  # cluster-specific
PY=$(command -v python3.11 || command -v python3)
echo "python: $PY ($($PY --version))"
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install torch --index-url "https://download.pytorch.org/whl/${CUDA_WHL:-cu121}"
pip install diffusers transformers accelerate safetensors sentencepiece protobuf pillow \
    pillow-heif "huggingface_hub[cli]"

export HF_HOME=$SCRATCH/models/hf
echo "free on scratch before download:"; df -h "$SCRATCH" | tail -1

FP16=(--include "*.json" "*.txt" "*fp16.safetensors")   # fp16 weights only; whole repos are huge
huggingface-cli download stable-diffusion-v1-5/stable-diffusion-v1-5 "${FP16[@]}"
huggingface-cli download stable-diffusion-v1-5/stable-diffusion-inpainting "${FP16[@]}"
huggingface-cli download stabilityai/stable-diffusion-xl-base-1.0 "${FP16[@]}"
huggingface-cli download diffusers/stable-diffusion-xl-1.0-inpainting-0.1 "${FP16[@]}"
huggingface-cli download black-forest-labs/FLUX.1-schnell --exclude "flux1-schnell.safetensors"

echo "downloaded:"; du -sh "$HF_HOME"
python - <<'EOF'
# offline check: every repo resolves from the local cache (what the compute node will do)
from huggingface_hub import snapshot_download
for r in ["stable-diffusion-v1-5/stable-diffusion-v1-5", "stable-diffusion-v1-5/stable-diffusion-inpainting",
          "stabilityai/stable-diffusion-xl-base-1.0", "diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
          "black-forest-labs/FLUX.1-schnell"]:
    print("cached:", r, snapshot_download(r, local_files_only=True))
EOF
echo "HPC setup done. Next (from the laptop): bash scripts/hpc/hpc.sh submit"
