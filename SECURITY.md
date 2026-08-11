# Security Policy

## Reporting a vulnerability

Please do not open a public issue for suspected credential exposure, private-data leakage, unsafe archive contents, or a vulnerability that could expose a user's knowledge base.

Use GitHub's private security reporting feature when available. If private reporting is unavailable, contact the maintainer through the repository owner's GitHub profile before publishing technical details.

## Data and credential boundary

This project is designed so that public source code can be separated from private runtime state.

The following must never be committed:

- API keys, access tokens, private keys, or `.env` files;
- `config.yaml` or `app_desktop/config_local.yaml` when they contain local endpoints or credentials;
- Obsidian vault contents, source documents, interview transcripts, chat exports, or inbox files;
- Qdrant database files, snapshots, bundled knowledge bases, generated embeddings, or vector payloads;
- private logs, error dumps, screenshots, or packaged desktop builds that contain private configuration or knowledge-base data.

Use `config.example.yaml` and `app_desktop/config.example.yaml` as public templates only. Keep real values in ignored local configuration.

## Desktop packaging warning

The desktop packaging workflow can bundle a local Qdrant snapshot. A packaged application may therefore contain the underlying text chunks and metadata from that knowledge base even if the source repository is clean.

Treat every generated `bundled_kb/` directory and desktop distribution as private unless the source documents and resulting vector payloads have been independently cleared for redistribution.

Never embed a reusable API credential in a distributable executable.

## Before making a fork or repository public

Run the public-release guard in this repository and perform an independent full-history secret scan. The guard checks the current tracked tree only; it does not prove that deleted material is absent from Git history.
