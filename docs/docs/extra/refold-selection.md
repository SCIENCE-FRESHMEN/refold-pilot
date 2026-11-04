# Reproducible refold selection

The default --refold_selection first preserves streaming first-arrival selection.
The rfd and rfd_partial workflows also support hash, score and diverse. These
modes wait for the complete AF2IG-filtered pool and apply --refold_max separately
to each target sequence.

Use --selection_seed 0 for deterministic hash sampling. Score selection ranks by
increasing AF2IG interaction PAE, decreasing binder pLDDT, then stable content
identifier. Diverse selection uses this ranking plus normalised edit similarity
between binder sequences; --selection_diversity_threshold 0.8 controls the greedy
pass. A labelled budget-fill pass fills remaining places, so the threshold is a
preference rather than a hard similarity constraint.

Outputs under refold_selection/ include the full candidate manifest, selected
table and a reason for every excluded or selected input. Exact duplicate
structures are distinct from identical sequences on different structures.
Missing or non-finite scores are excluded by score-dependent policies, not
converted into zero. Hash sampling does not require scores.

Pass an earlier selection_audit.json as --selection_manifest to replay its
selection. The unique candidate pool and exact file checksums must match, and a
smaller requested budget cannot silently truncate a replay.

The selector uses only pre-refold data. Evaluation labels and future folding
metrics must remain outside its inputs. Waiting for the whole pool can increase
latency: report this cost, shared generation cost and reference-data acquisition
separately from selected-candidate refolding.

The standalone entry point is bin/select_refold_candidates.py --help.
It needs only the Python standard library. The integrated mode requires the
usual runtime and a Python interpreter compatible with that script.
For offline experiments, pass one frozen AF2IG score table as --scores-file.
The score reader accepts description, id, or the native filtered AF2IG design_id
and pdb_path columns. Multiple identifier columns must refer to the same candidate.
Use a fresh output directory outside the input structure directory.

Boltz complex and binder-monomer tasks use task-local Triton and cuEquivariance
cache directories so compiler caches do not require a writable container home.

bin/evaluate_refold_selection.py reads that manifest and a separate TSV with
stable_id, quality_pass (0 or 1) and optional refold_seconds. Outcomes must cover
the entire unique pool; failed model runs remain rows with quality_pass 0.
--label-kind distinguishes synthetic labels, computational proxies and
experimental measurements. Computational proxy success is not binding affinity.
It reports per-target precision, recall against the complete reference pool,
exact sequence diversity, edit similarity, budget shortfall and recorded cost.
The candidate refold fraction excludes generation and reference acquisition.
Compare policies on the same frozen pool, rather than independent pipeline runs.

## Interface metrics

Complex refolding explicitly requests full PAE output so interface scoring does
not depend on the prediction command's default output flags.

bin/parse_boltz_confidence.py rejects multiple min rows without chain roles.
Use --binder-chains C --target-chains A B for a three-chain complex. Only
binder-target pairs are considered. Multiple qualifying pairs are conservatively
aggregated per metric, labelled pairwise_min_not_union; this is not a
recomputed union-interface ipSAE. Missing metrics remain missing.

--require-interface fails on an absent interface. Without that flag or explicit
roles, a table without chain pairs remains valid for a monomer.

## Workers and privacy

BoltzGen wrappers preserve --num_workers 0 and reject negative/non-integer
worker counts. Unset/false retains the upstream default.

--privacy_mode true removes identifying fields, external references, absolute
paths and calendar dates from the final parameter metadata. It does not sanitise
third-party model console logs or runtime-generated HTML. Share only an audited
export, not raw work directories, source inputs, Git history or caches.

CPU checks:

    python tests/bin/test_refold_selection.py

The tests/cpu_selection.nf integration workflow executes the real selection
process without GPU inference or containers.
