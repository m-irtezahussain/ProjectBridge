# ProjectBridge

ProjectBridge is a container-first, multi-tenant project management platform with two
interfaces over one backend core:

- a Next.js web application;
- a FastAPI REST API and MCP Streamable HTTP server;
- PostgreSQL through async SQLAlchemy and Alembic.

The backend implements authentication, businesses, projects, tasks, immutable document
upload, a controlled OCR ingestion workflow, and tenant-separated semantic knowledge
search through shared managers and services.

## Start the stack

Requirements: Docker Desktop with Docker Compose v2.

```bash
docker compose up --build --wait
```

Then open:

- Web app: <http://localhost:3000>
- REST documentation: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/api/v1/health/live>
- Database readiness: <http://localhost:8000/api/v1/health/ready>
- MCP Streamable HTTP: `http://localhost:8000/mcp/`

The MCP server exposes authenticated account, project, and task tools. Read tools include
`get_current_account`, paginated/filterable project and task lookup, and assignee discovery;
write tools include project creation, updates, and archival plus task creation, assignment,
reassignment, updates, and retry-safe archival. The HTTP MCP endpoint requires a
ProjectBridge MCP OAuth access token and resolves its user, active grant, scopes, and owned
business before accepting a request. Retryable creates require an idempotency key and every MCP
write records an audit outcome. Expected MCP failures use stable JSON error codes for validation,
authorization, conflicts, and missing records. `get_service_status` uses the same `StatusService` as the REST
liveness route to demonstrate the one-core/two-interface architecture.

MCP clients can discover compact context through the static
`projectbridge://capabilities` resource and six stable resource templates for individual
projects, tasks, and documents plus their paginated collections. All resources use
`application/vnd.projectbridge.context+json;version=1`. Collection resources use signed,
opaque keyset cursors ordered by stable descending IDs, with a default page size of 50 and
maximum of 100. Cursors are bound to the authenticated business and collection, so they
cannot be reused to cross tenant, project, or resource boundaries. Resource representations
include related stable URIs but exclude internal business IDs, storage keys, raw files, and
complete OCR text.

`get_task_source_reference` returns compact provenance for source-backed tasks: document
and ingestion IDs, the immutable content hash, a bounded source excerpt, page/line
coordinates, extractor and OCR versions, and initiation/execution origins. It never returns
raw document bytes or complete OCR text and requires both `tasks:read` and `documents:read`.

Document ingestion uses a quarantine-first direct upload flow for private S3-compatible
storage such as MinIO by Silo. Configure `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`,
`S3_SECRET_ACCESS_KEY`, and `S3_BUCKET`; optional region, path-style, presign expiry, file-size,
page-count, decompression, and image-dimension limits are shown in `.env.example`. The bucket
must block public access. Browser clients need bucket CORS limited to the web app origin and
`POST`/`GET` as required. Production configuration requires HTTPS storage and explicit
credentials. Enable MinIO versioning or Object Lock when infrastructure-enforced WORM retention
is required in addition to ProjectBridge's content-addressed, never-overwrite application policy.

`initiate_document_upload` returns a five-minute presigned POST constrained to the declared
PDF, PNG, or JPEG size and MIME type. After upload, `finalize_document_upload` streams the
object through size, magic-byte, structural, page, decompression, and pixel checks; hashes the
original bytes; and promotes them to a tenant-separated `raw/sha256` key. Raw objects are never
modified or deleted by document archival. Duplicate content shares the immutable object while
retaining separate document metadata and audit history. Failed and unfinalized quarantine
objects are never downloadable.

Finalized documents can be queued with `start_document_ingestion`. A separate
`ocr-worker` service downloads the immutable raw object to a temporary file and runs
PP-OCRv6 Small outside the API event loop. The worker stores OCR text separately, extracts
only explicitly marked `TODO:`, `TASK:`, and `ACTION:` lines as candidates, and pauses at
`awaiting_confirmation`. No task is created until a caller with both `documents:write` and
`tasks:write` confirms or rejects every candidate with `confirm_task_candidates`.

OCR and document text are always untrusted data. Their contents are never interpreted as
permissions or tool instructions, and candidate extraction itself cannot call tools.
Created tasks retain both source-document and source-candidate IDs. After confirmation,
the ingestion worker creates normalized, overlapping source chunks and queues durable RAG
synchronization jobs. `get_document_ingestion` and `list_task_candidates` expose progress;
failed stages record a durable checkpoint and use bounded exponential retries. Exhausted or
partial runs can be resumed with `retry_document_ingestion` without duplicating OCR text,
candidates, tasks, or vector records.

The OCR dependencies live in the `ocr` optional dependency group and only the worker image
installs them. PaddleOCR downloads the configured official model files on first use, so the
worker needs outbound access during initial model provisioning. Set `OCR_MODEL`,
`OCR_LANGUAGE`, `OCR_WORKER_CONCURRENCY`, `OCR_LEASE_SECONDS`, and `OCR_MAX_ATTEMPTS` as
needed; their defaults are documented in `.env.example`. The worker defaults to
`linux/amd64` because PaddlePaddle does not publish a Linux ARM64 wheel; Docker Desktop can
emulate it on Apple Silicon, and `OCR_WORKER_PLATFORM` remains overridable for supported
deployment targets.

Semantic search uses a self-hosted Ollama server for embeddings and a self-hosted Chroma
server for vectors. Set the following deployment values (full subdomain URLs, without an
API suffix):

```dotenv
OLLAMA_BASE_URL=https://ollama.example.com
OLLAMA_EMBEDDING_MODEL=embeddinggemma
CHROMA_BASE_URL=https://chroma.example.com
CHROMA_TENANT=default_tenant
CHROMA_DATABASE=default_database
CHROMA_COLLECTION_PREFIX=projectbridge
CHROMA_CF_ACCESS_CLIENT_ID=your-cloudflare-access-client-id
CHROMA_CF_ACCESS_CLIENT_SECRET=your-cloudflare-access-client-secret
```

The embedding model named by `OLLAMA_EMBEDDING_MODEL` must already be pulled into Ollama.
ProjectBridge calls Ollama's native `/api/embed` batch endpoint. Every Chroma HTTP request
includes the two Cloudflare Access service-token headers. Each business receives a separate
Chroma collection, all reads and deletes also contain a business metadata filter, and
returned metadata is checked again before results are exposed.

The `rag-worker` service processes transactional indexing jobs with leases, bounded retries,
and deterministic vector IDs. Task edits and document ingestion upsert current content;
task, document, and project archival synchronizes deletion; and
`reindex_project_knowledge` rebuilds a project from PostgreSQL. MCP clients use
`search_project_knowledge` with `search:read` and receive bounded excerpts plus compact
project, document, task, chunk, OCR-text, and ingestion IDs. Returned excerpts are explicitly
marked as untrusted content and can never authorize actions or trigger tools. Reindexing
requires `search:write`.

Stop containers while retaining the PostgreSQL volume:

```bash
docker compose down
```

`docker compose down -v` also destroys local database data; use it only when a reset is
intentional.

## Configuration

Compose includes safe development defaults. Copy `.env.example` to `.env` only when
overriding them. Never store production secrets in that file or in Compose.

The frontend uses `INTERNAL_API_URL` for server-side container traffic and
`NEXT_PUBLIC_API_URL` for browser traffic. Containers address each other by Compose
service name, while browser URLs use localhost.

## Development and verification

Backend commands run inside its development image:

```bash
docker compose run --rm backend uv run pytest
docker compose run --rm backend uv run ruff check .
docker compose run --rm backend uv run mypy app
docker compose exec \
  -e PROJECTBRIDGE_MCP_ACCESS_TOKEN="$PROJECTBRIDGE_MCP_ACCESS_TOKEN" \
  backend uv run python scripts/check_mcp.py
```

Frontend commands:

```bash
docker compose run --rm frontend npm test
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run build
```

Create a new migration rather than editing an existing one:

```bash
docker compose run --rm backend uv run alembic revision --autogenerate -m "describe change"
```

Review every autogenerated migration before applying it. All future business-owned
queries must accept and enforce a business identifier in the repository layer.

## Layout

```text
backend/
  app/
    api/          # thin FastAPI routers
    core/         # interface-independent services and managers
    mcp/          # thin MCP tools/resources
    models/       # SQLAlchemy models
    repositories/ # tenant-scoped database access
    schemas/      # explicit Pydantic contracts
  migrations/
  tests/
frontend/
  src/
    app/          # Next.js App Router pages and boundaries
    components/   # reusable presentation components
    services/     # typed API clients
    types/        # frontend contracts matching backend schemas
  tests/
compose.yaml
```

See [AGENTS.md](AGENTS.md) for the architecture, security, and quality rules governing
all future work.
