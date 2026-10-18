"""Render worker for consent-gated longitudinal memory jobs."""
from __future__ import annotations

import logging
import signal
import threading

from app.config import get_settings
from app.database import SessionLocal, engine
from app.main import _verify_production_schema, _wait_for_db
from app.services.memory_pipeline import run_memory_worker_once

logger = logging.getLogger("psychapp.memory_worker")
POLL_SECONDS = 3


def main() -> None:
    settings = get_settings()
    if not settings.is_production:
        raise RuntimeError("The Render memory worker requires APP_ENV=production")

    _wait_for_db()
    _verify_production_schema()
    stop = threading.Event()

    def request_stop(signum, _frame) -> None:
        logger.info("Memory worker received shutdown signal=%s", signum)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    logger.info("Consent-gated longitudinal memory worker started")

    try:
        while not stop.is_set():
            db = SessionLocal()
            try:
                processed = run_memory_worker_once(db)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.error("Memory worker loop failed exception_type=%s", type(exc).__name__)
                processed = False
            finally:
                db.close()

            if not processed:
                stop.wait(POLL_SECONDS)
    finally:
        engine.dispose()
        logger.info("Consent-gated longitudinal memory worker stopped")


if __name__ == "__main__":
    main()
