# Project structure

This repository contains source code and public configuration templates only. Keep vault contents, Qdrant data, local configuration, generated desktop artifacts, and credentials outside the tracked tree.

```
obsidian-qdrant-pipeline-oss/
├── convert.py            # Convert supported documents to Markdown
├── structure.py          # Generate structured metadata
├── obsidian_writer.py    # Write Markdown into a configured vault
├── qdrant_writer.py      # Chunk and index content in Qdrant
├── ingest.py             # Single-file and watch-mode ingestion entry point
├── migrate.py            # Existing Markdown vault migration entry point
├── llm_client.py         # Hosted-provider and local-model client helpers
├── app_desktop/          # Experimental desktop RAG source
├── scripts/              # Release safety checks
├── config.example.yaml   # Public configuration template
└── requirements.txt      # Python dependencies
```

## Data flow

1. `ingest.py` accepts a supported source document.
2. `convert.py` extracts Markdown content.
3. `structure.py` derives metadata and frontmatter.
4. `obsidian_writer.py` writes the Markdown to the vault selected by the user.
5. `qdrant_writer.py` chunks the same content and indexes it in Qdrant.

`migrate.py` is the separate path for indexing Markdown that already exists in a vault. It does not modify the source Markdown files.

## Runtime boundaries

- Copy `config.example.yaml` to ignored `config.yaml` and replace every placeholder with a location you control.
- Keep provider credentials out of files when possible. `NVIDIA_API_KEY` in the process environment takes precedence over local YAML.
- The desktop client is experimental source. Do not distribute generated desktop binaries or bundled knowledge bases unless their contents and credential handling have been separately reviewed.
