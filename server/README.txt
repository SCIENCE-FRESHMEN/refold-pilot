Server orchestration extension, without host, login or account values.

The deployed server project already contains source/, containers/, runtime/,
scripts/ and runs/. These files are the reviewable copies of its scripts.
They are separate from the standalone single-GPU launchers under scripts/ in
this delivery bundle.

For another prepared project, copy the files in server/ into PROJECT/scripts/.
Use the patched upstream checkout as PROJECT/source/ and the six verified
containers listed in evidence/server-containers.json as PROJECT/containers/.
Model acquisition, upstream licences and runtime verification remain required;
the runtime/ready marker must only follow successful verification.
Use Python 3.10 or newer. Also copy one exported fixed protocol, for example
gpu-results/study-pdl1-n16/protocol.json, to PROJECT/scripts/protocol.json.
The controller reads this file when exporting and evaluating a new reference.

From that prepared project, run:
    bash scripts/submit_study.sh ACCOUNT L40S
Replace ACCOUNT with the authorised scheduler account. Credentials are never
arguments to these scripts. Partition names and resource settings may need
adjustment for a different scheduler configuration.

The finite chain runs the pilot, then three reference studies. Each run
independently evaluates one frozen pool, checks chain roles, records failures,
and exports anonymised structures, tables and reports. Raw logs and scheduler
records remain private. Output under export/ is content-audited and archived
with neutral owner/time metadata under runtime/experiment-results.tar.gz.
The aggregate English report is export/study-summary.txt.
The chain requests one model GPU at a time and stops scaling on failure.

An optional private scheduler profile can select a compatible single-GPU pool.
The scoped sbatch adapter can update future GPU submissions from an already
running controller without restarting it; CPU and unrelated jobs are unchanged.
The resume guard permits checkpoint continuation after infrastructure interruption
or a controller wall-time limit, but requires investigation for model failures.
Hardware observations currently cover RFdiffusion stdout only; resource summaries
do not establish a common GPU model or an end-to-end performance comparison.

environment.sh pins the initial project path spelling in a private runtime file.
Restarting through a filesystem alias keeps that spelling for Nextflow cache
identity. A frozen run can be listed in the private scheduler profile under
frozen_generation_runs; generation cache misses then fail before allocation.
The controller checks an optional private frozen-manifest checkpoint before
and after a resumed run. Quarantined non-reference attempt traces stay private;
their recorded overhead is exported separately from reference outcomes.
