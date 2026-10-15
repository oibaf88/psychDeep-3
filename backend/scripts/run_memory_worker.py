"""Run the asynchronous longitudinal-memory queue.

Examples:
  python scripts/run_memory_worker.py --once
  python scripts/run_memory_worker.py --poll-interval 5

Deploy this as a separate worker process, not as a second API worker. The API
remains usable if the memory worker or its selected model is unavailable.
"""
from __future__ import annotations

import argparse
import logging
import time

from app.database import SessionLocal
from app.services.memory_pipeline import run_memory_worker_once


def main() -> int:
    parser = argparse.ArgumentParser(description="PsychDeep incremental memory worker")
    parser.add_argument("--once", action="store_true", help="process at most one queued job then exit")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="seconds between empty-queue polls")
    parser.add_argument("--max-idle-seconds", type=float, default=0.0, help="exit after this much continuous idle time; 0 means no limit")
    args = parser.parse_args()
    poll_interval = max(1.0, min(float(args.poll_interval), 60.0))
    max_idle = max(0.0, float(args.max_idle_seconds))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    idle_since = time.monotonic()

    while True:
        db = SessionLocal()
        try:
            worked = run_memory_worker_once(db)
        finally:
            db.close()

        if args.once:
            return 0
        if worked:
            idle_since = time.monotonic()
            continue
        if max_idle and time.monotonic() - idle_since >= max_idle:
            return 0
        time.sleep(poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
