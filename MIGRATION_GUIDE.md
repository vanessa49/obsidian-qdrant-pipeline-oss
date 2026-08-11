# Vault migration guide

`migrate.py` indexes Markdown already present in an Obsidian vault into a Qdrant collection. It reads the source Markdown and writes only to the configured Qdrant target.

## Before you run it

1. Create an ignored local configuration from `config.example.yaml`, or pass the required command-line options.
2. Use a disposable vault and disposable local Qdrant collection for testing.
3. Review the target collection before a production run. Migration writes vectors and payloads to Qdrant.

## Common commands

Use placeholders rather than copying a machine-specific path:

```powershell
# Inspect the planned work without writing to Qdrant.
python migrate.py --vault <VAULT_PATH> --dry-run

# Index Markdown from a vault you control.
python migrate.py --vault <VAULT_PATH>

# Exclude selected folders.
python migrate.py --vault <VAULT_PATH> --exclude 00-inbox drafts templates
```

The default local endpoints in the public configuration template are `http://localhost:6333` for Qdrant and `http://localhost:11434` for Ollama. Change them only in ignored local configuration.

## Behavior

- Existing chunks are skipped to support repeatable incremental runs.
- Missing frontmatter is completed in memory before indexed payloads are written.
- `--dry-run` reports the planned work without sending writes to Qdrant.
- Use `--exclude` for folders that should remain outside the index.

## Validate safely

For a first run, create a temporary vault containing one synthetic Markdown file and point the command at a disposable local Qdrant collection. Confirm the expected vector count and retrieval result before choosing a real vault or service.

## Troubleshooting

- If Qdrant is unavailable, confirm the configured endpoint and collection before retrying.
- If embeddings fail, confirm the configured Ollama endpoint and model.
- Preserve an existing production collection until a separate backup and rollback plan has been reviewed.
