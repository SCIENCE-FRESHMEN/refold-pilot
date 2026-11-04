#!/bin/bash
set -euo pipefail
source "${REFOLD_ROOT:-${SLURM_SUBMIT_DIR:?}}/scripts/environment.sh"
previous="${1:?}"
target="${2:?}"
designs="${3:?}"
phase="${4:?}"
[[ "${previous}" =~ ^[0-9]+$ && "${designs}" =~ ^[1-9][0-9]*$ ]] || exit 2
[[ "${target}" =~ ^(pdl1|egfr)$ && "${phase}" =~ ^[a-z0-9_-]+$ ]] || exit 2
summary="${REFOLD_ROOT}/export/${phase}-${target}-n${designs}/summary.json"
if [[ -f "${summary}" ]]; then
    if python3 - "${summary}" <<'PY'
import json, sys
from pathlib import Path
summary = json.loads(Path(sys.argv[1]).read_text())
assert summary['status'] == 'reference_complete' and summary['missing_reference_outputs'] == 0
PY
    then
        printf '%s\n' 'REFERENCE_ALREADY_COMPLETE'
        exit 0
    fi
fi
export REFOLD_PREVIOUS_JOB="${previous}"
python3 - <<'PY'
import os, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(os.environ['REFOLD_ROOT']) / 'scripts'))
from resume_guard import can_resume
previous = os.environ['REFOLD_PREVIOUS_JOB']
result = subprocess.run(['sacct', '-nP', '-j', previous, '--format=JobIDRaw,State,ExitCode,ElapsedRaw,TimelimitRaw'],
                        check=True, capture_output=True, text=True, timeout=30)
row = next(line.split('|') for line in result.stdout.splitlines() if line.split('|')[0] == previous)
assert can_resume(row[1], row[2], int(row[3]), int(row[4])), 'Model or user-cancelled failures require investigation'
PY
bash "${REFOLD_ROOT}/scripts/run_reference.sh" "${target}" "${designs}" "${phase}"
