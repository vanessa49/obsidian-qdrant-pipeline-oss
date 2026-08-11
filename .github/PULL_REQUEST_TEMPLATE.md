## Summary

Describe the user-visible problem and the focused change in this PR.

## Changes

- 

## Validation

List the checks you ran and the environment required. Prefer synthetic or redistributable fixtures.

- [ ] `python scripts/public_release_guard.py`
- [ ] `python -m compileall -q .`
- [ ] Relevant unit/integration path exercised when applicable

## Privacy and release boundary

- [ ] No credentials, private endpoints, or machine-local configuration are included.
- [ ] No real vault contents, source documents, transcripts, Qdrant snapshots, embeddings, or private runtime artifacts are included.
- [ ] New tests/examples use synthetic or redistributable material.
- [ ] Documentation was updated if configuration or user-visible behavior changed.

## Notes for reviewers

Call out provider, converter, Qdrant schema, desktop packaging, credential-handling, or privacy-boundary changes that need extra scrutiny.
