include { workerArguments } from '../modules/local/boltzgen/worker_args'

nextflow.enable.dsl = 2

params.outdir = 'cpu-selection-results'
params.selection_manifest = false
params.pdb_dir = false
params.scores = false
params.policy = 'hash'
params.budget = 2
params.worker_test = 0

include { SELECT_REFOLD_CANDIDATES } from '../modules/local/common/select_refold_candidates'

workflow {
    workerArguments(params.worker_test)
    pdbs = Channel.fromPath("${params.pdb_dir}/*.pdb").toList()
    scores = Channel.fromPath(params.scores).toList()
    SELECT_REFOLD_CANDIDATES(
        pdbs, scores, 'A', 'B', params.policy, params.budget, 0, 0.8,
        file(params.selection_manifest ?: "${projectDir}/../assets/dummy_files/empty"),
    )
    SELECT_REFOLD_CANDIDATES.out.table.view { it.text }
    def privateMeta = [author: 'private', start: 'private', slurm_account: 'private', hostname: 'private', path: '/' + ['scratch', 'workspace', 'file'].join('/'), relative: 'structures/example.pdb', value: 'retained']
    assert refold.PrivacyMetadata.clean(privateMeta) == [path: '[redacted]', relative: 'structures/example.pdb', value: 'retained']
    assert workerArguments(0) == '--num_workers 0'
    assert workerArguments(false) == ''
    assert workerArguments(null) == ''
    assert workerArguments(2) == '--num_workers 2'
}
