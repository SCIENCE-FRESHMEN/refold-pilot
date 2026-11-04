# Reference study

## Design

Four finite reference runs cover two target sequences and 42 unique structural candidates. The staged acquisition consists of a two-design PDL1 pilot, an eight-design PDL1 study, and sixteen-design studies for PDL1 and EGFR. At most one model GPU is requested at a time.

Each run freezes its valid AF2IG structures and pre-refold score table, obtains complete reference outcomes, then evaluates `hash`, `score`, and `diverse` on that same pool for K=2/4/8 and seeds 0/7/42. Separate generation runs are not used as policy quality controls. The two-candidate pilot has no budget compression at these budgets.

The fixed computational proxy requires ipSAE >= 0.6 and target-aligned binder RMSD_all <= 2 angstrom. Binder and target roles are A and B in both fixed and mobile structures. Missing or failed outcomes remain `quality_pass=0` with a reason. Per-pool [protocol.json](../gpu-results/study-pdl1-n16/protocol.json) files preserve the exact settings.

Generation settings include one sequence per backbone, one ProteinMPNN relaxation cycle, three AF2IG recycles, an AF2IG filter of `plddt_binder>=0`, disabled target MSA creation/server use, disabled Foldseek, queue size one, and explicit full complex PAE output. These define this finite study rather than a general recommended design protocol.

## Completed pools

| Pool | Unique candidates | Proxy positives | Missing reference outputs |
| --- | ---: | ---: | ---: |
| pilot-pdl1-n2 | 2 | 0 | 0 |
| study-pdl1-n8 | 8 | 0 | 0 |
| study-pdl1-n16 | 16 | 1 | 0 |
| study-egfr-n16 | 16 | 0 | 0 |
| Total | 42 | 1 | 0 |

Every pool includes exported structures, content and file identities, pre-refold scores, complete outcome labels, quality metrics, resource summaries, 27 policy/budget/seed comparisons, 48 order-invariance checks, and a checksum replay audit.

## Positive-pool observation

In `study-pdl1-n16`, `score` and `diverse` retain the sole proxy-positive candidate with K=2, 4, and 8. For `hash`, the positive-hit counts for seeds 0/7/42 are 0/0/1 at each budget. Score-based policies do not use the seed, so their repeated selections are not independent evidence.

At K=2, the selected fraction is 2/16 = 12.5%. This describes candidate count and single-pool proxy retention. It does not establish binding affinity, statistical significance, general improvement across targets, or end-to-end speedup. Three of the four reference pools have no proxy positives.

## Cost and recovery accounting

Reported durations are recorded task-script wall times from the full reference run, not pure GPU kernel times. Policy costs are sums over selected tasks in that reference trace; each budget policy was not independently run on a GPU. Shared generation, reference acquisition, setup, queueing, and selected refolding costs must be distinguished. GPU peak memory was not measured.

Hardware observations cover RFdiffusion stdout only. Compatible GPU classes include A100, A40, and L40S; this does not establish common hardware across stages or a hardware performance comparison.

A path-alias cache mismatch caused a non-reference regeneration attempt. It was isolated, original frozen inputs were preserved, and path identity and frozen-generation safeguards were added. The EGFR export reports one quarantined non-reference attempt with 1,412.999 known task-script seconds. That overhead is retained separately and excluded from the frozen candidate denominator. Per-pool resource summaries preserve cached, completed, and failed task accounting.

## Running a new reference study

Prepare Linux, a suitable CUDA GPU, Java, Nextflow 24.04.3, Apptainer, and the model weights and licenses required by upstream. Apply the integration to the clean pinned upstream revision first. A planned memory budget is not a guarantee that a model fits; verify the pilot before scaling.

From this repository's root, with the patched upstream checkout alongside it:

```bash
export REFOLD_REPO=../nf-binder-design
bash scripts/run_reference.sh pdl1 2
```

After a successful pilot, run the larger references serially with `pdl1 8`, `pdl1 16`, and `egfr 16`. Inspect complete outputs, chain mapping, failures, and resource use before advancing. Optional Slurm scripts require the separately prepared layout in [server/README.txt](../server/README.txt).

Model weights, container images, raw logs, scheduler records, and runtime HTML are excluded from this repository. Review new exports separately before sharing them.
