from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable

from bot.utils import log

_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="carousel")


def run_async(fn: Callable, *args, **kwargs) -> Future:
    """Enqueue a task to run in background thread."""
    future = _executor.submit(fn, *args, **kwargs)
    log.info("task_enqueued", fn=fn.__name__)
    return future
