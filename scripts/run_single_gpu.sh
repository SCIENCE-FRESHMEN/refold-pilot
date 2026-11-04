#!/bin/bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
default_repo="${script_dir}/../nf-binder-design"
[[ -d "${default_repo}" ]] || default_repo="${script_dir}/../../nf-binder-design"
repo_dir="${REFOLD_REPO:-${default_repo}}"
repo_dir="$(cd -- "${repo_dir}" && pwd)"
target="${1:-pdl1}"
designs="${2:-2}"
policy="${3:-first}"
budget="${4:-2}"
for value in "${designs}" "${budget}"; do
    [[ "${value}" =~ ^[1-9][0-9]*$ ]] || { echo 'Counts must be positive integers.' >&2; exit 2; }
done
case "${policy}" in first|hash|score|diverse) ;; *) echo 'Unknown selection policy.' >&2; exit 2 ;; esac
case "${target}" in
    pdl1) input_pdb="${repo_dir}/examples/pdl1-rfd/input/PDL1.pdb"; contigs='[A18-132/0 65-120]'; hotspot='A56' ;;
    egfr) input_pdb="${repo_dir}/examples/egfr-rfd-hypermpnn/input/6aru.pdb"; contigs='[A310-481/0 65-120]'; hotspot='A412' ;;
    *) echo 'Target must be pdl1 or egfr.' >&2; exit 2 ;;
esac
for dependency in nvidia-smi apptainer nextflow; do
    command -v "${dependency}" >/dev/null 2>&1 || { echo "Missing prerequisite: ${dependency}" >&2; exit 2; }
done
nvidia-smi -L
[[ -f "${input_pdb}" ]] || { echo 'Input structure is missing.' >&2; exit 2; }
output="${REFOLD_OUTPUT:-${script_dir}/runs/${target}-${policy}-n${designs}-k${budget}}"
mkdir -p "${output}"
output="$(cd -- "${output}" && pwd)"
selection_args=()
if [[ "${policy}" != first ]]; then
    selection_args=(--refold_selection "${policy}" --refold_max "${budget}" --selection_seed 0)
fi
cd -- "${output}"
export NXF_VER=24.04.3
nextflow run "${repo_dir}/main.nf" -c "${script_dir}/single-gpu.config" -profile local \
    --method rfd --input_pdb "${input_pdb}" --outdir "${output}/results" \
    --design_name "${target}_experiment" --contigs "${contigs}" --hotspot_res "${hotspot}" \
    --rfd_n_designs "${designs}" --rfd_batch_size 1 --pmpnn_seqs_per_struct 1 \
    --pmpnn_relax_cycles 1 --af2ig_recycle 3 --refold_af2ig_filters 'plddt_binder>=0' \
    --refold_create_target_msa false --refold_use_msa_server false --do_foldseek false \
    --privacy_mode true "${selection_args[@]}" \
    -with-trace "${output}/trace.tsv" -with-report "${output}/execution-report.html" \
    -with-timeline "${output}/timeline.html" -resume
