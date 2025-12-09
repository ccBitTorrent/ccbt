# Peer Discovery and Piece Selection Loop Fix

## Problem Diagnosis

### Symptoms
- Piece selector repeatedly selecting the same pieces (1244, 1241, 1206) in a loop
- Warnings: "No available peers for piece X: active_peers=1, peers_with_bitfield=1, unchoked=1"
- Peer shows `has_piece=False` for selected pieces
- Pieces transition to REQUESTED state but no actual requests are made
- Download stalls with pieces stuck in REQUESTED state

### Root Cause
The piece selector (`_select_rarest_first`) was selecting pieces based on `piece_frequency` without verifying that any peer actually has those pieces in `peer_availability`. This caused:

1. **Stale Frequency Data**: When peers disconnect, `piece_frequency` may not be properly decremented, leaving pieces with `frequency > 0` but no actual availability
2. **Race Conditions**: Frequency counter can be out of sync with `peer_availability` during peer disconnections/reconnections
3. **Selection Loop**: Selector keeps selecting the same unavailable pieces, causing infinite loop

### Example from Logs
```
INFO: Piece selector selected 3 pieces to request: [1244, 1241, 1206]
INFO: Peer 41.66.97.58:25190 for piece 1244: has_piece=False, can_request=True, choking=False
WARNING: No available peers for piece 1244: active_peers=1, peers_with_bitfield=1, unchoked=1
```

The piece was selected because `piece_frequency[1244] > 0`, but no peer actually has it.

## Solution Implemented

### 1. Early Return When No Bitfields (`_select_rarest_first`)

**Location**: `ccbt/piece/async_piece_manager.py:3889-3900`

**Changes**:
- Check if any peers have bitfields before starting piece selection
- Early return if `peers_with_bitfield=0` to prevent infinite loops
- Prevents selecting pieces when peers are connected but haven't sent bitfields yet

**Key Code**:
```python
# CRITICAL FIX: Don't select pieces if no peers have bitfields yet
if self._peer_manager and hasattr(self._peer_manager, "get_active_peers"):
    active_peers = self._peer_manager.get_active_peers()
    peers_with_bitfield = [
        p for p in active_peers
        if f"{p.peer_info.ip}:{p.peer_info.port}" in self.peer_availability
    ]
    if not peers_with_bitfield:
        # No peers have sent bitfields yet - wait for bitfields before selecting pieces
        return
```

### 2. Enhanced Piece Selection Validation (`_select_rarest_first`)

**Location**: `ccbt/piece/async_piece_manager.py:3884-3955`

**Changes**:
- Always verify piece availability in `peer_availability`, not just `piece_frequency`
- Calculate `actual_frequency` from `peer_availability` for each piece
- If `frequency > 0` but `actual_frequency == 0`, update frequency to 0 and skip piece
- If `frequency != actual_frequency`, update frequency to match reality
- Only select pieces that actually exist in at least one peer's availability

**Key Code**:
```python
# Always verify piece availability in peer_availability
actual_frequency = sum(
    1 for peer_avail in self.peer_availability.values()
    if piece_idx in peer_avail.pieces
)

if actual_frequency == 0:
    # Frequency > 0 but no peers actually have the piece
    # Update frequency to match reality and skip
    self.piece_frequency[piece_idx] = 0
    if piece_idx in self.piece_frequency:
        del self.piece_frequency[piece_idx]
    continue
elif actual_frequency != frequency:
    # Frequency doesn't match actual availability - update it
    self.piece_frequency[piece_idx] = actual_frequency
    frequency = actual_frequency
```

### 3. Request Validation (`request_piece_from_peers`)

**Location**: `ccbt/piece/async_piece_manager.py:1093-1125`

**Changes**:
- Check if peer availability is empty before requesting
- Verify that at least one peer actually has the piece before requesting
- Reset stuck pieces immediately if no peers have bitfields
- If no peers have the piece, reset frequency and skip request

**Changes**:
- Verify that at least one peer actually has the piece before requesting
- If no peers have the piece, reset frequency and skip request
- Prevents requesting pieces that were selected based on stale frequency data

**Key Code**:
```python
# Verify that at least one peer actually has this piece
actual_availability = sum(
    1 for peer_avail in self.peer_availability.values()
    if piece_index in peer_avail.pieces
)
if actual_availability == 0:
    # No peers actually have this piece - reset frequency and skip
    if piece_index in self.piece_frequency:
        del self.piece_frequency[piece_index]
    piece.state = PieceState.MISSING
    return
```

## Impact

### Before Fix
- Pieces with stale frequency data were selected repeatedly
- Download stalled with pieces stuck in REQUESTED state
- Infinite loop of selecting unavailable pieces
- No recovery mechanism for stale frequency data

### After Fix
- Pieces are only selected if at least one peer actually has them
- Frequency counter is automatically synchronized with `peer_availability`
- Stale frequency data is detected and corrected
- Download continues even after peer disconnections/reconnections

## Technical Details

### Frequency Counter Synchronization

**Normal Updates**:
- `update_peer_availability()`: Updates frequency when bitfields are received
- `update_peer_have()`: Updates frequency when HAVE messages are received
- `_remove_peer()`: Decrements frequency when peers disconnect

**Recovery Mechanism**:
- Recalculates from `peer_availability` when frequency is 0
- Verifies frequency matches actual availability before selection
- Updates frequency to match reality when mismatch detected
- Handles empty frequency counter (checkpoint restoration)

### Piece Selection Flow

1. **Before Selection**:
   - Clear stale requested pieces
   - Recalculate frequency from peer availability (if needed)
   - Reset stuck pieces

2. **During Selection**:
   - Check `piece_frequency` for each piece
   - **NEW**: Verify piece exists in `peer_availability`
   - **NEW**: Recalculate and update frequency if mismatch detected
   - Only select pieces that actually exist in peer availability

3. **Before Request**:
   - **NEW**: Verify piece exists in `peer_availability` again
   - Skip request if no peers have the piece
   - Update frequency if stale

4. **After Request**:
   - Request selected pieces from available peers
   - Update tracking to prevent duplicates

## Testing Recommendations

1. **Test frequency synchronization**:
   - Simulate peer disconnection/reconnection
   - Verify frequency is recalculated correctly
   - Verify pieces are only selected if peers have them

2. **Test stale frequency detection**:
   - Manually set `piece_frequency[piece_idx] = 5` but remove piece from all `peer_availability`
   - Verify selector detects mismatch and updates frequency
   - Verify piece is not selected

3. **Test piece selection loop**:
   - Start download with peers that don't have certain pieces
   - Verify selector doesn't get stuck selecting unavailable pieces
   - Verify download continues with available pieces

4. **Test DHT peer discovery**:
   - Start download with DHT-discovered peers
   - Verify bitfields are received before piece selection
   - Verify pieces are only selected after bitfields arrive

## Configuration

No new configuration options required. The fix is automatic and transparent.

## Related Issues

- Fixes infinite loop in piece selection when peers don't have selected pieces
- Fixes stale frequency data causing download stalls
- Improves synchronization between `piece_frequency` and `peer_availability`
- Prevents requesting pieces that no peer has

## Files Modified

- `ccbt/piece/async_piece_manager.py`:
  - `_select_rarest_first()`: Added peer availability verification
  - `request_piece_from_peers()`: Added availability check before requesting

