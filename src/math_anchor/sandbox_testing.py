from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from . import sandbox, worker_pool, worker_process
from .worker_pool import _WorkerPool


@contextmanager
def isolated_worker_pool(maximum: int = 1) -> Iterator[_WorkerPool]:
    """Install one pool consistently across the public and pool modules."""
    previous_public = sandbox._WORKER_POOL
    previous_owner = worker_pool._WORKER_POOL
    pool = _WorkerPool(maximum=maximum)
    previous_public.shutdown()
    sandbox._WORKER_POOL = pool
    worker_pool._WORKER_POOL = pool
    try:
        yield pool
    finally:
        pool.shutdown()
        sandbox._WORKER_POOL = previous_public
        worker_pool._WORKER_POOL = previous_owner


def current_worker_pool() -> _WorkerPool:
    return sandbox._WORKER_POOL


def bind_worker_pool(patcher: Any, pool: _WorkerPool) -> None:
    """Bind a pytest-style patcher to both references that own pool state."""
    patcher.setattr(sandbox, "_WORKER_POOL", pool)
    patcher.setattr(worker_pool, "_WORKER_POOL", pool)


def shutdown_worker_pool() -> None:
    sandbox._WORKER_POOL.shutdown()


def process_runtime():
    """Return the owning module for narrow worker-process fault injection."""
    return worker_process


def pool_runtime():
    """Return the owning module for narrow pool-policy fault injection."""
    return worker_pool
