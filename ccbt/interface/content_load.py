"""Helpers for dynamic Textual content areas (avoids DuplicateIds on tab switches)."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


def coalesce_gather_result(result: Any, default: T) -> T:
    """Return *default* when ``asyncio.gather(..., return_exceptions=True)`` failed."""
    if isinstance(result, BaseException):
        return default
    if result is None:
        return default
    return result  # type: ignore[return-value]


def clear_container_children(container: Any) -> None:
    """Remove all children from a Textual container."""
    if container is None:
        return
    try:
        container.remove_children()
    except Exception:
        for child in list(getattr(container, "children", ())):
            with contextlib.suppress(Exception):
                child.remove()


def query_child_by_id(container: Any, widget_id: str) -> Optional[Any]:
    """Return a child widget by DOM id, or None if missing."""
    if container is None:
        return None
    try:
        return container.query_one(f"#{widget_id}")
    except Exception:
        return None


def mount_or_update_static(
    container: Any,
    widget_id: str,
    message: str,
    static_cls: type[Any],
    *,
    clear_on_mount: bool = False,
) -> Any:
    """Mount a Static placeholder once, or update its message if it already exists."""
    existing = query_child_by_id(container, widget_id)
    if existing is not None:
        if hasattr(existing, "update"):
            existing.update(message)
        return existing
    if clear_on_mount:
        clear_container_children(container)
    widget = static_cls(message, id=widget_id)
    container.mount(widget)
    return widget


def remove_widgets_by_ids(container: Any, widget_ids: list[str]) -> None:
    """Remove every child matching any of the given widget ids."""
    if container is None:
        return
    for widget_id in widget_ids:
        try:
            matches = list(container.query(f"#{widget_id}"))
        except Exception:
            matches = []
        for widget in matches:
            with contextlib.suppress(Exception):
                widget.remove()


def torrents_snapshot_from_app(widget: Any) -> list[dict[str, Any]] | None:
    """Return the App ``torrents_data`` list for a mounted widget, if available."""
    app = getattr(widget, "app", None)
    if app is None:
        return None
    data = getattr(app, "torrents_data", None)
    if data is None:
        return None
    return list(data)


def schedule_widget_worker(
    widget: Any,
    coro: Any,
    *,
    group: str = "widget_refresh",
    exclusive: bool = True,
) -> None:
    """Schedule async work from a Textual ``watch_*`` handler on the widget loop.

    Textual 8 reactive watchers must be synchronous. Bare ``asyncio.create_task``
    from a watcher often never runs on the App loop; ``run_worker`` is the
    supported path (see Textual worker API).
    """
    try:
        widget.run_worker(
            coro,
            name=group,
            group=group,
            exclusive=exclusive,
            exit_on_error=False,
        )
        return
    except Exception:
        pass

    app = getattr(widget, "app", None)
    if app is not None:
        with contextlib.suppress(Exception):
            app.run_worker(
                coro,
                name=group,
                group=group,
                exclusive=exclusive,
                exit_on_error=False,
            )
            return
        with contextlib.suppress(Exception):
            if hasattr(app, "loop"):
                app.loop.create_task(coro)  # type: ignore[attr-defined]
                return

    with contextlib.suppress(Exception):
        asyncio.get_running_loop().create_task(coro)


class SyncContentLoadGuard:
    """Serialize synchronous tab/content loads on the Textual main thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def run(self, func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        with self._lock:
            return func(*args, **kwargs)
