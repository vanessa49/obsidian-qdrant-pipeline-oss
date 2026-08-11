# Experimental Desktop Knowledge Assistant

This directory contains an experimental, read-only RAG client for an existing Qdrant knowledge base.

It is a consumer of the knowledge base, not part of the ingestion pipeline. The client does not intentionally write new documents or embeddings back to Qdrant.

## Current architecture

```text
question
  │
  ▼
Ollama embedding
  │
  ▼
Qdrant retrieval
  │
  ▼
context truncation
  │
  ▼
configured NVIDIA text model
  │
  ▼
answer + source metadata
```

The current desktop implementation is still experimental and should not be treated as a zero-configuration public binary.

## Local configuration

Create an ignored local configuration before running the client:

```bash
cd app_desktop
cp config.example.yaml config_local.yaml
```

On PowerShell:

```powershell
Copy-Item config.example.yaml config_local.yaml
```

Then edit `config_local.yaml` for your environment.

**Do not commit `config_local.yaml`.** It may contain private endpoints and an API credential.

The public template contains only `localhost` endpoints and an empty credential field.

## Development mode

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the UI:

```bash
python app.py
```

The Gradio interface normally opens on `http://localhost:7860`.

You can also exercise the engine directly:

```bash
python rag_engine.py "your question"
```

## Private-data boundary

The desktop tooling can work with a local Qdrant database or a bundled Qdrant snapshot. Qdrant payloads may contain source-document text, Obsidian paths, tags, metadata, and other information derived from the original knowledge base.

Therefore:

- never commit `qdrant_data/` or `bundled_kb/`;
- never publish a packaged desktop build merely because the source repository is safe to publish;
- do not use private interview transcripts, chat exports, internal reports, or personal documents as public fixtures;
- inspect any generated bundle independently before redistribution.

The root `.gitignore`, `SECURITY.md`, and public-release guard enforce part of this boundary for the tracked repository.

## Credential boundary

The current runtime reads NVIDIA provider configuration from the ignored local YAML file. Do not distribute a reusable API key inside a packaged application.

A future hardening step should move distributable builds to runtime credential injection (for example, an environment variable, OS credential store, or first-run local configuration) instead of embedding a secret in PyInstaller data.

Until that refactor is complete, treat `build.py` as a **private/internal packaging path**, not as a recommended way to distribute a public binary.

## Packaging warning

`build.py` can create `bundled_kb/` from a local Qdrant database and include that snapshot in a PyInstaller build. This is useful for controlled internal distribution, but it is intentionally excluded from Git and is not part of the open-source release artifact.

Before building, confirm that you are authorized to redistribute every source represented in the knowledge-base snapshot and that the resulting package contains no reusable credentials.

## Configuration reference

The public template defines:

- a local Qdrant primary path;
- an optional Qdrant fallback URL using `localhost` as the safe example;
- Ollama `bge-m3` embeddings;
- a configurable NVIDIA text-model fallback list;
- retrieval limits and context truncation.

See `config.example.yaml` for the exact fields expected by `rag_engine.py`.

## Known limitations

- Credential handling is not yet suitable for public binary distribution.
- Packaging can intentionally contain private knowledge-base material.
- Provider/model availability can change over time.
- The desktop path has fewer reproducible tests than the core ingestion pipeline.
- It assumes that the embedding model used for querying is compatible with the stored Qdrant vectors.

These limitations do not prevent use in a controlled local environment, but they are release blockers for a generic downloadable executable.
