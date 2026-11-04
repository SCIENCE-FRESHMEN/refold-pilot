#!/bin/bash
set -euo pipefail
source "${REFOLD_ROOT:-${SLURM_SUBMIT_DIR:?}}/scripts/environment.sh"
[[ -n "${SLURM_JOB_ID:-}" ]] || { echo 'Run the controller as a CPU batch job.' >&2; exit 2; }
[[ -f "${REFOLD_ROOT}/runtime/ready" ]] || { echo 'Resources are not ready.' >&2; exit 2; }
apptainer exec --cleanenv "${REFOLD_ROOT}/containers/af2.sif" test -s \
    /app/dl_binder_design/af2_initial_guess/model_weights/params/params_model_1_multimer_v3.npz
export REFOLD_ACCOUNT="${REFOLD_ACCOUNT:-${SLURM_JOB_ACCOUNT:?}}"
target="${1:-pdl1}"
designs="${2:-2}"
phase="${3:-pilot}"
[[ "${designs}" =~ ^[1-9][0-9]*$ ]] || exit 2
[[ "${phase}" =~ ^[a-z0-9_-]+$ ]] || exit 2
case "${target}" in
    pdl1) input="${REFOLD_ROOT}/source/examples/pdl1-rfd/input/PDL1.pdb"; contigs='[A18-132/0 65-120]'; hotspot='A56' ;;
    egfr) input="${REFOLD_ROOT}/source/examples/egfr-rfd-hypermpnn/input/6aru.pdb"; contigs='[A310-481/0 65-120]'; hotspot='A412' ;;
    *) exit 2 ;;
esac
output="${REFOLD_ROOT}/runs/${phase}-${target}-n${designs}"
mkdir -p "${output}"
cd -- "${output}"
exec 9>.controller.lock
flock -n 9 || { echo 'A controller already owns this run.' >&2; exit 2; }
verify_frozen_reference() {
    python3 - "${output}" <<'PY'
import hashlib, json, sys
from pathlib import Path
run = Path(sys.argv[1])
pin = run / '.frozen-reference.private.json'
if pin.is_file():
    expected = json.loads(pin.read_text())
    actual = json.loads((run / 'results/refold_selection/selection/candidate_manifest.json').read_text())
    assert expected == actual, 'Frozen candidate manifest changed'
    for item in expected['candidates']:
        path = run / 'results/rfd/af2_initial_guess/pdbs' / item['candidate']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['file_sha256'], 'Frozen AF2 structure changed'
    print('FROZEN_REFERENCE_VERIFIED', len(expected['candidates']), flush=True)
PY
}
verify_frozen_reference
python3 "${REFOLD_ROOT}/scripts/cancel_child_jobs.py" "${output}"
nf_pid=''
cleanup_controller() {
    failure_status=$?
    if [[ "${failure_status}" -ne 0 ]]; then
        [[ -z "${nf_pid}" ]] || kill -TERM "${nf_pid}" 2>/dev/null || true
        python3 "${REFOLD_ROOT}/scripts/cancel_child_jobs.py" "${output}" || true
    fi
}
trap cleanup_controller EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
if [[ -f trace.private.tsv ]]; then
    mkdir -p attempts
    attempt=1
    while [[ -e "attempts/trace-${attempt}.private.tsv" ]]; do attempt=$((attempt + 1)); done
    cp -- trace.private.tsv "attempts/trace-${attempt}.private.tsv"
fi
nextflow run "${REFOLD_ROOT}/source/main.nf" -c "${REFOLD_ROOT}/scripts/server.config" \
    --method rfd --input_pdb "${input}" --outdir "${output}/results" \
    --design_name "${target}_candidate" --contigs "${contigs}" --hotspot_res "${hotspot}" \
    --rfd_n_designs "${designs}" --rfd_batch_size 1 --rfd_model_directory_path /models --pmpnn_seqs_per_struct 1 \
    --pmpnn_relax_cycles 1 --af2ig_recycle 3 --refold_af2ig_filters 'plddt_binder>=0' \
    --refold_selection hash --refold_max "${designs}" --selection_seed 0 \
    --refold_create_target_msa false --refold_use_msa_server false --do_foldseek false \
    --privacy_mode true -with-trace trace.private.tsv -with-report report.private.html \
    -with-timeline timeline.private.html -resume &
nf_pid=$!
wait "${nf_pid}"
verify_frozen_reference
export_dir="${REFOLD_ROOT}/export/${phase}-${target}-n${designs}"
if [[ -e "${export_dir}" ]]; then
    mkdir -p "${REFOLD_ROOT}/export-archive"
    mv -- "${export_dir}" "${REFOLD_ROOT}/export-archive/${phase}-${target}-n${designs}-${SLURM_JOB_ID}"
fi
python3 "${REFOLD_ROOT}/scripts/analyse_reference.py" "${output}" --expected-designs "${designs}"
python3 - "${export_dir}/summary.json" <<'PY'
import json
import sys
from pathlib import Path
summary = json.loads(Path(sys.argv[1]).read_text())
assert summary['missing_reference_outputs'] == 0, 'Missing metrics require investigation before scaling'
PY
printf '%s\n' 'REFERENCE_RUN_COMPLETE'
