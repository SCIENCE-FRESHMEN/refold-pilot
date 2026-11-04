#!/bin/bash
set -euo pipefail
source "${REFOLD_ROOT:-${SLURM_SUBMIT_DIR:?}}/scripts/environment.sh"
phase="${1:?}"
expected="${2:?}"
[[ "${phase}" =~ ^[a-z0-9_-]+$ ]] || exit 2
python3 "${REFOLD_ROOT}/scripts/analyse_reference.py" "${REFOLD_ROOT}/runs/${phase}" --expected-designs "${expected}"
