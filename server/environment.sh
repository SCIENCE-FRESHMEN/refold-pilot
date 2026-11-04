#!/bin/bash
set -euo pipefail
umask 077
refold_script_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${REFOLD_ROOT:-}" && "$(readlink -f -- "${REFOLD_ROOT}")" != "$(readlink -f -- "${refold_script_root}")" ]]; then
    echo 'Configured project root refers to a different project.' >&2
    exit 2
fi
refold_selected_root="${REFOLD_ROOT:-${refold_script_root}}"
if [[ -f "${refold_script_root}/runtime/project-root.private.txt" ]]; then
    IFS= read -r refold_selected_root < "${refold_script_root}/runtime/project-root.private.txt"
fi
[[ "${refold_selected_root}" == /* && -d "${refold_selected_root}" &&
   "$(readlink -f -- "${refold_selected_root}")" == "$(readlink -f -- "${refold_script_root}")" ]] || {
    echo 'Pinned project root is invalid.' >&2
    exit 2
}
export REFOLD_ROOT="${refold_selected_root}"
export NXF_HOME="${REFOLD_ROOT}/runtime/nextflow"
export NXF_APPTAINER_CACHEDIR="${REFOLD_ROOT}/containers"
export APPTAINER_CACHEDIR="${REFOLD_ROOT}/cache/apptainer"
export APPTAINER_TMPDIR="${REFOLD_ROOT}/tmp/apptainer"
export XDG_CACHE_HOME="${REFOLD_ROOT}/cache"
export UV_CACHE_DIR="${REFOLD_ROOT}/cache/uv"
export UV_PYTHON_INSTALL_DIR="${REFOLD_ROOT}/runtime/python"
export UV_PYTHON_BIN_DIR="${REFOLD_ROOT}/runtime/bin"
export CAPSULE_CACHE_DIR="${REFOLD_ROOT}/cache/capsule"
export APPTAINER_CONFIGDIR="${REFOLD_ROOT}/cache/apptainer-config"
export TMPDIR="${REFOLD_ROOT}/tmp"
export NXF_VER=24.04.3
export NXF_DISABLE_CHECK_LATEST=true
export NXF_ANSI_LOG=false
export NXF_OPTS='-Xms256m -Xmx3g'
export APPTAINER_MKSQUASHFS_PROCS=2
export PATH="${REFOLD_ROOT}/runtime/bin:${PATH}"
if [[ -f "${REFOLD_ROOT}/runtime/scheduler-profile.private.sh" ]]; then
    source "${REFOLD_ROOT}/runtime/scheduler-profile.private.sh"
fi
mkdir -p "${NXF_HOME}" "${APPTAINER_CACHEDIR}" "${APPTAINER_TMPDIR}" \
    "${REFOLD_ROOT}/runtime/bin" "${REFOLD_ROOT}/containers" "${REFOLD_ROOT}/logs"
if [[ ! -f "${REFOLD_ROOT}/runtime/project-root.private.txt" ]]; then
    printf '%s\n' "${REFOLD_ROOT}" > "${REFOLD_ROOT}/runtime/project-root.private.txt"
fi
if ! type module >/dev/null 2>&1; then
    source /etc/profile.d/modules.sh
fi
module load nextflow/24.04.3
