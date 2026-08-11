# Desktop Client User Guide (Experimental)

This guide covers the experimental desktop RAG client included in `app_desktop/`.

The initial open-source release ships **source code only**. It does not ship a prebuilt executable, private Qdrant database, bundled knowledge base, or reusable API credential.

## Before you start

Create local configuration from the public template:

```bash
cd app_desktop
cp config.example.yaml config_local.yaml
```

On PowerShell:

```powershell
Copy-Item config.example.yaml config_local.yaml
```

`config_local.yaml` is ignored by Git. Keep real credentials and private service endpoints there only for controlled local development.

Install the desktop dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the client:

```bash
python app.py
```

The Gradio UI normally opens at:

```text
http://127.0.0.1:7860
```

## Safe demo data

For testing a public fork or contribution, use only synthetic or redistributable documents. For example:

```text
sample-notes/
├── renewable-energy-overview.md
├── python-testing-notes.md
└── demo-interview-participant-01.txt
```

Example questions:

- "What are the main points in the renewable-energy overview?"
- "Which testing techniques are mentioned in the Python notes?"
- "Summarize the synthetic interview findings."
- "Compare the two demo documents and cite the relevant sources."

Do not use company reports, private research material, personal chat exports, interview transcripts, or other confidential content as public examples or fixtures.

## How answers are produced

The current client:

1. creates a query embedding through the configured embedding service;
2. retrieves matching chunks from Qdrant;
3. constructs a bounded context from those chunks;
4. sends the resulting prompt to the configured text-model provider;
5. returns the generated answer with source metadata.

Because a configured hosted model may receive retrieved text in its prompt, **do not assume all processing stays on the local machine**. Review the privacy and data-handling terms of every provider you configure before using sensitive documents.

If you require fully local processing, configure and verify an all-local inference path before ingesting sensitive material.

## Sources and retrieval scores

Answers may display:

- source file or Obsidian path;
- chunk index;
- retrieval score;
- a short content preview.

These fields are intended to make it easier to trace an answer back to the stored knowledge-base material. They are not proof that a generated statement is correct; inspect the original source before making important decisions.

## Closing the client

Closing the browser tab does not necessarily stop the Python process. Stop the running process in the terminal or use the normal process/application controls for your operating system.

## Packaging

The repository still contains an internal/experimental PyInstaller path. It can bundle local configuration and a Qdrant knowledge-base snapshot, so it is **not approved as a generic public distribution workflow** in the initial source release.

Do not redistribute a packaged build unless you have independently verified that:

- no API credential is embedded;
- every bundled document/vector payload is authorized for redistribution;
- generated metadata and source paths reveal no private information;
- the executable was built from the audited release commit.

See [`README.md`](README.md) and the repository root [`SECURITY.md`](../SECURITY.md) for the current release boundary.

## Troubleshooting

If the client cannot start or return an answer, check in this order:

1. `config_local.yaml` exists and matches `config.example.yaml`;
2. the configured Qdrant database/endpoint is available;
3. the embedding service is available and compatible with the stored vectors;
4. any configured hosted provider credential is available locally;
5. the terminal output for the original error.

For reproducible bug reports, use synthetic data and remove credentials, private paths, document text, and provider secrets before posting logs or screenshots.
