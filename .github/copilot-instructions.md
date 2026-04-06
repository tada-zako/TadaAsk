# OpenKapa Workspace Instructions

## Project Identity

- This project is an open-source AI knowledge-base assistant with a widget-first integration model.
- Core stack is FastAPI backend + Vue 3 frontend.
- Design decisions should preserve extensibility for provider, vector DB, ingestion, and admin workflows.

## Backend Rules (FastAPI)

- Keep HTTP concerns separated from business logic; handlers should stay thin and delegate core workflows to a service layer.
- Keep LLM/provider abstractions decoupled from specific vendor SDKs and avoid locking new features to one provider.
- Keep retrieval/vector-store logic behind stable interfaces exposed to upper layers.
- Use centralized configuration management; avoid hard-coded secrets, model names, and environment paths.
- Prefer async-first implementations for I/O-heavy flows.
- Current backend structure is evolving; prioritize clear boundaries and replaceable modules over fixed folder conventions.

## Frontend Rules (Vue)

- Implement UI with Vue 3 + TypeScript and keep framework-level choices consistent within each feature area.
- Keep UI modules reusable so widget and future admin console can evolve independently.
- Keep client-server contracts explicit and consistent with backend payload conventions.
- Frontend structure is expected to change for widget/admin adaptation; avoid coupling rules to fixed directory layouts.

## Roadmap Alignment

- Favor protocol-oriented abstractions that support multiple LLMs (Gemini/OpenAI/DeepSeek/Ollama).
- Keep vector DB integration replaceable (current Chroma, future Qdrant/LanceDB).
- Prefer additive changes that make crawler ingestion, GitHub repo ingestion, and owner-side MCP actions easier.
- Treat SQLite as the default metadata/config baseline unless a task explicitly changes persistence strategy.
- For MVP, prioritize grounded answers from known knowledge sources over broad web search.

## Quality Expectations

- Keep boundaries explicit: router -> service -> provider/rag/core.
- Avoid shortcut coupling that bypasses existing layers without a documented reason.
- For architecture-impacting changes, include a brief note on extensibility impact.