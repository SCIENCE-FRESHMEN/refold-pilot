# Implementation and validation

RefoldPilot adds budgeted candidate selection and complete-outcome evaluation to an existing protein binder design pipeline. The core selector and evaluator require Python 3.10+ and no third-party Python libraries.

## Selection and identity

The explicit `hash`, `score`, and `diverse` policies operate on a complete AF2IG-filtered pool. Budgets are applied independently to each target sequence. The existing streaming `first` mode remains the default upstream behavior.

Stable IDs include chain roles, sequences, and coordinates; exact file hashes are stored separately. Structural duplicates are recorded, while the same sequence on distinct structures remains eligible. Conflicting score records, conflicting candidate identifiers, and basename collisions across different structures fail explicitly. Missing or non-finite scores are ineligible for score-dependent policies and remain missing rather than becoming zero.

Every export contains a complete candidate manifest, a selected-candidate table, and a selection audit with decision reasons and pool checksums. Replay verifies the pool and files; it rejects invalid IDs and a budget smaller than the recorded per-target selection. Zero budgets and empty pools still emit audit artifacts without scheduling selected GPU candidates.

The `diverse` policy uses normalized edit similarity, not an evolutionary or homology estimate. Its greedy diversity pass is followed by a budget-fill pass, so the threshold is a preference rather than a hard exclusion rule.

## Integration and related fixes

- Integrate selection into the shared refolding subworkflow used by `rfd` and `rfd_partial`, preserving original basenames for upstream score joins.
- Accept native AF2IG `design_id` and `pdb_path` score identifiers and reject conflicting identifier columns.
- Use explicit binder/target roles for multi-chain interface tables. Aggregate qualifying chain-pair metrics with `pairwise_min_not_union`; this does not recompute a union-interface ipSAE.
- Preserve `num_workers=0` across BoltzGen wrappers and reject negative or non-integer worker counts.
- Request full complex PAE output explicitly and place Boltz compiler caches in writable task-local directories.
- Filter identifying fields and absolute paths from final parameter metadata. Third-party console logs and runtime HTML still require a separate export review.

The stable patch targets the exact revision in [BASE_REVISION](../BASE_REVISION). The optional development scoring port has its own baseline in [patches/develop-notes.txt](../patches/develop-notes.txt). These patches are not interchangeable.

## Independent evaluation

The evaluator consumes a frozen manifest and a separate outcome TSV with `stable_id`, `quality_pass`, and optional `refold_seconds`. Labels must cover every unique candidate; failures remain rows with `quality_pass=0`. Missing duration measurements remain missing.

Label provenance is explicit: `synthetic`, `computational_proxy`, or `experimental`. Reports include precision, recall against reference positives in the complete pool, any-positive hits, exact sequence counts, pairwise edit similarity, budget shortfall, and recorded selected-task cost. Recall is undefined for pools without reference positives.

Only pre-refold features enter selection. Future refolding metrics and outcome labels belong exclusively to evaluation. A `first` baseline requires actual recorded arrival order; filename sorting is not a substitute.

## Recorded validation

| Check | Saved result | Scope |
| --- | --- | --- |
| Python regressions | 51 passed | Integrated working tree, including existing related regressions |
| Standalone Python tests | 30 available here | Selection, interface roles, and independent evaluation |
| Nextflow CPU checks | 11 passed | Process execution, replay, zero/empty pools, preview wiring, argument rejection, metadata filtering, native score schema |
| Synthetic order checks | 8,100 consistent / 8,100 | Candidate counts 8/32/128, budgets 2/4/8, seeds 0/7/42, three policies, 100 permutations each |
| Real-pool order checks | 192 consistent / 192 | Four pools, three policies, 16 permutations per policy |
| Targeted lint | Zero targeted errors recorded | Existing upstream warnings remain; whole-repository strict lint is not clean |

Records are in [evidence/](../evidence/). The publication verification record distinguishes checks run on this packaged repository from earlier integrated-tree results. Repeated input permutations test software consistency and do not add biological samples.

Historical run summaries hash the selector source with CRLF line endings. The published Python file uses LF. Re-encoding the published source as CRLF reproduces the historical hash exactly; the original run summaries retain their original hashes. Both hashes and the comparison are recorded in `evidence/release-verification.json`.

The historical server record includes 28 tests at an earlier server snapshot and 30 standalone tests locally. These are snapshots of different validation stages, rather than conflicting counts for a single run. Model outputs and cost limitations are described in the [reference study](reference-study.md).
