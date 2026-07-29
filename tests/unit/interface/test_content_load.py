"""Tests for dynamic content-area loading helpers."""

from __future__ import annotations

import asyncio

from ccbt.interface.content_load import (
    SyncContentLoadGuard,
    clear_container_children,
    coalesce_gather_result,
    mount_or_update_static,
    query_child_by_id,
    torrents_snapshot_from_app,
)


class _FakeWidget:
    def __init__(self, message: str, widget_id: str | None = None, **kwargs: object) -> None:
        self.message = message
        self.id = widget_id or str(kwargs.get("id", ""))

    def update(self, message: str) -> None:
        self.message = message


class _FakeContainer:
    def __init__(self) -> None:
        self.children: list[_FakeWidget] = []

    def remove_children(self) -> None:
        self.children.clear()

    def mount(self, widget: _FakeWidget) -> None:
        self.children.append(widget)

    def query_one(self, selector: str) -> _FakeWidget:
        widget_id = selector.removeprefix("#")
        for child in self.children:
            if child.id == widget_id:
                return child
        raise LookupError(widget_id)


def test_mount_or_update_static_reuses_existing_widget() -> None:
    container = _FakeContainer()
    first = mount_or_update_static(
        container,
        "placeholder",
        "first",
        _FakeWidget,
    )
    second = mount_or_update_static(
        container,
        "placeholder",
        "second",
        _FakeWidget,
    )
    assert first is second
    assert second.message == "second"
    assert len(container.children) == 1


def test_query_child_by_id_returns_none_when_missing() -> None:
    container = _FakeContainer()
    assert query_child_by_id(container, "missing") is None


def test_clear_container_children_empties_container() -> None:
    container = _FakeContainer()
    container.mount(_FakeWidget("msg", "a"))
    clear_container_children(container)
    assert container.children == []


def test_coalesce_gather_result_returns_default_for_exceptions() -> None:
    assert coalesce_gather_result(asyncio.CancelledError(), {}) == {}
    assert coalesce_gather_result(RuntimeError("x"), []) == []


def test_coalesce_gather_result_passes_through_values() -> None:
    assert coalesce_gather_result({"a": 1}, {}) == {"a": 1}


def test_torrents_snapshot_from_app_returns_none_without_app() -> None:
    assert torrents_snapshot_from_app(object()) is None


def test_torrents_snapshot_from_app_returns_list() -> None:
    widget = type("W", (), {"app": type("A", (), {"torrents_data": [{"name": "x"}]})()})()
    assert torrents_snapshot_from_app(widget) == [{"name": "x"}]


def test_sync_content_load_guard_serializes_calls() -> None:
    guard = SyncContentLoadGuard()
    state = {"count": 0}

    def increment() -> None:
        current = state["count"]
        state["count"] = current + 1

    guard.run(increment)
    guard.run(increment)
    assert state["count"] == 2
