# ProjectBridge backend

FastAPI and MCP interfaces over shared services. Run through the repository-level
Docker Compose stack, or locally with Python 3.12 and `uv`:

```bash
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

