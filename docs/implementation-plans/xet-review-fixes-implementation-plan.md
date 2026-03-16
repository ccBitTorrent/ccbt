# XET Code Review Fixes — Implementation Plan

**Source**: Greptile-apps bot review (blocking I/O, double-close, SQLite contention, exception type, checkpoint compatibility)  
**Scope**: `ccbt/storage/xet_folder_manager.py`, `ccbt/executor/xet_executor.py`, `ccbt/session/xet_metadata_resolver.py`, `ccbt/session/session.py`  
**Confidence**: Review raised valid concerns; current codebase already addresses most of them. This plan confirms status and covers one optional hardening.

---

## 1. Investigation Summary

| Issue | File(s) | Current status | Action |
|-------|--------|----------------|--------|
| Blocking I/O in async methods | xet_folder_manager.py | **Fixed** | Verify only |
| Double-close of XetDeduplication | xet_folder_manager.py | **Guarded** | Verify only |
| Raw SQLite alongside XetDeduplication | xet_executor.py | **Fixed** | Verify only |
| Wrong exception type (FileNotFoundError) | xet_metadata_resolver.py | **Fixed** | Verify only |
| Set-based checkpoint in is_peer_recently_processed | session.py | **Fixed** | Verify only |
| Blocking rglob/is_file in _refresh_metadata_snapshot | xet_folder_manager.py | **Fixed** | Implemented (Phase 2) |

---

## 2. Per-Issue Analysis

### 2.1 Blocking I/O in `_build_file_metadata` and chunk reads

**Review concern**: `file_path_obj.read_bytes()` and `chunk_path.read_bytes()` run synchronously inside async methods and block the event loop.

**Current code**:

- `_build_file_metadata` (lines 757–764):
  - `exists = await asyncio.to_thread(file_path_obj.exists)`
  - `if not exists or not await asyncio.to_thread(file_path_obj.is_file): return None`
  - `file_data = await asyncio.to_thread(file_path_obj.read_bytes)`
- Chunk reads:
  - Line 620: `chunk_bytes = await asyncio.to_thread(chunk_path.read_bytes)`
  - Line 900: `return await asyncio.to_thread(chunk_path.read_bytes)`

**Conclusion**: Already fixed. No code change; add/run tests to prevent regression.

**Regression risk**: None if we only verify. If someone later inlines `read_bytes()` without `to_thread`, event loop blocking would return.

---

### 2.2 Double-close of XetDeduplication

**Review concern**: `stop()` and `__del__` both call `self.dedup.close()`, leading to double-close when normal lifecycle runs before GC.

**Current code**:

- `XetFolder.__del__` (lines 133–137): `if getattr(self, "_stopped", False): return` then `with contextlib.suppress(Exception): self.dedup.close()`.
- `XetFolder.stop()` (lines 204–212): Sets `self._stopped = True` first, then calls `self.dedup.close()`.
- `XetDeduplication.close()` (xet_deduplication.py 1018–1022): Idempotent — `if self.db is not None: self.db.close(); self.db = None`.

**Conclusion**: Double-close is avoided by (1) `__del__` skipping when `_stopped` is True, (2) idempotent `close()`. No code change; document in comments if desired.

**Regression risk**: Removing the `_stopped` check in `__del__` would re-introduce double-close; second close is still safe due to idempotence.

---

### 2.3 Concurrent SQLite access in XetExecutor._cache_info

**Review concern**: `_cache_info` used raw `sqlite3.connect(dedup_path)` alongside XetDeduplication’s connection, risking lock contention or stale reads.

**Current code** (xet_executor.py 713–726):

- Uses `async with XetDeduplication(dedup_path) as dedup`, then `dedup.get_cache_stats()` and `dedup.get_recent_chunks(limit=...)`.
- No `sqlite3.connect` in this file (grep confirms).

**Conclusion**: Already fixed; single connection path via XetDeduplication context manager. No change.

**Regression risk**: Reintroducing a raw `sqlite3.connect()` for the same DB would bring back lock/stale-read risk.

---

### 2.4 Exception type in XetMetadataResolver._resolve_link

**Review concern**: Raising `FileNotFoundError` for “no metadata for tonic link” is wrong; it’s a lookup/session failure, not a missing file.

**Current code** (xet_metadata_resolver.py 70–72):

- `if metadata_bytes is None: raise RuntimeError(msg)`.

**Conclusion**: Already fixed; correct exception type. No change.

**Regression risk**: Switching back to `FileNotFoundError` would make callers that catch `OSError`/`FileNotFoundError` for real file paths mis-handle lookup failures.

---

### 2.5 is_peer_recently_processed and set-based checkpoint

**Review concern**: When `_recently_processed_peers` is the old set-based checkpoint format, `is_peer_recently_processed` returns False for everyone because of `if not isinstance(data, dict): return False`, causing a burst of re-processing after upgrade.

**Current code** (session.py 3156–3172):

- If `data` is a dict: TTL check as usual.
- After the dict branch: comment “Legacy set-based checkpoint: treat as non-expiring entries” and `return key in data`.

**Conclusion**: Legacy set is already handled; no code change. Verify behavior with a test that loads set-based checkpoint and calls `is_peer_recently_processed`.

**Regression risk**: Removing the legacy branch would break upgraded sessions with set-based checkpoints.

---

### 2.6 Blocking rglob/is_file in _refresh_metadata_snapshot (optional hardening)

**Gap**: `_refresh_metadata_snapshot` (lines 819–826) does:

- `for file_path_obj in self.folder_path.rglob("*"):`
- `if not file_path_obj.is_file(): continue`

`rglob("*")` and `is_file()` are synchronous filesystem calls. On large trees this can block the event loop during full snapshot refresh.

**Recommendation**: Optional hardening — run the directory listing (and optionally `is_file()` checks) in a thread so the event loop is not blocked:

- Collect list of candidate paths with `await asyncio.to_thread(lambda: list(self.folder_path.rglob("*")))`.
- For each path, either keep `is_file()` on the loop (small overhead per path) or do a single threaded “list of (path, is_file)” helper and then process only files in the async loop.

**Regression risk**: Low. Moving only the listing to a thread preserves semantics; ordering/behavior of snapshot should remain the same. Test with a directory containing many files.

---

## 3. Call Sites and Implications

- **resolve()** (XetMetadataResolver): Called from session (add_xet_folder path) and xet_executor (start sync). Both handle generic `Exception`; RuntimeError propagates correctly. No caller relies on FileNotFoundError for tonic link failure.
- **is_peer_recently_processed**: Used by session/peer logic; legacy set support avoids redundant re-announces and re-processing after checkpoint upgrade.
- **XetFolder.stop() / __del__**: Normal shutdown calls `stop()`, which sets `_stopped` and closes dedup; `__del__` then no-ops. Short-lived wrappers (e.g. preview in session 5645–5654) call `dedup.close()` in `finally` and do not call `stop()`, so `__del__` can still run and close dedup once; idempotent close makes double-close safe.
- **_cache_info**: Only used via XetDeduplication; no second connection, so no lock contention from this path.

---

## 4. Regression Prevention

- **Unit tests**
  - **xet_folder_manager**: Test that `_build_file_metadata` and chunk read paths use `asyncio.to_thread` (e.g. mock or assert no synchronous read_bytes on Path in the async path). Test that a large file does not block the event loop (e.g. run a concurrent task that completes only if the loop is not blocked).
  - **XetFolder lifecycle**: Test that calling `stop()` then letting the object be collected does not call `dedup.close()` twice (e.g. mock `dedup.close` and assert call count 1), or that double close is harmless (assert no exception).
  - **session**: Test `is_peer_recently_processed` with `_recently_processed_peers` set to a set of (ip, port) tuples (legacy checkpoint); assert True for peer in set, False for peer not in set. Test `cleanup_recently_processed_peers` with legacy set (no-op, no exception).
  - **xet_metadata_resolver**: Test that when no metadata is available for a tonic link, `_resolve_link` raises `RuntimeError`, not `FileNotFoundError`.
- **Integration**: One integration test that runs XET sync with a workspace and triggers file change + snapshot refresh, to ensure no event-loop stall under load (optional; can be added later).
- **Code review / checklist**: When touching XET sync or session checkpoint code, checklist: “No synchronous file I/O in async methods without to_thread”; “No raw sqlite3.connect to dedup DB”; “Legacy set for _recently_processed_peers still supported”.

---

## 5. Implementation Steps

### Phase 1 — Verification (no behavior change)

1. **Confirm blocking I/O fixes**
   - In `ccbt/storage/xet_folder_manager.py`: Ensure `_build_file_metadata` uses `asyncio.to_thread` for `exists`, `is_file`, and `read_bytes`; ensure lines 620 and 900 use `asyncio.to_thread(chunk_path.read_bytes)`. **Status: already present.**
2. **Confirm double-close guard**
   - In `XetFolder.__del__`: Ensure `if getattr(self, "_stopped", False): return` before `dedup.close()`. In `stop()`: Ensure `_stopped = True` before `dedup.close()`. **Status: already present.**
3. **Confirm _cache_info uses single connection**
   - In `ccbt/executor/xet_executor.py`: Ensure `_cache_info` uses `async with XetDeduplication(dedup_path) as dedup` and `get_recent_chunks`; no `sqlite3.connect`. **Status: already present.**
4. **Confirm exception type**
   - In `ccbt/session/xet_metadata_resolver.py`: Ensure `_resolve_link` raises `RuntimeError` when metadata is None. **Status: already present.**
5. **Confirm legacy set handling**
   - In `ccbt/session/session.py`: Ensure `is_peer_recently_processed` has the legacy branch `return key in data` when `data` is not a dict. **Status: already present.**

### Phase 2 — Optional hardening (implemented)

6. **Offload rglob in _refresh_metadata_snapshot** — DONE
   - In `_refresh_metadata_snapshot`, directory listing and `.git`/`.xet` filtering are done inside `_list_workspace_files()` and run via `await asyncio.to_thread(_list_workspace_files)`, so the event loop is not blocked during full tree walk and `is_file()` checks.

### Phase 3 — Tests and docs

7. **Add/run regression tests**
   - Add or extend tests as in Section 4 (exception type, legacy set, double-close, and optionally blocking I/O and rglob).
8. **Update docs**
   - In architecture or XET docs, briefly note: “XET file and chunk reads run off the event loop via asyncio.to_thread”; “XetFolder closes dedup once via stop() or __del__, with idempotent close”; “Tonic link resolution raises RuntimeError when metadata is unavailable”; “Recently processed peers support legacy set checkpoints.”

---

## 6. Completion Criteria

- [x] All Phase 1 verifications documented or confirmed in this plan.
- [x] Phase 2 (rglob) implemented: `_list_workspace_files()` runs in `asyncio.to_thread`.
- [x] Tests added: `test_resolver_raises_runtime_error_for_missing_tonic_link_metadata` (test_xet_folder_sessions.py); `test_is_peer_recently_processed_legacy_set_checkpoint` (test_session_status_and_utils.py).
- [x] No new synchronous file or DB access in async XET paths without `to_thread` or the shared XetDeduplication context.
- [ ] Docs or comments updated as in Phase 3 (optional).

---

## 7. References

- `ccbt/storage/xet_folder_manager.py`: `_build_file_metadata`, `_refresh_metadata_snapshot`, `stop`, `__del__`, chunk read paths (620, 900).
- `ccbt/storage/xet_deduplication.py`: `close()`, `get_recent_chunks`.
- `ccbt/executor/xet_executor.py`: `_cache_info`, `_cache_stats`.
- `ccbt/session/xet_metadata_resolver.py`: `_resolve_link`.
- `ccbt/session/session.py`: `is_peer_recently_processed`, `get_recently_processed_peers`, `cleanup_recently_processed_peers`.
