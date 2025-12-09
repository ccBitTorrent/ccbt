# DHT Download Start Loop Fix

## Problem Diagnosis

### Symptoms
- `_start_download_with_dht_peers` being called multiple times for the same DHT peer discovery event
- Same correlation_id and taskName in logs, indicating duplicate execution
- Download manager and piece manager being started multiple times
- Infinite loop of "Starting download with 1 DHT-discovered peers" messages

### Root Causes

1. **No Guard Against Concurrent Calls**: `_start_download_with_dht_peers` had no protection against concurrent execution
   - Multiple DHT callbacks could trigger it simultaneously
   - Race condition between checking `_download_started` and setting it

2. **Missing Lock**: No synchronization mechanism to prevent duplicate calls
   - Multiple async tasks could call `_start_download_with_dht_peers` concurrently
   - No way to detect if download start is already in progress

3. **Callback Deduplication Not Enough**: The deduplication wrapper filters peers but doesn't prevent multiple calls to `_start_download_with_dht_peers`
   - Same peer set could trigger multiple calls if callback is invoked multiple times
   - No check in callback handler to see if download start is already in progress

## Solution Implemented

### 1. Add Lock and Starting Flag

**Location**: `ccbt/session/dht_setup.py:571-598`

**Changes**:
- Added `_dht_download_start_lock` to synchronize access
- Added `_dht_download_starting` flag to track if download start is in progress
- Check `_download_started` at the start of function and return early if already started
- Check `_dht_download_starting` flag and return early if already starting
- Set flag to True before starting download to prevent concurrent calls

**Key Code**:
```python
# Prevent duplicate calls
if not hasattr(self.session, "_dht_download_start_lock"):
    self.session._dht_download_start_lock = asyncio.Lock()
    self.session._dht_download_starting = False

async with self.session._dht_download_start_lock:
    # Check if already started
    if getattr(self.session.download_manager, "_download_started", False):
        return
    
    # Check if already starting
    if getattr(self.session, "_dht_download_starting", False):
        return
    
    # Mark as starting
    self.session._dht_download_starting = True
```

### 2. Clear Flag in Finally Block

**Location**: `ccbt/session/dht_setup.py:676-680`

**Changes**:
- Added finally block to clear `_dht_download_starting` flag
- Ensures flag is cleared even if exception occurs
- Allows retry if download start fails

**Key Code**:
```python
finally:
    # Clear the starting flag even if exception occurs
    async with self.session._dht_download_start_lock:
        self.session._dht_download_starting = False
```

### 3. Check Flag in Callback Handler

**Location**: `ccbt/session/dht_setup.py:197-214`

**Changes**:
- Check `_dht_download_starting` flag before calling `_start_download_with_dht_peers`
- Skip call if download start is already in progress
- Prevents duplicate calls from DHT callback

**Key Code**:
```python
if not download_started:
    # Check if download is already starting
    is_starting = getattr(self.session, "_dht_download_starting", False)
    if not is_starting:
        await self._start_download_with_dht_peers(peer_list, metadata_fetched)
    else:
        self.logger.debug("Download start already in progress, skipping duplicate call")
```

## Impact

### Before Fix
- `_start_download_with_dht_peers` called multiple times for same peer discovery
- Download manager and piece manager started multiple times
- Infinite loop of duplicate download start attempts
- Race conditions between concurrent calls

### After Fix
- Only one call to `_start_download_with_dht_peers` per download start
- Lock prevents concurrent execution
- Flag prevents duplicate calls even if callback is triggered multiple times
- Clean error handling with finally block

## Testing Recommendations

1. **Test concurrent DHT callbacks**:
   - Trigger multiple DHT callbacks simultaneously
   - Verify only one download start occurs
   - Verify lock prevents race conditions

2. **Test duplicate peer discovery**:
   - Discover same peer multiple times
   - Verify download start is only called once
   - Verify flag prevents duplicate calls

3. **Test exception handling**:
   - Cause exception during download start
   - Verify flag is cleared in finally block
   - Verify retry is possible after exception

## Files Modified

- `ccbt/session/dht_setup.py`:
  - `_start_download_with_dht_peers()`: Added lock and starting flag to prevent duplicate calls
  - `on_dht_peers_discovered()`: Added check for `_dht_download_starting` flag before calling `_start_download_with_dht_peers`












