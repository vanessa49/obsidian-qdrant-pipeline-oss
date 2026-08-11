# Public Release Scope

The `v0.1.0` source release is intended to contain reusable ingestion/RAG code, public configuration templates, documentation, and release-safety checks only.

It explicitly excludes:

- personal or company knowledge-base contents;
- Obsidian vaults and source documents;
- interview/chat transcripts and research data;
- Qdrant runtime databases, vector snapshots, and bundled knowledge bases;
- model caches and bundled Ollama files;
- reusable API credentials or private keys;
- machine-local configuration and private network endpoints;
- generated desktop binaries built from private data.

The desktop client is included as experimental source code. A generic downloadable desktop binary is not part of the initial public source release until credential injection and bundled-data handling are hardened and validated.
