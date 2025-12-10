# Peer Timeout and No-Pieces Disconnect Fix

## Problem Diagnosis

### Symptoms
- Peers connected but showing `pieces_known=0` (no bitfields received)
- All peers choked (`choking=True`, `can_request=False`)
- `peers_with_bitfield=0` - no peers have sent bitfields
- Peers kept in connection pool even when they have no pieces we need
- Infinite loops selecting pieces that no peer has

### Root Causes

1. **No Bitfield Timeout**: Peers that don't send bitfield after handshake are kept indefinitely
   - According to BitTorrent spec, bitfield should be sent immediately after handshake
   - No timeout mechanism to disconnect peers that don't follow protocol

2. **No Mutual Interest Check**: Peers with no pieces we need are kept in connection pool
   - BitTorrent protocol: peers should disconnect when there's no mutual interest
   - No logic to check if peer has any pieces we need after bitfield is received
   - No timeout to disconnect useless peers

3. **Missing NOT_INTERESTED Message**: When peer has no pieces we need, we don't send NOT_INTERESTED
   - BitTorrent protocol requires NOT_INTERESTED when we're not interested
   - This helps peers know we don't need anything from them

## Solution Implemented

### 1. Bitfield Timeout Monitor

**Location**: `ccbt/peer/async_peer_connection.py:3644-3675`

**Changes**:
- Start timeout monitor after handshake completes
- Disconnect peers that don't send bitfield within 60 seconds
- Cancel timeout monitor when bitfield is received
- Complies with BitTorrent protocol (bitfield should be sent immediately after handshake)

**Key Code**:
```python
# Start bitfield timeout monitor
bitfield_timeout = 60.0  # 60 seconds timeout
async def bitfield_timeout_monitor():
    await asyncio.sleep(bitfield_timeout)
    if connection.state not in (BITFIELD_RECEIVED, ACTIVE, CHOKED):
        # Bitfield not received - disconnect
        await self._disconnect_peer(connection)
```

### 2. Check for No Useful Pieces After Bitfield

**Location**: `ccbt/peer/async_peer_connection.py:5891-5967`

**Changes**:
- After bitfield is received, check if peer has ANY pieces we need
- If peer has no pieces we need:
  - Send NOT_INTERESTED message (BitTorrent protocol compliance)
  - Schedule disconnect after 10-second grace period
  - Grace period allows peer to send HAVE messages for new pieces

**Key Code**:
```python
# Check if peer has any pieces we need
has_needed_piece = False
for piece_idx in missing_pieces:
    if bitfield has piece_idx:
        has_needed_piece = True
        break

if not has_needed_piece:
    # Send NOT_INTERESTED and schedule disconnect
    await send_not_interested(connection)
    await delayed_disconnect()  # 10 second grace period
```

### 3. Periodic Health Check for Useless Peers

**Location**: `ccbt/peer/async_peer_connection.py:7058-7080`

**Changes**:
- In `_peer_evaluation_loop`, check all active peers
- If peer has bitfield but no pieces we need, disconnect after grace period (30 seconds)
- Prevents keeping useless connections that waste resources

**Key Code**:
```python
# Check if peer has no pieces we need
if connection.is_active() and connection.peer_state.bitfield:
    has_needed_piece = check_if_peer_has_missing_pieces(connection)
    if not has_needed_piece:
        connection_age = time.time() - connection.stats.last_activity
        if connection_age > 30.0:  # Grace period
            await self._disconnect_peer(connection)
```

## BitTorrent Protocol Compliance

### Bitfield Message (BEP 3)
- **Requirement**: Bitfield should be sent immediately after handshake
- **Our Fix**: Timeout peers that don't send bitfield within 60 seconds

### Mutual Interest (BEP 3)
- **Requirement**: Peers should disconnect when there's no mutual interest
- **Our Fix**: 
  - Send NOT_INTERESTED when peer has no pieces we need
  - Disconnect peers with no useful pieces after grace period

### NOT_INTERESTED Message (BEP 3)
- **Requirement**: Send NOT_INTERESTED when we're not interested in peer
- **Our Fix**: Send NOT_INTERESTED when peer has no pieces we need

## Impact

### Before Fix
- Peers without bitfields kept indefinitely
- Peers with no useful pieces kept in connection pool
- Wasted resources on useless connections
- Infinite loops selecting pieces no peer has

### After Fix
- Peers that don't send bitfield are disconnected after 60 seconds
- Peers with no useful pieces are disconnected after grace period
- NOT_INTERESTED sent to peers with no pieces we need
- Connection pool only keeps useful peers
- No infinite loops - peers are disconnected if they have nothing we need

## Configuration

No new configuration options required. The fix uses:
- Bitfield timeout: 60 seconds (hardcoded, follows BitTorrent spec)
- Grace period for no-pieces disconnect: 10 seconds (immediate) + 30 seconds (periodic check)
- Peer evaluation interval: 30 seconds (configurable via `config.network.peer_evaluation_interval`)

## Testing Recommendations

1. **Test bitfield timeout**:
   - Connect to peer that doesn't send bitfield
   - Verify peer is disconnected after 60 seconds

2. **Test no-pieces disconnect**:
   - Connect to peer that has no pieces we need
   - Verify NOT_INTERESTED is sent
   - Verify peer is disconnected after grace period

3. **Test periodic health check**:
   - Connect to peer with no useful pieces
   - Wait for periodic evaluation loop
   - Verify peer is disconnected

4. **Test grace period**:
   - Connect to peer with no pieces we need
   - Verify peer is kept for grace period (30 seconds)
   - Verify peer is disconnected after grace period

## Files Modified

- `ccbt/peer/async_peer_connection.py`:
  - `_handle_bitfield()`: Added check for no useful pieces, send NOT_INTERESTED, schedule disconnect
  - `_connect_to_peer()`: Added bitfield timeout monitor
  - `_peer_evaluation_loop()`: Added periodic check for peers with no useful pieces












