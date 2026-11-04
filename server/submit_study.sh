#!/bin/bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/environment.sh"
account="${1:?Specify the authorised scheduler account}"
gpu_type="${2:-L40S}"
[[ "${account}" =~ ^[A-Za-z0-9_-]+$ && "${gpu_type}" =~ ^[A-Za-z0-9_-]+$ ]] || exit 2
[[ -f "${REFOLD_ROOT}/runtime/ready" ]] || { echo 'Resource verification is incomplete.' >&2; exit 2; }
cd -- "${REFOLD_ROOT}"
previous=''
for entry in 'pilot pdl1 2' 'study pdl1 8' 'study pdl1 16' 'study egfr 16'; do
    read -r phase target designs <<<"${entry}"
    arguments=(--parsable --account="${account}" --partition=comp --ntasks=1 --cpus-per-task=2
        --mem=8G --time=24:00:00 --signal=B:TERM@120 --job-name="refold_${phase}"
        --kill-on-invalid-dep=yes --export="ALL,REFOLD_ACCOUNT=${account},REFOLD_GPU_TYPE=${gpu_type}"
        --output="logs/${phase}-${target}-n${designs}.private.log" --chdir="${REFOLD_ROOT}")
    if [[ -n "${previous}" ]]; then arguments+=(--dependency="afterok:${previous}"); fi
    previous="$(sbatch "${arguments[@]}" scripts/run_reference.sh "${target}" "${designs}" "${phase}")"
    printf '%s\t%s\t%s\t%s\n' "${phase}" "${target}" "${designs}" "${previous}" | tee -a runtime/study-jobs.private.tsv
done
