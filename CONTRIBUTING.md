# Contributing

Contributions are welcome, especially around document conversion, privacy-preserving ingestion, metadata extraction, Qdrant integration, local-model support, and reproducible deployment.

## Development setup

1. Fork or clone the repository.
2. Create a virtual environment.
3. Install the required dependencies from `requirements.txt`.
4. Copy `config.example.yaml` to `config.yaml` and keep all real paths, endpoints, and credentials in that ignored local file.
5. Do not use private documents as fixtures in a contribution. Use synthetic or redistributable test material only.

## Before opening a pull request

Run:

```bash
python scripts/public_release_guard.py
python -m compileall -q .
```

If your change touches a provider, converter, Qdrant schema, or desktop packaging path, describe how you tested that path and whether network services were required.

## Pull-request expectations

- Keep changes focused and explain user-visible behavior.
- Add or update documentation when configuration changes.
- Do not commit generated knowledge bases, embeddings, packaged executables, logs, local configuration, or credentials.
- Prefer synthetic fixtures for tests.
- Preserve the boundary between public code and private runtime data.

## Security-sensitive changes

For changes that affect secret handling, packaged knowledge bases, remote endpoints, or privacy boundaries, read `SECURITY.md` first. Do not include real secrets or private data in an issue, commit, test, screenshot, or pull-request discussion.
