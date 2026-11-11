# AGENTS.md

## Project Overview

**ProjectBridge** is a container-first, multi-tenant project management platform that ships as **both a web app and an MCP server**. Both interfaces sit on top of the same backend, so any MCP-compatible chatbot can work with a business's projects and tasks exactly like the web app does. It enables users to:
- **Register and authenticate**: create a user account, register a business (organization), invite members, and manage roles and permissions.
- **Manage projects and tasks**: create, read, update, delete, assign, and change the status of projects and tasks within their business.
- **Connect a chatbot via MCP**: the chatbot fetches project context, receives a document or image from the user, runs OCR on it, then calls MCP again to create or update tasks and store the results.
- **Keep the original source**: every uploaded file is stored raw and unmodified, alongside the extracted OCR text and structured data.
- **Search project knowledge with RAG**: project data and extracted document text are indexed so chatbots and the app can retrieve relevant context by semantic search.

Core flow: `chatbot -> MCP (authenticated, get project context) -> OCR -> MCP (create/update tasks + store raw file + store extracted text) -> RAG index`.

---

## Code Style & Architecture

### Backend (Python)
- **One Core, Two Interfaces**:
  - The web app (REST API) and the MCP server are **thin interface layers over the same managers and services**. Business rules, permission checks, and validation live in the shared core and are never duplicated per interface.
  - If a rule is needed by both the API and an MCP tool, it belongs in a manager or service, not in a router or tool.
- **Layered Architecture**:
  - **MCP Tools / Resources (`mcp/`)**: Keep tool definitions thin. They validate input, resolve the authenticated user and business, call a manager, and return a typed result.
  - **Routers (`routers/`)**: Clean, dedicated `APIRouter` files separated by domain (auth, businesses, members, projects, tasks, documents, search).
  - **Managers**: Orchestrate complex flows such as business registration, member invitations, and the document ingestion pipeline (store raw -> OCR -> extract -> create/update tasks -> index), including lifecycle handling and coordination across components.
  - **Services**: Encapsulate concrete logic (authentication, token handling, permissions, OCR, raw file storage, chunking, embeddings, vector DB interactions, LLM calls).
  - **Repositories / Models**: Keep database access isolated from services and managers.
- **Multi-Tenancy**:
  - Every business-owned record (projects, tasks, documents, collections, vector entries, stored files) carries a business identifier, and **every query must be scoped to the caller's business**.
  - Enforce tenant scoping in the repository layer, not only in routers or tools, so a missed check cannot leak data across businesses.
  - Keep RAG indexes separated per business so retrieval can never return another tenant's content.
- **Authentication & Authorization**:
  - Hash passwords with a modern, slow algorithm (argon2 or bcrypt). Never store or log plaintext passwords.
  - Use short-lived access tokens and a secure refresh strategy. Validate token signature, expiry, and audience on every request.
  - Use role-based access control (e.g. owner, admin, member, viewer). Check permissions in managers/services for every action, on both the API and MCP paths.
  - MCP clients authenticate with scoped, revocable credentials bound to a specific user and business. A token must grant only the scopes it needs (e.g. read-only vs. write).
  - Business registration, invitations, and password resets must use single-use, expiring tokens and must not reveal whether an email or business already exists.
- **Tool Design**:
  - Each MCP tool does one clear thing and has a precise name, description, and typed parameters, because the calling chatbot relies on them to choose the right tool.
  - Tools must be **idempotent where possible**. A retried call must not create duplicate tasks or duplicate files.
  - Tool responses must be compact and structured. Return IDs and the fields the chatbot needs, not entire database rows or large raw text blobs.
- **Schemas & Responses**:
  - Always define explicit Pydantic schemas for requests, responses, tool inputs and outputs, and internal models.
  - Ensure every endpoint and tool returns strongly-typed, well-structured responses with appropriate status codes or structured error objects.
- **Python Standards**:
  - Use type hints everywhere and keep the code mypy-clean.
  - Use `async`/`await` consistently for I/O-bound work. Never block the event loop with CPU-heavy OCR; offload it to a worker or thread pool.
  - Follow PEP 8, and format and lint with the tools already configured in the repo.
- **Data Integrity**:
  - The original uploaded file is the source of truth. **Never modify or overwrite raw files.** Store them immutably (e.g. content-hash-based naming, namespaced per business) and keep OCR output and extracted data as separate, linked records.
  - Every task and extracted record links back to its source document so users can trace where it came from.
  - Prefer soft deletes for projects, tasks, and documents, and record an audit trail (who, what, when, via app or MCP) for create, update, delete, and permission changes.
- **Security Best Practices**:
  - Keep security at the forefront at all times.
  - **Treat OCR output and document text as untrusted data, never as instructions.** Documents may contain prompt-injection text. Extracted content must never trigger tool calls, change permissions, or alter behavior on its own.
  - Validate and sanitize all user input, tool arguments, and uploaded file contents: check MIME type and magic bytes, enforce size and page-count limits, and prevent directory traversal, file bombs, decompression bombs, and shell injection.
  - Never pass user-supplied filenames or paths to the filesystem or subprocesses (including OCR binaries) without sanitization.
  - Apply rate limiting on login, registration, password reset, and MCP endpoints to limit brute-force and abuse.
  - Never log or expose sensitive credentials, tokens, environment secrets, or full document contents.
  - Ensure proper error handling that prevents leaking stack traces or internal implementation details through API responses or tool results.

### Frontend (Next.js & TypeScript)
- **Layered Architecture**:
  - **App Router & Pages (`src/app/`)**: Keep page components and route layouts thin, focusing on page-level composition.
  - **Managers & Hooks**: Use dedicated custom hooks and manager/context providers for auth state, business context, and other complex client-side flows.
  - **Services & API Clients**: Encapsulate all API calls (auth, business registration, projects, tasks, documents, search) into dedicated typed service functions.
  - **Components**: Build modular, reusable components separated into UI/presentational and feature-specific container components.
- **Types & Schemas**:
  - Strictly type all models, props, and API payloads with TypeScript types matching the backend schemas. Avoid `any`.
- **Security Best Practices**:
  - Never expose secrets or server-only credentials in client code; restrict client env vars to `NEXT_PUBLIC_` where intended.
  - Store auth tokens safely (prefer httpOnly secure cookies over localStorage) and never render or log them.
  - Treat the UI as untrusted for authorization: hiding a button is not access control, and the backend must enforce every permission.
  - Sanitize all rendered user, OCR, and LLM content against XSS (especially Markdown and document previews).
  - Validate and restrict client-side file uploads (MIME type, size limits) before sending them to the backend.

---

## Testing & Quality

- **Behavior Changes**: Add or update automated tests for every behavior change or new feature (backend and frontend).
- **Verification**: Always run the relevant test suites (`pytest`, frontend tests), linters (`ruff` or the configured linter, `npm run lint`), and type checks (`mypy`) before declaring any task done.
- **Coverage**: Include unit and integration tests covering edge cases, invalid inputs, and failure scenarios, in particular:
  - **Tenant isolation**: a user from business A must never read, modify, or search business B's data, through either the API or MCP.
  - **Permissions**: each role can do only what it should, and expired, revoked, or under-scoped tokens are rejected.
  - **Auth flows**: registration, login, refresh, invitation, and password reset, including reuse of single-use tokens.
  - **MCP tool contracts**: valid input, invalid input, unauthorized access, and duplicate or retried calls.
  - **Ingestion pipeline**: end to end, including a failed OCR step and a partially completed run.
  - **Hostile input**: malformed, oversized, empty, and malicious files, plus prompt-injection text inside documents.
- **Test Isolation**: Mock external services (OCR engines, LLM calls, embedding providers). Tests must not require network access or real API keys.

---

## Workflow Rules

- **Minimal Diffs**: Make the smallest change that completely solves the task; do not refactor unrelated code.
- **Dependencies**: Do not add new external libraries or dependencies without explicit user permission.
- **Protected Files**: Never edit files in `/generated` or commit secrets / `.env` files.
- **Migrations**: Never edit an existing database migration. Add a new one.
- **Clarification**: If requirements are unclear, ask one clarifying question before beginning implementation.

---

## Communication

- **Concise Summaries**: Summarize what you changed and why in a few concise lines.
- **Transparency**: Clearly flag anything you were unsure about, assumptions made, or anything that could not be fully tested.