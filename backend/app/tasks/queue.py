"""Background job dispatch.

TASK_MODE:
  rq     — production: Redis + RQ worker process(es) (`rq worker analysis`)
  thread — development: in-process worker threads (no Redis needed)
  inline — tests: run synchronously
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.core.config import get_settings

log = logging.getLogger(__name__)
_executor: ThreadPoolExecutor | None = None
_lock = threading.Lock()


def _run_safely(analysis_id: str) -> None:
    """Run one analysis; on an unexpected error retry automatically.

    Retries resume from the saved extraction/OCR checkpoints, so work already
    done on a large document is not repeated. Permanent problems (unreadable
    file, no text) are not retried.
    """
    from app.services.pipeline import mark_retrying, run_analysis

    attempts = get_settings().AUTO_RETRY_ATTEMPTS
    for attempt in range(attempts + 1):
        try:
            run_analysis(analysis_id)
            return
        except Exception:  # noqa: BLE001 — already recorded on the analysis row
            log.exception("analysis %s failed (attempt %d)", analysis_id, attempt + 1)
            if attempt < attempts:
                time.sleep(3)
                mark_retrying(analysis_id, attempt + 1)


def enqueue_analysis(analysis_id: str) -> None:
    s = get_settings()
    if s.TASK_MODE == "rq":
        from redis import Redis
        from rq import Queue, Retry

        q = Queue(s.RQ_QUEUE_NAME, connection=Redis.from_url(s.REDIS_URL))
        q.enqueue(
            "app.services.pipeline.run_analysis",
            analysis_id,
            job_timeout=s.JOB_TIMEOUT_SECONDS,
            retry=Retry(max=2, interval=[15, 60]),
            job_id=f"analysis-{analysis_id}",
        )
    elif s.TASK_MODE == "thread":
        global _executor
        with _lock:
            if _executor is None:
                # default 1: large documents are processed one at a time, the rest wait in the queue
                _executor = ThreadPoolExecutor(max_workers=max(1, s.MAX_CONCURRENT_ANALYSES), thread_name_prefix="analysis")
        _executor.submit(_run_safely, analysis_id)
    else:
        _run_safely(analysis_id)
