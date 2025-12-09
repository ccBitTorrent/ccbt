# Empty Bitfield Peer Disconnect Fix

## Problem Diagnosis

### Symptoms
- Download stuck in infinite loop selecting pieces 0-6 repeatedly
- Peer shows `pieces_known=0` but counted as `peers_with_bitfield=1`
- All peers choked, no pieces available
- `has_piece=False` for all pieces from peer
- No new peers being sought or connected
- Download verification fails

### Root Causes

1. **Empty Bitfield Not Detected**: Peers with empty bitfields (no pieces at all) were kept in `peer_availability` and counted as having bitfields
   - `pieces_known=0` means `len(peer_avail.pieces) == 0`
   - But peer was still in `peer_availability`, so `peers_with_bitfield=1`
   - Piece selector kept selecting pieces from peer with no pieces

2. **No Immediate Disconnect**: Peers with empty bitfields were not disconnected immediately
   - According to BitTorrent spec, if a peer has no pieces, they may skip sending bitfield
   - But if they DO send an empty bitfield, we should disconnect immediately
   - No point keeping a peer with nothing

3. **Piece Selector Not Filtering**: `_select_rarest_first` only checked if peer was in `peer_availability`, not if they had pieces
   - Filter didn't check `len(peer_avail.pieces) > 0`
   - Selected pieces from peers with empty bitfields

4. **No New Peer Discovery**: When all current peers have no pieces, no mechanism to seek new peers
   - Download gets stuck with useless peers
   - No trigger to announce to trackers or use DHT for new peers

## Solution Implemented

### 1. Filter Empty Bitfields in Piece Selector (`_select_rarest_first`)

**Location**: `ccbt/piece/async_piece_manager.py:3935-3938`

**Changes**:
- Filter `peers_with_bitfield` to only include peers that actually have pieces
- Check `len(peer_avail.pieces) > 0` before counting as having bitfield
- Prevents selecting pieces from peers with empty bitfields

**Key Code**:
```python
peers_with_bitfield = [
    p for p in active_peers
    if f"{p.peer_info.ip}:{p.peer_info.port}" in self.peer_availability
    and len(self.peer_availability[f"{p.peer_info.ip}:{p.peer_info.port}"].pieces) > 0
]
```

### 2. Immediate Disconnect for Empty Bitfields (`_handle_bitfield`)

**Location**: `ccbt/peer/async_peer_connection.py:5950-5968`

**Changes**:
- Check if `pieces_count == 0` immediately after bitfield is processed
- Disconnect peer immediately if they have no pieces at all
- Return early to prevent further processing

**Key Code**:
```python
# CRITICAL FIX: Check if peer has any pieces at all (empty bitfield)
if pieces_count == 0:
    self.logger.warning(
        "Peer %s sent empty bitfield (no pieces at all) - disconnecting immediately",
        connection.peer_info,
    )
    await self._disconnect_peer(connection)
    return
```

### 3. Filter Empty Bitfields in Request Validation (`request_piece_from_peers`)

**Location**: `ccbt/piece/async_piece_manager.py:1107-1113`

**Changes**:
- Filter out peers with empty bitfields before checking availability
- Only check `actual_availability` from peers that have pieces
- Prevents requesting pieces from peers with no pieces

**Key Code**:
```python
# CRITICAL FIX: Filter out peers with empty bitfields (no pieces at all)
peers_with_pieces = {
    k: v for k, v in self.peer_availability.items()
    if len(v.pieces) > 0
}

actual_availability = sum(
    1 for peer_avail in peers_with_pieces.values()
    if piece_index in peer_avail.pieces
)
```

### 4. Peer Evaluation Loop Enhancement (`_peer_evaluation_loop`)

**Location**: `ccbt/peer/async_peer_connection.py:7079-7093`

**Changes**:
- Check if peer has any pieces at all before checking if they have pieces we need
- Disconnect peers with empty bitfields immediately in evaluation loop
- Prevents keeping useless peers in connection pool

**Key Code**:
```python
# CRITICAL FIX: Disconnect peers with empty bitfields immediately
if pieces_count == 0:
    self.logger.info(
        "Disconnecting %s: peer has empty bitfield (no pieces at all)",
        connection.peer_info,
    )
    peers_to_recycle.append(connection)
    continue
```

## BitTorrent Protocol Compliance

According to BitTorrent specification:
- **Bitfield Message**: Should be sent immediately after handshake
- **Empty Bitfield**: If a peer has no pieces, they may skip sending bitfield message
- **Mutual Interest**: Peers should disconnect when there's no mutual interest
- **NOT_INTERESTED**: Should be sent when peer has no pieces we need

Our implementation:
- ✅ Disconnects peers with empty bitfields immediately
- ✅ Sends NOT_INTERESTED when peer has pieces but none we need
- ✅ Filters empty bitfields from piece selection
- ✅ Prevents infinite loops from selecting pieces from peers with no pieces

## Testing Recommendations

1. **Empty Bitfield Test**: Connect to peer that sends empty bitfield, verify immediate disconnect
2. **Piece Selection Test**: Verify piece selector doesn't select pieces from peers with empty bitfields
3. **Peer Evaluation Test**: Verify evaluation loop disconnects peers with empty bitfields
4. **New Peer Discovery Test**: Verify new peers are sought when all current peers have no pieces

## Related Fixes

- [Peer Discovery and Piece Selection Loop Fix](./peer-discovery-piece-selection-fix.md)
- [Peer Timeout and No-Pieces Disconnect Fix](./peer-timeout-no-pieces-fix.md)
- [DHT Download Start Loop Fix](./dht-download-start-loop-fix.md)











