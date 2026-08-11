# Obsidian Qdrant Pipeline

A local-first document ingestion and retrieval pipeline for turning mixed-format files into structured Markdown for Obsidian and searchable chunks in Qdrant.

The project is intended for researchers, knowledge workers, and developers who want to keep their source material and vector database under their own control while still using local or hosted models for metadata extraction and summarization.

> **Status:** early open-source release. The core ingestion pipeline is usable, but provider integrations and the experimental desktop client are still evolving.

## What it does

```text
source documents
      │
      ▼
format conversion
      │
      ▼
optional raw-material compression
      │
      ▼
LLM metadata extraction
      │
      ├──────────────► Obsidian Markdown + YAML frontmatter
      │
      └──────────────► chunking + embeddings + Qdrant
```

Current capabilities include:

- PDF, PPTX, DOCX, HTML, Markdown, TXT, and LaTeX ingestion;
- OCR / vision-assisted handling for image-heavy material;
- detection and compression of interview transcripts, chats, and other low-density raw material;
- structured YAML frontmatter generation;
- automatic routing into an Obsidian vault;
- Qdrant chunk storage with source metadata and duplicate protection;
- migration of an existing Markdown vault into Qdrant;
- local Ollama support and optional hosted-model fallback paths;
- an experimental read-only desktop RAG client under `app_desktop/`.

## Privacy model

The repository contains **code and public configuration templates only**. Real knowledge-base data should remain local.

Do not commit:

- Obsidian vault contents or source documents;
- interview transcripts, chat exports, research material, or inbox files;
- Qdrant databases, snapshots, embeddings, or bundled knowledge bases;
- API keys, private keys, `.env` files, or machine-local configuration;
- packaged desktop applications that include private configuration or a private knowledge-base snapshot.

The repository includes `scripts/public_release_guard.py` and a GitHub Actions workflow that reject common private-runtime paths, private-network addresses, and obvious secret patterns in the **current tracked tree**. This is a safety net, not a substitute for a full Git-history secret scan.

See [SECURITY.md](SECURITY.md) for the full boundary.

## Requirements

- Python 3.8+
- Qdrant, either local or reachable from the machine running the pipeline
- Ollama for local embedding and local-model fallback paths
- optional hosted model access for configured provider paths

Typical Ollama models used by the current configuration are:

```bash
ollama pull bge-m3
ollama pull qwen2.5:7b
```

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

Some conversion backends, especially OCR-heavy ones, may download additional models on first use.

## Quick start

### 1. Create local configuration

```bash
cp config.example.yaml config.yaml
```

On Windows PowerShell:

```powershell
Copy-Item config.example.yaml config.yaml
```

Edit `config.yaml` with your own vault path and local service endpoints. `config.yaml` is ignored by Git.

The public example uses `localhost` for Qdrant and Ollama and contains no API credential.

### 2. Process one file

```bash
python ingest.py --file path/to/document.pdf --vault <VAULT_PATH>
```

### 3. Watch an inbox folder

```bash
python ingest.py --watch <INBOX_PATH> --vault <VAULT_PATH>
```

Processed files are moved into the inbox's `processed/` directory. Failures are moved into `failed/` with an error note.

### 4. Migrate an existing vault

```bash
python migrate.py --vault <VAULT_PATH> --dry-run
python migrate.py --vault <VAULT_PATH>
```

The migration path reads existing Markdown, chunks it, and writes searchable records to Qdrant without rewriting the source Markdown files.

## Output model

A generated Obsidian note uses YAML frontmatter similar to:

```yaml
---
title: Example document
type: paper
tags:
  - retrieval
  - knowledge_management
summary: Short generated summary
entities:
  - Qdrant
source_file: example.pdf
date_added: 2026-08-10
---
```

Raw material can also carry fields such as:

```yaml
tier: raw_material
compressed: true
source_length: 15000
source_type: interview
compression_ratio: 25.00%
```

Qdrant payloads retain the source file, Obsidian path, chunk index, document type, tags, text, and raw-material metadata so retrieval results can be traced back to their origin.

## Repository layout

```text
.
├── ingest.py                 # main ingestion / watch entry point
├── migrate.py                # migrate an existing Markdown vault
├── convert.py                # document conversion
├── compress.py               # raw-material detection and compression
├── structure.py              # structured metadata extraction
├── llm_client.py             # model-provider routing
├── obsidian_writer.py        # Obsidian output
├── qdrant_writer.py          # chunk / embedding / Qdrant output
├── interview_processor.py    # interview-project processing helpers
├── app_desktop/              # experimental read-only desktop RAG client
├── scripts/
│   └── public_release_guard.py
├── config.example.yaml
├── CONTRIBUTING.md
└── SECURITY.md
```

## Desktop client

`app_desktop/` is an experimental consumer of an existing Qdrant knowledge base. It is intentionally separate from the ingestion path.

Before using it, copy its public template:

```bash
cd app_desktop
cp config.example.yaml config_local.yaml
```

`config_local.yaml` is ignored by Git. Do not commit or distribute it when it contains credentials or private endpoints.

The existing packaging workflow can also bundle a local Qdrant snapshot. **A bundled snapshot may contain the underlying text chunks and metadata from your source documents.** Treat generated desktop distributions as private unless that data has been explicitly cleared for redistribution.

See [app_desktop/README.md](app_desktop/README.md) for current limitations.

## Development checks

The public-release checks intentionally avoid requiring live model or Qdrant services:

```bash
python scripts/public_release_guard.py
python -m compileall -q .
```

GitHub Actions runs the same checks on pushes and pull requests.

For provider-, OCR-, Qdrant-, and packaging-related changes, also run the relevant integration path locally and describe the environment used in the pull request.

## Contributing

Contributions are welcome. Please use synthetic or redistributable fixtures and keep private runtime data out of commits, issues, screenshots, and pull-request discussions.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Roadmap

Areas that would benefit from contributions include:

- incremental re-ingestion when a source document changes;
- more deterministic converter and metadata tests;
- Excel / CSV support;
- multilingual metadata prompts;
- configurable prompt templates;
- safer credential handling for the desktop packaging path;
- reproducible synthetic integration fixtures;
- provider lifecycle and compatibility checks.

## License

MIT. See [LICENSE](LICENSE).
