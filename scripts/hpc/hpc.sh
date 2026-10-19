#!/bin/bash
# Laptop-side HPC helper. Run in Git Bash from the repo root:
#   export HPC=<user>@<login-host>
#   bash scripts/hpc/hpc.sh check     # ssh, hello-world GPU job, scp round trip
#   bash scripts/hpc/hpc.sh push      # scripts + seeds + masks + prompts → $SCRATCH/claimshield
#   bash scripts/hpc/hpc.sh setup     # venv + ~57 GB of weights, on the login node
#   bash scripts/hpc/hpc.sh submit    # qsub the generation job
#   bash scripts/hpc/hpc.sh status    # queue + last log lines
#   bash scripts/hpc/hpc.sh pull      # generated images → data/generated/
# Needs key login (no password prompt): ssh-copy-id <user>@<login-host> once.
set -euo pipefail
: "${HPC:?export HPC=<user>@<login-host>}"
R='$SCRATCH/claimshield'   # single-quoted: expanded on the HPC, not here
run() { ssh -o BatchMode=yes "$HPC" "$@"; }
# scp (SFTP mode in new OpenSSH) does not expand $SCRATCH → resolve the absolute path once
abs() { echo "$(run 'echo $SCRATCH')/claimshield"; }

case "${1:-}" in
check)
    run 'hostname; echo "SCRATCH=$SCRATCH"'
    run "mkdir -p $R/logs && cd $R && echo 'hostname; nvidia-smi' | qsub -q gpu -l ngpus=1 -l walltime=00:05:00 -j oe -o logs/hello.out"
    echo "wait ~1 min, then: bash scripts/hpc/hpc.sh status"
    A=$(abs); echo roundtrip-$$ > rt.txt
    scp -q rt.txt "$HPC:$A/rt.txt" && scp -q "$HPC:$A/rt.txt" rt_back.txt
    diff rt.txt rt_back.txt && echo "scp round trip OK"
    rm -f rt.txt rt_back.txt ;;
push)
    for d in data/seeds data/masks data/prompts; do [ -d "$d" ] || { echo "missing $d (see README § Data)"; exit 1; }; done
    run "mkdir -p $R/data $R/logs"
    A=$(abs)
    scp -rq scripts "$HPC:$A/"
    scp -rq data/seeds data/masks data/prompts "$HPC:$A/data/"
    echo "pushed" ;;
setup)
    # a gated model needs a one-time `huggingface-cli login` ON the HPC (the token is never
    # passed on the command line: it would show in `ps` on a shared login node)
    run "cd $R && CUDA_WHL=${CUDA_WHL:-cu121} bash scripts/hpc/setup_hpc.sh" ;;
submit)
    run "cd $R && qsub -o logs/ scripts/hpc/generate.pbs" ;;
status)
    run 'qstat -u $USER'
    run "cd $R/logs && for f in \$(ls -t | head -2); do echo \"== \$f\"; tail -n 5 \$f; done" ;;
pull)
    mkdir -p data/generated
    A=$(abs)
    for fam in sd15 sdxl flux; do scp -rq "$HPC:$A/data/generated/$fam" data/generated/ || echo "no $fam yet"; done
    ls data/generated ;;
*)
    sed -n '2,12p' "$0"; exit 1 ;;
esac
