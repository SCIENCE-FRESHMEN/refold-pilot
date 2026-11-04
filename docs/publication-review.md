# Publication review

This release contains the standalone tools, Nextflow extension files, minimal upstream integration patches, synthetic fixtures, exported reference structures and outcomes, and supporting validation records. Documentation and generated report templates are in English.

Personal inputs, career preparation drafts, internal planning and deployment snapshots, duplicate documentation, raw runtime logs, scheduler records, model weights, container images, caches, and Git history are excluded. Earlier working documents were preserved outside the publication directory.

## Privacy and artifact checks

The final text and filename scan checks known private identifiers, local user paths, email and telephone patterns, calendar metadata, credential token formats, literal credential assignments, private-key blocks, IP addresses, and SSH destinations. It also checks for private or generated files, symlinks, and remaining CJK text. No matches were detected in the reviewed release. Public upstream attribution is retained as provenance.

Exported PDB files contain only ATOM, HETATM, TER, and END records. Their file hashes and structural identities were checked against the frozen manifests. Scientific JSON/TSV/PDB inputs and recorded comparisons retain their original bytes; human-readable study summaries were translated separately.

This is a review of the packaged files. New runtime output requires its own review; ignoring output paths in Git does not sanitize their contents.

## Verification

The standalone CPU tests, synthetic benchmark, documented Python examples, reference-pool comparison reproduction, replay checks, and English report export were verified on an isolated copy. See [release-verification.json](../evidence/release-verification.json) for counts and runtime scope. Historical GPU and integrated Nextflow results remain separately scoped evidence; they were not rerun for publication.

A final privacy scan of the packaged text files (categories such as dates, absolute paths, emails, credentials, and IP addresses) returned no matches; its scope covered the packaged files only. [SHA256SUMS](../SHA256SUMS) covers every packaged file except itself. The distributed ZIP uses neutral timestamps and owner metadata.

Git attributes preserve exact artifact bytes and keep scripts and documentation on LF line endings. Ignore rules exclude generated output, private execution state, common credentials, model weights, and containers. Upload the contents of the release directory as the repository root.
