# Backend Smoke Test Bugs

Date: 2026-06-23

## Current Status

No unresolved business-code bugs remain from this smoke-test pass.

The previously noted default rerank model issue was fixed by moving model defaults into `core.config`:

- `EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5`
- `RERANK_MODEL_NAME=Xenova/ms-marco-MiniLM-L-6-v2`

## Environment Notes

These issues were observed only inside the current Codex/Windows sandbox and are not tracked as backend bugs:

- SQLite and Chroma writes under the workspace path produced disk I/O errors, while temp-dir paths worked.
- `fastapi dev` reloader hit Windows multiprocessing named-pipe permission errors.
- FastAPI CLI output needed UTF-8 console encoding to avoid GBK emoji encoding errors.
