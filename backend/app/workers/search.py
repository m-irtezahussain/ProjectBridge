import asyncio
import logging
import signal
import socket
from contextlib import suppress

from app.config import get_settings
from app.db import create_database
from app.deps import get_search_indexing_manager
from app.repositories.search import SearchRepository

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    engine, session_factory = create_database(settings.database_url)
    manager = get_search_indexing_manager()
    repository = SearchRepository()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for event in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(event, stop.set)
    worker_base = socket.gethostname()

    async def consume(slot: int) -> None:
        worker_id = f"{worker_base}:{slot}"
        while not stop.is_set():
            async with session_factory() as session:
                job = await repository.claim(
                    session, worker_id, settings.rag_lease_seconds
                )
                await session.commit()
                if job is not None:
                    logger.info("Processing search index job %s", job.id)
                    await manager.process_claimed(session, job)
                    continue
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.rag_poll_seconds)
            except TimeoutError:
                pass

    tasks = [
        asyncio.create_task(consume(slot))
        for slot in range(settings.rag_worker_concurrency)
    ]
    await stop.wait()
    await asyncio.gather(*tasks)
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
