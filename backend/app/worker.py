"""Standalone Background Worker Entrypoint for Predictive DevOps Intelligence Platform.

Runs the Redis Streams consumer worker with:
- Consumer group initialization.
- Pending message recovery (auto-claim for unacknowledged messages).
- Retry policy with poison pill dead-letter routing.
- Graceful shutdown handling for SIGTERM and SIGINT.
- Database health check.
"""

import asyncio
import logging
import signal
import sys
from app.config import settings
from app.core.logging import setup_logging
from app.database import engine
from app.workers.redis_stream_worker import redis_stream_worker

setup_logging(level="DEBUG" if settings.DEBUG else "INFO")
logger = logging.getLogger("app.worker")


async def main():
    logger.info("Initializing DevOps Intelligence background worker process...")

    # Test database connectivity
    try:
        async with engine.connect():
            logger.info("Worker database connection established.")
    except Exception as e:
        logger.critical(f"Worker could not connect to database: {e}", exc_info=True)
        sys.exit(1)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_signal(sig):
        logger.warning(f"Received termination signal {sig}. Initiating graceful shutdown...")
        redis_stream_worker.stop()
        stop_event.set()

    for s in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(s, lambda sig=s: handle_signal(sig))
        except (NotImplementedError, RuntimeError):
            # Windows signal handling fallback
            pass

    worker_task = asyncio.create_task(redis_stream_worker.start())

    # Wait until shutdown requested or worker task crashes
    done, pending = await asyncio.wait(
        [worker_task, asyncio.create_task(stop_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if worker_task in done:
        exc = worker_task.exception()
        if exc:
            logger.critical(f"Worker loop terminated with unhandled exception: {exc}", exc_info=True)
            sys.exit(1)

    logger.info("Waiting for active stream messages to complete processing...")
    try:
        await asyncio.wait_for(worker_task, timeout=15.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        logger.warning("Worker shutdown timeout reached. Exiting.")

    logger.info("Worker shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
