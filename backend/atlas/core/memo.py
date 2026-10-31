"""Keeps expensive computed responses in memory, so repeat views are instant."""

import asyncio
import functools
import time
from collections.abc import Awaitable, Callable
from typing import Any

_stores: list[dict] = []


def memo(ttl: float) -> Callable:
    """Caches an async function by its arguments. Old values are served while a refresh runs."""

    def wrap(fn: Callable[..., Awaitable[Any]]) -> Callable:
        store: dict[tuple, tuple[float, Any]] = {}
        running: dict[tuple, asyncio.Task] = {}
        _stores.append(store)

        async def refresh(key: tuple, args: tuple, kwargs: dict) -> Any:
            value = await fn(*args, **kwargs)
            store[key] = (time.monotonic() + ttl, value)
            return value

        @functools.wraps(fn)
        async def inner(*args: Any, **kwargs: Any) -> Any:
            key = (args, tuple(sorted(kwargs.items())))
            hit = store.get(key)
            if hit and hit[0] > time.monotonic():
                return hit[1]
            task = running.get(key)
            if task is None or task.done() or task.get_loop() is not asyncio.get_running_loop():
                task = running[key] = asyncio.create_task(refresh(key, args, kwargs))
            if hit:
                # Retrieve any failure so a background error is never reported as unhandled.
                task.add_done_callback(lambda t: t.cancelled() or t.exception())
                return hit[1]
            return await asyncio.shield(task)

        return inner

    return wrap


def clear_memos() -> None:
    for store in _stores:
        store.clear()
