# Pre-Commit Hook Failure and Warning Inventory

## Summary
- **Total Failures**: 3 distinct failure types
- **Total Warnings**: 0 explicit warnings (informational messages only)
- **Critical Issues**: 2 (test timeout, changelog validation)
- **Recurring Issues**: 1 (benchmark file cleanup on Windows)

---

## 1. TEST FAILURES

### 1.1 Test Timeout
- **Status**: ❌ FAILED
- **Test**: `dev\unit\session\test_session_event_handlers.py::test_on_download_complete_calls_callback`
- **Error Type**: Test execution timeout
- **Timeout Duration**: 3600 seconds (1 hour)
- **Location**: Line 4
- **Severity**: HIGH
- **Description**: Test exceeded maximum execution time limit, indicating potential deadlock, infinite loop, or resource contention
- **Impact**: Blocks pre-commit hook completion
- **Recommendation**: 
  - Investigate test for async/await issues
  - Check for missing timeouts in async operations
  - Verify proper cleanup of resources
  - Consider reducing timeout or fixing underlying issue

---

## 2. BENCHMARK FAILURES

### 2.1 bench_disk_io.py PermissionError (Windows File Lock)
- **Status**: ❌ FAILED (Recurring)
- **Hook**: `bench-smoke-disk` and `bench-smoke-all`
- **Error Type**: `PermissionError: [WinError 32]`
- **Error Message**: "The process cannot access the file because it is being used by another process"
- **Affected File Pattern**: `C:\Users\MeMyself\AppData\Local\Temp\tmp*\bench.bin`
- **Occurrence Count**: 10+ instances throughout the log
- **Location**: `tests/performance/bench_disk_io.py`, line 77 (`run_case` function)
- **Stack Trace Pattern**:
  ```
  tempfile.TemporaryDirectory().__exit__()
  → tempfile.py:950 (cleanup)
  → tempfile.py:954 (_rmtree)
  → shutil.py:790 (rmtree)
  → shutil.py:629 (_rmtree_unsafe)
  → PermissionError on os.unlink(fullname)
  ```
- **Root Cause**: File handle not properly closed before temporary directory cleanup on Windows
- **Severity**: MEDIUM (benchmark-specific, doesn't affect core functionality)
- **Impact**: 
  - Prevents `bench_disk_io.py` from completing successfully
  - Causes `bench-smoke-disk` hook to fail
  - Causes `bench-smoke-all` hook to fail when `bench_disk_io.py` is included
- **Platform**: Windows-specific issue
- **Temporary Directories Affected**:
  - `tmp2j1x6u4i` (line 20)
  - `tmpybtdguan` (line 81)
  - `tmp527ig13h` (line 244)
  - `tmpew76gy8e` (line 407)
  - `tmp8w4sc8ob` (line 608)
  - `tmpep8qdrmw` (line 771)
  - `tmpc_9qhr_8` (line 860)
  - `tmpm20itzi2` (line 1023)
  - `tmp3q0h43hm` (line 1336)
  - `tmpimtpefgk` (line 1499)
- **Recommendation**:
  - Ensure all file handles are explicitly closed before `TemporaryDirectory` context exit
  - Add explicit `await disk_io_manager.stop()` with proper cleanup
  - Consider using `asyncio.wait_for()` with timeout for cleanup operations
  - Add retry logic with exponential backoff for file deletion on Windows
  - Use `os.close()` or `file.close()` explicitly before cleanup
  - Consider using `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)` as temporary workaround (not recommended for production)

### 2.2 Successful Benchmarks (For Reference)
- **bench-smoke-hash**: ✅ PASSED
- **bench-smoke-piece**: ✅ PASSED
- **bench-smoke-loopback**: ✅ PASSED
- **bench-smoke-encryption**: ✅ PASSED
- **bench_encryption.py**: ✅ PASSED (all runs)
- **bench_hash_verify.py**: ✅ PASSED (all runs)
- **bench_loopback_throughput.py**: ✅ PASSED (all runs)
- **bench_piece_assembly.py**: ✅ PASSED (all runs)

---

## 3. PRE-COMMIT HOOK VALIDATION FAILURES

### 3.1 Changelog Format Validation
- **Status**: ❌ FAILED
- **Hook**: `validate-changelog`
- **Error Type**: Format validation error
- **Location**: `dev/CHANGELOG.md`, line 21
- **Error Message**: 
  ```
  [ERROR] Invalid changelog entry format at line 21: Entry must include author attribution: '- Description (Author1, Author2, ...)'
  Entry: - Session refactoring with controller-based architecture and dependency injection (Joseph Pollack, c...
  ```
- **Current Author**: Joseph Pollack
- **Severity**: LOW (formatting issue, easily fixable)
- **Impact**: Blocks pre-commit hook completion
- **Required Format**: `'- Description (YourName, ccBitTorrent contributors)'`
- **Current Entry**: Appears to be truncated or incomplete
- **Recommendation**:
  - Fix line 21 in `dev/CHANGELOG.md`
  - Ensure entry follows format: `'- Description (Author1, Author2, ...)'`
  - Complete the truncated entry if it was cut off
  - Example fix: `'- Session refactoring with controller-based architecture and dependency injection (Joseph Pollack, ccBitTorrent contributors)'`

---

## 4. SUCCESSFUL HOOKS (For Reference)

### 4.1 Passed Hooks
- ✅ `mkdocs-build`: Documentation build succeeded
- ✅ `check-translations`: Translation validation passed
- ✅ `validate-po`: Skipped (no files to check)
- ✅ `validate-version`: Version validation passed

---

## 5. INFORMATIONAL MESSAGES

### 5.1 Platform Detection
- **Message**: "HDD storage detected"
- **Message**: "io_uring not available, using fallback I/O"
- **Message**: "Disk I/O manager started with 2 workers"
- **Status**: INFO (not errors, expected behavior on Windows)

### 5.2 Benchmark Processing
- Multiple "INFO: Processing X changed file(s)" messages
- Multiple "INFO: Selected benchmarks" messages
- Multiple "INFO: Running benchmark" messages
- **Status**: INFO (normal operation)

---

## 6. STATISTICAL SUMMARY

### Failure Breakdown by Category
| Category | Count | Severity |
|----------|-------|----------|
| Test Timeouts | 1 | HIGH |
| Benchmark Failures | 10+ | MEDIUM |
| Validation Failures | 1 | LOW |
| **Total** | **12+** | - |

### Failure Breakdown by Hook
| Hook | Status | Failures |
|------|--------|----------|
| `bench-smoke-disk` | ❌ FAILED | 1 |
| `bench-smoke-all` | ❌ FAILED | 1 |
| `validate-changelog` | ❌ FAILED | 1 |
| Test suite | ⚠️ PARTIAL | 1 timeout |

---

## 7. PRIORITY FIX RECOMMENDATIONS

### Priority 1 (Critical - Blocks Pre-Commit)
1. **Fix changelog format** (Line 21 in `dev/CHANGELOG.md`)
   - Quick fix, low effort
   - Required format: `'- Description (Author1, Author2, ...)'`

2. **Investigate test timeout** (`test_on_download_complete_calls_callback`)
   - High priority - indicates potential deadlock or resource leak
   - Review async/await patterns
   - Add proper timeouts and cleanup

### Priority 2 (Important - Recurring Issue)
3. **Fix Windows file handle cleanup in `bench_disk_io.py`**
   - Medium priority - affects benchmark reliability
   - Ensure all file handles closed before temp directory cleanup
   - Add explicit cleanup with proper async handling
   - Consider Windows-specific workarounds

---

## 8. PLATFORM-SPECIFIC NOTES

### Windows-Specific Issues
- **File Locking**: Windows file locking behavior differs from Unix
- **Temp File Cleanup**: More aggressive file locking on Windows requires explicit handle closure
- **Recommendation**: Test file cleanup patterns specifically on Windows

---

## 9. NEXT STEPS

1. ✅ **Immediate**: Fix changelog format validation error
2. ✅ **Short-term**: Investigate and fix test timeout
3. ✅ **Medium-term**: Fix Windows file handle cleanup in disk I/O benchmark
4. ✅ **Long-term**: Add Windows-specific test coverage for file cleanup patterns

---

*Generated from precom.log analysis*

