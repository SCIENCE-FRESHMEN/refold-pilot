process SELECT_REFOLD_CANDIDATES {
    tag "${policy}"
    publishDir "${params.outdir}/refold_selection", mode: 'copy'

    input:
    path pdb_files, stageAs: 'structures??/*'
    path score_files, stageAs: 'scores??/*'
    val binder_chain
    val target_chain
    val policy
    val budget
    val seed
    val similarity
    path replay_file, stageAs: 'selection_request.json'

    output:
    path 'selection/selected/*.pdb', emit: selected, optional: true
    path 'selection/candidate_manifest.json', emit: manifest
    path 'selection/selection_audit.json', emit: audit
    path 'selection/selected_candidates.tsv', emit: table

    script:
    if (!(policy in ['hash', 'score', 'diverse'])) {
        throw new IllegalArgumentException('Unknown candidate selection policy')
    }
    def has_budget = budget != null && !(budget instanceof Boolean && !budget)
    if (has_budget && (budget instanceof Boolean || !(budget.toString() ==~ /\d+/))) {
        throw new IllegalArgumentException('Selection budget must be a non-negative integer')
    }
    if (!(seed.toString() ==~ /-?\d+/)) {
        throw new IllegalArgumentException('Selection seed must be an integer')
    }
    if (!(similarity.toString() ==~ /(?:0(?:\.\d+)?|1(?:\.0+)?)/)) {
        throw new IllegalArgumentException('Selection similarity must be between zero and one')
    }
    def budget_arg = budget == null || (budget instanceof Boolean && !budget) ? '' : "--budget ${budget}"
    def replay_arg = params.selection_manifest ? "--replay ${replay_file}" : ''
    """
    set -euo pipefail
    python3 ${moduleDir}/../../../bin/select_refold_candidates.py \\
        --pdb-dir . --scores-dir . \\
        --binder-chains ${binder_chain} --target-chains ${target_chain} \\
        --policy ${policy} ${budget_arg} --seed ${seed} \\
        --similarity-threshold ${similarity} ${replay_arg} \\
        --output-dir selection
    """
}
