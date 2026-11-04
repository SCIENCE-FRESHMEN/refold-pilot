# RefoldPilot

**Make every refold count.**

Reproducible, auditable candidate selection for protein binder design.

RefoldPilot puts a clear decision layer between a pool of designed binders and the next round of expensive refolding: **which candidates get the budget, why they get it, and how much of the reference pool's proxy success survives the cut.**

Built with **Python and Nextflow**, it extends the upstream **RFdiffusion → ProteinMPNN → AF2IG → Boltz refolding** workflow with per-target budgets, three deterministic selection policies, content-based candidate identities, checksum-verified replay, and independent frozen-pool evaluation.

The ambition is simple: give every selection a reason, every result a traceable input, and every headline a supporting artifact.

## Evidence behind the headline

| Result | What was checked |
| --- | --- |
| **3 selection policies** | Seeded hash sampling, score ranking, and score-guided sequence diversity |
| **42 unique structural candidates across 4 real reference pools** | Completed reference runs covering PDL1 and EGFR, using at most one model GPU at a time |
| **8,100 / 8,100 synthetic order checks passed** | 81 configurations, each with 100 input permutations |
| **192 / 192 real-pool order checks passed** | 48 checks per frozen reference pool, plus checksum replay |
| **51 related Python regressions and 11 Nextflow CPU checks passed** | Counts recorded during development in an external integrated working tree (upstream `nf-binder-design` plus this repo's extensions); they cannot be rerun from this repository alone. The 30 standalone Python tests in [tests/bin/](tests/bin/) run directly in this repository |

Inspect the saved records in [evidence/](evidence/) and the full exported reference artifacts in [gpu-results/](gpu-results/). Order invariance concerns selection from a frozen pool; it does not establish reproducibility of model generation.

## Three ways to spend a fixed budget

Taking the first K candidates to finish makes workflow scheduling part of the selection policy. RefoldPilot's explicit policies wait for the complete AF2IG-filtered pool and apply the budget independently to each target sequence.

| Policy | Selection rule | Role |
| --- | --- | --- |
| `hash` | Rank stable content IDs by a seeded hash | Reproducible sampling baseline |
| `score` | Rank by lower AF2IG interaction PAE, then higher binder pLDDT, then stable ID | Prioritize candidates with stronger pre-refold scores |
| `diverse` | Apply score ranking with normalized binder-sequence edit-similarity preference, then fill remaining places | Balance pre-refold ranking with sequence coverage |

The diversity threshold is a preference: the budget-fill pass may admit candidates above it. The upstream streaming `first` mode remains available. Waiting for a complete pool can add latency, so that cost belongs in any performance comparison.

## Built to explain itself

- **Content-based identity.** Chain roles, sequences, and coordinates define a stable ID; a separate SHA256 records exact file bytes. Identical sequences with different structures remain distinguishable.
- **A reason for every decision.** Export the full manifest, selected table, and audit trail. Duplicate structures, missing scores, empty pools, and zero budgets receive explicit handling.
- **Replay with verification.** Recheck the unique pool and exact file checksums before replaying a selection. Mismatched inputs and budgets too small for the recorded selection fail explicitly.
- **No future labels in the selector.** Pre-refold features and refolding outcomes are separate inputs to separate stages.
- **Keep the denominator honest.** Outcome labels must cover the full unique pool. Failed runs remain failures; reports include hits, precision, reference recall, sequence diversity, budget shortfall, and recorded refolding cost.

The integration also addresses ambiguous multi-chain interface parsing, native AF2IG score identifiers, zero-worker argument forwarding, explicit full-PAE output, and task-local compiler caches. See the [implementation notes](docs/implementation.md) and [upstream integration guide](docs/docs/extra/refold-selection.md).

## Real reference study

The fixed computational proxy was **ipSAE ≥ 0.6 and target-aligned binder RMSD_all ≤ 2 Å**.

| Frozen reference pool | Unique candidates | Proxy-positive candidates | Missing reference outputs |
| --- | ---: | ---: | ---: |
| PDL1 pilot | 2 | 0 | 0 |
| PDL1 study, n=8 | 8 | 0 | 0 |
| PDL1 study, n=16 | 16 | 1 | 0 |
| EGFR study, n=16 | 16 | 0 | 0 |
| **Total** | **42** | **1** | **0** |

One result earns the spotlight: in the **16-candidate PDL1 pool**, both `score` and `diverse` retained the sole proxy-positive candidate at **K=2**. In that frozen-pool comparison, selecting **12.5% of candidates** retained all observed proxy positives in the pool.

At the same budget, `hash` found `0 / 0 / 1` positives for seeds `0 / 7 / 42`; `score` and `diverse` each found `1 / 1 / 1`. Repeated seeds for the latter policies produce the same deterministic selection, rather than independent experiments.

This is a **single-pool, single-positive observation**. Experimental binding validation and independently measured end-to-end speedup are unavailable. The 12.5% figure is a candidate count fraction, not a measured GPU-time saving. Read the [reference study](docs/reference-study.md) and [raw comparison](gpu-results/study-pdl1-n16/comparison.json) for the protocol and cost scope.

## Quick start: no GPU required

Use **Linux or WSL with Python 3.10+**. The standalone tools use only the Python standard library.

### One-command run

Run the full select → evaluate pipeline on the bundled synthetic fixtures:

```bash
python3 run_example.py
```

This selects 2 of 8 unique fixture candidates with the `score` policy, then evaluates the frozen selection across budgets 1/2/4 and seeds 0/7/42. All outputs land in `example-output/`:

```text
example-output/
├── selection/
│   ├── candidate_manifest.json
│   ├── selected_candidates.tsv
│   ├── selection_audit.json
│   └── selected/
└── evaluation.json
```

From the repository root:

```bash
bash scripts/run_cpu.sh
```

This runs 30 standalone tests, 8,100 synthetic order checks, structure-file selection, and a synthetic-label evaluation. The main outputs are:

```text
results/
├── invariance.json
├── selection/
│   ├── candidate_manifest.json
│   ├── selected_candidates.tsv
│   ├── selection_audit.json
│   └── selected/
└── synthetic-evaluation.json
```

The demo fixtures and labels validate software behavior. For another full demo run, move the previous `results/` directory aside or edit the script to use fresh output paths; output files and selection directories are protected against accidental reuse.

Try score-based selection separately:

```bash
python3 bin/select_refold_candidates.py \
  --pdb-dir fixtures/structures \
  --scores-file fixtures/scores.tsv \
  --binder-chains A --target-chains B \
  --policy score --budget 2 --seed 0 \
  --output-dir results/score-demo
```

Omit `--budget` to keep all eligible candidates. Explore the interfaces with:

```bash
python3 bin/select_refold_candidates.py --help
python3 bin/evaluate_refold_selection.py --help
```

## Re-evaluate a real frozen pool on CPU

The exported reference pools are included, so policy comparisons can be reproduced without running the models again:

```bash
python3 bin/evaluate_refold_selection.py \
  --manifest gpu-results/study-pdl1-n16/candidate_manifest.json \
  --outcomes gpu-results/study-pdl1-n16/outcomes.tsv \
  --label-kind computational_proxy \
  --budgets 2 4 8 --seeds 0 7 42 \
  --output results/pdl1-n16-comparison.json
```

Use the same frozen pool and complete outcomes when comparing policies. Separate generation runs introduce a different candidate pool and confound the comparison.

## Nextflow integration

With Java and Nextflow installed, run a real CPU process without containers or GPU inference:

```bash
NXF_VER=24.04.3 nextflow run tests/cpu_selection.nf \
  -lib lib -c configs/cpu.config \
  --pdb_dir fixtures/structures \
  --scores fixtures/scores.tsv \
  --outdir results/nf-demo --policy hash
```

This repository contains extension files and minimal integration patches. Obtain the full upstream [nf-binder-design](https://github.com/Australian-Protein-Design-Initiative/nf-binder-design) repository separately. Check out the revision in [BASE_REVISION](BASE_REVISION) in a clean upstream working tree, then apply from this repository's root:

```bash
python3 scripts/apply_integration.py --repo ../nf-binder-design
```

The helper checks the revision, working-tree state, destination conflicts, and patch applicability before copying extensions and applying the patch. The integrated `rfd` and `rfd_partial` workflows expose `--refold_selection`, `--refold_max`, `--selection_seed`, `--selection_diversity_threshold`, and `--selection_manifest`.

Full model runs require Linux, a suitable CUDA GPU, Apptainer, Nextflow, and the upstream model weights and licenses. The single-GPU reference entry point is `scripts/run_reference.sh`; setup and study design are described in the [reference study](docs/reference-study.md). Optional Slurm orchestration is documented in [server/README.txt](server/README.txt) and requires a separately prepared environment.

## Repository map

| Path | Contents |
| --- | --- |
| [bin/](bin/) | Standalone selection, evaluation, and interface metrics |
| [modules/](modules/) / [lib/](lib/) | Nextflow extension modules and parameter metadata filtering |
| [tests/](tests/) / [fixtures/](fixtures/) | Standalone tests, CPU workflow, and synthetic fixtures |
| [patches/](patches/) | Minimal upstream integration and optional development-branch scoring port |
| [scripts/](scripts/) | CPU demo, order benchmark, integration helper, and single-GPU launchers |
| [server/](server/) | Optional Slurm orchestration, recovery guards, and audited result export |
| [gpu-results/](gpu-results/) | Structures, frozen inputs, labels, comparisons, and replay evidence for four pools |
| [evidence/](evidence/) | Saved validation records and publication checks |
| [docs/](docs/) | Implementation, study design, and publication review |
| [SHA256SUMS](SHA256SUMS) | Exact-file integrity manifest for this release |

The packaged files were reviewed for publication; details are in the [publication review](docs/publication-review.md).

## Attribution and license

The foundation models and original design workflow belong to their upstream authors. RefoldPilot's contribution is candidate selection, independent evaluation, workflow fixes, and execution safeguards. This is an independent extension.

New extension files are provided under the [MIT License](LICENSE). Preserve upstream and model-specific licenses and copyright notices when using or distributing a combined source tree. See [NOTICE.txt](NOTICE.txt).
