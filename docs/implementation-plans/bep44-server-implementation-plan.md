# BEP 44 Server Implementation Plan (Todo 7)

Complete implementation plan for handling **incoming** DHT get/put requests so this node can act as a BEP 44 storage node. **All items are in scope**, including those previously marked optional: error response handling (y="e"), BEP 5 query handlers (find_node, get_peers, announce_peer), adding sender to routing table, full IPv6 nodes6 in get response, sending error for invalid get target, CAS (compare-and-swap) for mutable put, and config `dht_max_storage_size`.

**Current state:** `DHTProtocol.datagram_received` calls only `handle_response(data, addr)`. `handle_response` processes only `y="r"`. All queries (`y="q"`) are ignored. The node never issues tokens or stores data for others.

**Target state:** When `dht_enable_storage` is True (and for put when not read-only), the node handles incoming **get**, **put** (BEP 44), and **find_node**, **get_peers**, **announce_peer** (BEP 5): responds with token + nodes/nodes6 (+ value or peers when applicable), accepts put after token/signature/seq/CAS checks, and adds senders to the routing table.

---

## Project 1: Datagram dispatch — route queries vs responses

**Goal:** Decode each incoming datagram once and dispatch to request handling (y="q") or response handling (y="r"/y="e"). Error responses (y="e") complete pending queries so client put/get see failures.

### Activity 1.1: Single entry point and response handling

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add `handle_datagram(self, data: bytes, addr: tuple[str, int]) -> None` as the single entry for all incoming UDP. | New method; insert after `handle_response` (~line 2199). |
| 2 | Decode message once: `decoder = BencodeDecoder(data); message = decoder.decode()`. On decode exception: log at debug, return. | Try/except around decode; log exception. |
| 3 | If `message.get(b"y") == b"q"`: call `self._handle_request(message, addr)` and return. | Query path. |
| 4 | If `message.get(b"y") == b"r"`: get `tid = message.get(b"t")`; if tid and tid in self.pending_queries: get future, if not future.done(): future.set_result(message). Return. | Inline current handle_response logic so one decode. |
| 5 | If `message.get(b"y") == b"e"`: same as "r" but set_result(message) so _send_query callers receive the error message (put/get can check for y="e" and e=[code, msg]). Return. | Error response path. |
| 6 | Else: return (unknown message type). | Defensive. |
| 7 | In `DHTProtocol.datagram_received` (line ~2493): replace `self.client.handle_response(data, addr)` with `self.client.handle_datagram(data, addr)`. | One-line change. |

**Line-level subtasks (Activity 1.1):**

- **dht.py** (after `handle_response`, ~2199): Add `def handle_datagram(self, data: bytes, addr: tuple[str, int]) -> None:`.
- **Line +1:** `try:` then `message = BencodeDecoder(data).decode()`.
- **Line +2:** `y = message.get(b"y")`.
- **Line +3:** `if y == b"q": self._handle_request(message, addr); return`.
- **Line +4:** `if y in (b"r", b"e"): tid = message.get(b"t"); ...` (if tid and tid in self.pending_queries: future = self.pending_queries[tid]; if not future.done(): future.set_result(message)); return.
- **Line +5:** `except Exception as e: self.logger.debug("Failed to parse DHT datagram: %s", e)`.
- **dht.py** `DHTProtocol.datagram_received` (current ~2493–2495): Replace body with `self.client.handle_datagram(data, addr)`.

### Activity 1.2: Request handler, routing table update, and BEP 5 + BEP 44 routing

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add `_handle_request(self, message: dict[bytes, Any], addr: tuple[str, int]) -> None`. Extract `q = message.get(b"q")`, `a = message.get(b"a")`, `t = message.get(b"t")`. If a is not a dict or t is None: return. | Central dispatcher. |
| 2 | Gate: if not `get_config().discovery.dht_enable_storage`: return (no response). Server only when storage enabled. | First check after extracting a, t. |
| 3 | Add sender to routing table: `node_id = a.get(b"id")`; if node_id is not None and len(node_id) == 20: create `DHTNode(node_id, addr[0], addr[1])`, call `self.routing_table.add_node(new_node)`. Use try/except or add_node's return to avoid breaking on duplicate/full bucket. | In scope: always add sender. |
| 4 | If `q == b"get"`: call `self._handle_get_request(a, t, addr)`. Elif `q == b"put"`: call `self._handle_put_request(a, t, addr)`. Elif `q == b"find_node"`: call `self._handle_find_node_request(a, t, addr)`. Elif `q == b"get_peers"`: call `self._handle_get_peers_request(a, t, addr)`. Elif `q == b"announce_peer"`: call `self._handle_announce_peer_request(a, t, addr)`. Else: return (unknown query). | All BEP 5 and BEP 44 query types in scope. |

**Line-level subtasks (Activity 1.2):**

- **dht.py** (new method after handle_datagram): `def _handle_request(self, message: dict[bytes, Any], addr: tuple[str, int]) -> None:`.
- **Line +1:** `a, t = message.get(b"a"), message.get(b"t")`. If not isinstance(a, dict) or t is None: return.
- **Line +2:** `if not get_config().discovery.dht_enable_storage: return`.
- **Line +3:** `node_id = a.get(b"id")`; if node_id is not None and len(node_id) == 20: `n = DHTNode(node_id, addr[0], addr[1])`; `try: self.routing_table.add_node(n)` except Exception: pass (or ignore).
- **Line +4:** `q = message.get(b"q")`. Then if q == b"get": self._handle_get_request(a, t, addr). Elif q == b"put": self._handle_put_request(a, t, addr). Elif q == b"find_node": self._handle_find_node_request(a, t, addr). Elif q == b"get_peers": self._handle_get_peers_request(a, t, addr). Elif q == b"announce_peer": self._handle_announce_peer_request(a, t, addr).

---

## Project 2: BEP 44 get request handler

**Goal:** Respond to incoming BEP 44 get with token, nodes, nodes6, and value (if stored). Issue and store write token. Send error response when target is invalid (in scope).

### Activity 2.1: Server token storage and issuance (BEP 44)

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | In `__init__` (~line 540): add `self._storage_write_tokens: dict[tuple[tuple[str, int], bytes], tuple[bytes, float]] = {}` mapping (addr, target_key) -> (token_bytes, expires_at). | Next to _storage_tokens, _xet_mutable_store. |
| 2 | Token expiry 900 seconds. Clean expired in `_cleanup_old_data`. | Below existing _storage_tokens cleanup block (~2314). |
| 3 | Add `_issue_storage_token(self, addr: tuple[str, int], target: bytes) -> bytes`. Use HMAC: `hmac.new(self.token_secret, addr[0].encode() + str(addr[1]).encode() + target, hashlib.sha256).digest()[:32]` (or full 32). Store `self._storage_write_tokens[(addr, target)] = (token, time.time() + 900)`. Return token. | New method; requires `import hmac` at top if not present. |

**Line-level subtasks (Activity 2.1):**

- **dht.py** `__init__` (~540): Add `self._storage_write_tokens: dict[tuple[tuple[str, int], bytes], tuple[bytes, float]] = {}`.
- **dht.py** `_cleanup_old_data` (after existing _storage_tokens cleanup, ~2321): Build list of keys to remove: `expired_write = [k for k, (_, exp) in self._storage_write_tokens.items() if current_time > exp]`. For k in expired_write: del self._storage_write_tokens[k].
- **dht.py** (new): `def _issue_storage_token(self, addr: tuple[str, int], target: bytes) -> bytes:`; body: token = hmac.new(self.token_secret, (addr[0] + str(addr[1])).encode() + target, hashlib.sha256).digest()[:32]; self._storage_write_tokens[(addr, target)] = (token, time.time() + 900); return token.

### Activity 2.2: Build compact nodes and nodes6 (IPv6 in scope)

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add `_build_compact_nodes(self, target_id: bytes, count: int = 8) -> tuple[bytes, bytes]` returning (nodes, nodes6). | New method. |
| 2 | `closest = self.routing_table.get_closest_nodes(target_id, count)`. | Reuse API. |
| 3 | IPv4 nodes: for each node in closest, try: `node.node_id + socket.inet_pton(socket.AF_INET, node.ip) + node.port.to_bytes(2, "big")`. On socket.error skip that node. Concatenate to `nodes` bytes. | 26 bytes per node. |
| 4 | IPv6 nodes6: for each node in closest where node.has_ipv6 and node.ipv6 and node.port6, try: `node.node_id + socket.inet_pton(socket.AF_INET6, node.ipv6) + node.port6.to_bytes(2, "big")`. Concatenate to `nodes6`. BEP 32: 38 bytes per node. If no IPv6 nodes, nodes6 = b"". | Full nodes6 in scope. |

**Line-level subtasks (Activity 2.2):**

- **dht.py** (new): `def _build_compact_nodes(self, target_id: bytes, count: int = 8) -> tuple[bytes, bytes]:`.
- **Line +1:** `closest = self.routing_table.get_closest_nodes(target_id, count)`.
- **Line +2:** `nodes_list = []`; for n in closest: try: nodes_list.append(n.node_id + socket.inet_pton(socket.AF_INET, n.ip) + n.port.to_bytes(2, "big")); except (OSError, ValueError): pass. `nodes = b"".join(nodes_list)`.
- **Line +3:** `nodes6_list = []`; for n in closest: if getattr(n, "has_ipv6", False) and getattr(n, "ipv6", None) and getattr(n, "port6", None): try: nodes6_list.append(n.node_id + socket.inet_pton(socket.AF_INET6, n.ipv6) + n.port6.to_bytes(2, "big")); except (OSError, ValueError): pass. `nodes6 = b"".join(nodes6_list)`.
- **Line +4:** return (nodes, nodes6).

### Activity 2.3: Get request handler and error response for invalid target

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add `_handle_get_request(self, a: dict[bytes, Any], t: Any, addr: tuple[str, int]) -> None`. Read `target = a.get(b"target")`. If target is None or len(target) != 20: call `self._send_error(t, addr, 203, b"invalid target")` and return. | In scope: send error for invalid get. |
| 2 | Token: `token = self._issue_storage_token(addr, target)`. | Activity 2.1. |
| 3 | Nodes: `nodes, nodes6 = self._build_compact_nodes(target)`. | Activity 2.2. |
| 4 | Build r = {b"id": self.node_id, b"token": token, b"nodes": nodes, b"nodes6": nodes6}. If target in self._xet_mutable_store: r[b"v"] = self._xet_mutable_store[target]. | BEP 44 get response. |
| 5 | Encode msg = {b"t": t, b"y": b"r", b"r": r}. If self.transport: self.transport.sendto(BencodeEncoder().encode(msg), addr). Wrap in try/except; on exception log at debug. | Synchronous send. |

**Line-level subtasks (Activity 2.3):**

- **dht.py** (new): `def _handle_get_request(self, a: dict[bytes, Any], t: Any, addr: tuple[str, int]) -> None:`.
- **Line +1:** target = a.get(b"target"). If not target or len(target) != 20: self._send_error(t, addr, 203, b"invalid target"); return.
- **Line +2:** token = self._issue_storage_token(addr, target); nodes, nodes6 = self._build_compact_nodes(target).
- **Line +3:** r = {b"id": self.node_id, b"token": token, b"nodes": nodes, b"nodes6": nodes6}. if target in self._xet_mutable_store: r[b"v"] = self._xet_mutable_store[target].
- **Line +4:** try: msg = {b"t": t, b"y": b"r", b"r": r}; self.transport.sendto(BencodeEncoder().encode(msg), addr) except Exception as e: self.logger.debug("Failed to send get response: %s", e). Guard with if self.transport.

---

## Project 3: BEP 44 put request handler (incl. CAS)

**Goal:** Validate put (token, size, mutable: signature, seq, CAS), store value, send success or BEP 44 error. Use config `dht_max_storage_size`. CAS in scope.

### Activity 3.1: Error helper and put key derivation

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add `_send_error(self, t: Any, addr: tuple[str, int], code: int, msg: bytes) -> None`. Build message = {b"t": t, b"y": b"e", b"e": [code, msg]}. If self.transport: sendto(BencodeEncoder().encode(message), addr). Try/except log on failure. | Shared for get (invalid target) and put (205/206/207/301/302/203). |
| 2 | Put key derivation: immutable key = calculate_immutable_key(value_bytes). Mutable key = calculate_mutable_key(a[b"k"], a.get(b"salt", b"")). | From dht_storage. |
| 3 | Use `get_config().discovery.dht_max_storage_size` for max value size (default 1000). If not set, use dht_storage.MAX_STORAGE_VALUE_SIZE. | In scope: config everywhere. |

**Line-level subtasks (Activity 3.1):**

- **dht.py** (new): `def _send_error(self, t: Any, addr: tuple[str, int], code: int, msg: bytes) -> None:`; body: message = {b"t": t, b"y": b"e", b"e": [code, msg]}; try: self.transport.sendto(BencodeEncoder().encode(message), addr) except Exception as e: self.logger.debug("Failed to send error: %s", e). Guard with if self.transport.
- **dht.py** `_handle_put_request`: max_size = getattr(get_config().discovery, "dht_max_storage_size", None) or MAX_STORAGE_VALUE_SIZE (import from dht_storage if needed).

### Activity 3.2: Put handler — read_only, required fields, size, token

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | In `__init__` (~540): add `self._storage_seq: dict[bytes, int] = {}` for mutable seq tracking. | Next to _storage_write_tokens. |
| 2 | `_handle_put_request(self, a: dict[bytes, Any], t: Any, addr: tuple[str, int]) -> None`. If self.read_only: _send_error(t, addr, 203, b"read-only node"); return. | BEP 43. |
| 3 | Read token = a.get(b"token"), v = a.get(b"v"). If token is None or v is None: _send_error(t, addr, 203, b"missing token or value"); return. | Required fields. |
| 4 | value_bytes = v if isinstance(v, bytes) else BencodeEncoder().encode(v). If len(value_bytes) > max_size (from config): _send_error(t, addr, 205, b"message too big"); return. | Use dht_max_storage_size. |
| 5 | Salt size (BEP 44): if a.get(b"salt") is not None and len(a[b"salt"]) > 64: _send_error(t, addr, 207, b"salt too big"); return. | Error 207. |
| 6 | Derive key: is_mutable = (a.get(b"k") is not None). If is_mutable: key = calculate_mutable_key(a[b"k"], a.get(b"salt", b"")). Else: key = calculate_immutable_key(value_bytes). | From dht_storage. |
| 7 | Token check: lookup_key = (addr, key). If lookup_key not in self._storage_write_tokens or self._storage_write_tokens[lookup_key][0] != token: _send_error(t, addr, 203, b"invalid token"); return. | BEP 44. |

**Line-level subtasks (Activity 3.2):**

- **dht.py** `__init__`: Add `self._storage_seq: dict[bytes, int] = {}`.
- **dht.py** (new): `def _handle_put_request(self, a: dict[bytes, Any], t: Any, addr: tuple[str, int]) -> None:`.
- **Lines:** read_only check; token/v check; value_bytes and len vs max_size (205); salt len check (207); key derivation; token lookup and match (203).

### Activity 3.3: Mutable put — signature, seq, CAS

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | If is_mutable: k, seq, sig = a.get(b"k"), a.get(b"seq"), a.get(b"sig"); salt = a.get(b"salt", b""). If k is None or seq is None or sig is None: _send_error(t, addr, 203, b"missing k/seq/sig"); return. | Required mutable fields. |
| 2 | Verify signature: data = value_bytes; if not verify_mutable_data_signature(data, k, sig, seq, salt): _send_error(t, addr, 206, b"invalid signature"); return. | dht_storage.verify_mutable_data_signature. |
| 3 | CAS (in scope): cas = a.get(b"cas"). If cas is not None: current_seq = self._storage_seq.get(key, 0). If current_seq != cas: _send_error(t, addr, 301, b"cas mismatch"); return. | BEP 44 CAS. |
| 4 | Seq check: if seq <= self._storage_seq.get(key, 0): _send_error(t, addr, 302, b"sequence number less than current"); return. | BEP 44. |
| 5 | Store: self._xet_mutable_store[key] = value_bytes; self._storage_seq[key] = seq. Send success. | After all checks. |

**Line-level subtasks (Activity 3.3):**

- **dht.py** _handle_put_request (mutable branch): extract k, seq, sig, salt; validate present; verify_mutable_data_signature; if a.get(b"cas") is not None and self._storage_seq.get(key, 0) != a[b"cas"]: _send_error 301; if seq <= self._storage_seq.get(key, 0): _send_error 302; then store and update _storage_seq; build success msg and sendto.

### Activity 3.4: Put success and immutable path

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Immutable path (else branch after is_mutable): no signature/seq/CAS. Store self._xet_mutable_store[key] = value_bytes. Send success. | No _storage_seq update. |
| 2 | Success response: msg = {b"t": t, b"y": b"r", b"r": {b"id": self.node_id}}. If self.transport: sendto(BencodeEncoder().encode(msg), addr). Try/except log. | Single place after store. |

**Line-level subtasks (Activity 3.4):**

- **dht.py** _handle_put_request: after mutable branch (store + _storage_seq[key]=seq), else (immutable): self._xet_mutable_store[key] = value_bytes. Then common: success_msg = {b"t": t, b"y": b"r", b"r": {b"id": self.node_id}}; try: self.transport.sendto(...); except log.

---

## Project 4: BEP 5 request handlers (find_node, get_peers, announce_peer)

**Goal:** Handle find_node, get_peers, and announce_peer so the node participates fully in the DHT. Token for get_peers/announce_peer; store peers per info_hash for announce_peer.

### Activity 4.1: Peer and get_peers token storage

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | In `__init__` (~540): add `self._get_peers_tokens: dict[tuple[tuple[str, int], bytes], tuple[bytes, float]] = {}` mapping (addr, info_hash) -> (token, expires_at). Expiry 900 seconds. | BEP 5 token for announce_peer. |
| 2 | In `__init__`: add `self._peers_store: dict[bytes, list[tuple[str, int]]] = {}` mapping info_hash -> list of (ip, port). | Store announced peers. |
| 3 | In `_cleanup_old_data`: remove expired entries from _get_peers_tokens (same pattern as _storage_write_tokens). | Cleanup. |

**Line-level subtasks (Activity 4.1):**

- **dht.py** `__init__`: `self._get_peers_tokens: dict[tuple[tuple[str, int], bytes], tuple[bytes, float]] = {}`; `self._peers_store: dict[bytes, list[tuple[str, int]]] = {}`.
- **dht.py** `_cleanup_old_data`: expired_get_peers = [k for k, (_, exp) in self._get_peers_tokens.items() if current_time > exp]; for k in expired_get_peers: del self._get_peers_tokens[k].

### Activity 4.2: find_node handler

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add `_handle_find_node_request(self, a: dict[bytes, Any], t: Any, addr: tuple[str, int]) -> None`. Read target = a.get(b"target"). If not target or len(target) != 20: return (or _send_error 203). | BEP 5 find_node. |
| 2 | nodes, nodes6 = self._build_compact_nodes(target). r = {b"id": self.node_id, b"nodes": nodes, b"nodes6": nodes6}. Send {b"t": t, b"y": b"r", b"r": r}. | No token. |

**Line-level subtasks (Activity 4.2):**

- **dht.py** (new): `def _handle_find_node_request(self, a: dict[bytes, Any], t: Any, addr: tuple[str, int]) -> None:`; target = a.get(b"target"); if not target or len(target) != 20: return; nodes, nodes6 = self._build_compact_nodes(target); r = {b"id": self.node_id, b"nodes": nodes, b"nodes6": nodes6}; try: self.transport.sendto(BencodeEncoder().encode({b"t": t, b"y": b"r", b"r": r}), addr) except Exception: self.logger.debug(...).

### Activity 4.3: get_peers handler and token issuance

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add `_issue_get_peers_token(self, addr: tuple[str, int], info_hash: bytes) -> bytes`. Generate token (e.g. HMAC with token_secret, key = addr + info_hash). Store _get_peers_tokens[(addr, info_hash)] = (token, time.time() + 900). Return token. | Same pattern as _issue_storage_token. |
| 2 | Add `_handle_get_peers_request(self, a: dict[bytes, Any], t: Any, addr: tuple[str, int]) -> None`. Read info_hash = a.get(b"info_hash"). If not info_hash or len(info_hash) != 20: return. | BEP 5 get_peers. |
| 3 | token = self._issue_get_peers_token(addr, info_hash). nodes, nodes6 = self._build_compact_nodes(info_hash). values = list of compact peer strings (6 bytes each: 4 IP + 2 port) from self._peers_store.get(info_hash, []). | BEP 5: values is list of 6-byte strings. |
| 4 | r = {b"id": self.node_id, b"token": token, b"nodes": nodes, b"nodes6": nodes6}. If values: r[b"values"] = values. Send response. | get_peers response. |

**Line-level subtasks (Activity 4.3):**

- **dht.py** (new): `def _issue_get_peers_token(self, addr: tuple[str, int], info_hash: bytes) -> bytes:`; token = hmac.new(self.token_secret, (addr[0] + str(addr[1])).encode() + info_hash, hashlib.sha256).digest()[:32]; self._get_peers_tokens[(addr, info_hash)] = (token, time.time() + 900); return token.
- **dht.py** (new): `def _handle_get_peers_request(self, a, t, addr):`; info_hash = a.get(b"info_hash"); if not info_hash or len(info_hash) != 20: return; token = self._issue_get_peers_token(addr, info_hash); nodes, nodes6 = self._build_compact_nodes(info_hash); peers = self._peers_store.get(info_hash, []); values = [socket.inet_pton(socket.AF_INET, ip) + port.to_bytes(2, "big") for ip, port in peers[:50]]; r = {b"id": self.node_id, b"token": token, b"nodes": nodes, b"nodes6": nodes6}; if values: r[b"values"] = values; sendto.

### Activity 4.4: announce_peer handler

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add `_handle_announce_peer_request(self, a: dict[bytes, Any], t: Any, addr: tuple[str, int]) -> None`. Read info_hash = a.get(b"info_hash"), token = a.get(b"token"), port = a.get(b"port"). If any missing or port not int: return or _send_error. | BEP 5 announce_peer. |
| 2 | Token check: key = (addr, info_hash). If key not in _get_peers_tokens or _get_peers_tokens[key][0] != token: return or _send_error 203. | Verify token. |
| 3 | Append (addr[0], port) to _peers_store[info_hash] (deduplicate if desired; limit list size e.g. 100). | Store peer. |
| 4 | Send success: r = {b"id": self.node_id}; send {b"t": t, b"y": b"r", b"r": r}. | announce_peer response. |

**Line-level subtasks (Activity 4.4):**

- **dht.py** (new): `def _handle_announce_peer_request(self, a, t, addr):`; info_hash, token, port = a.get(b"info_hash"), a.get(b"token"), a.get(b"port"); if not info_hash or len(info_hash) != 20 or not token: return; if not isinstance(port, int): return; key = (addr, info_hash); if key not in self._get_peers_tokens or self._get_peers_tokens[key][0] != token: return; peer = (addr[0], port); self._peers_store.setdefault(info_hash, []); if peer not in self._peers_store[info_hash]: self._peers_store[info_hash].append(peer); self._peers_store[info_hash] = self._peers_store[info_hash][-100:]; send success response.

---

## Project 5: Configuration and cleanup (all explicit)

**Goal:** Gate server with dht_enable_storage; read_only for put; cleanup all server token dicts; use dht_max_storage_size everywhere.

### Activity 5.1: Gating and config

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | _handle_request: first line after validating a, t: if not get_config().discovery.dht_enable_storage: return. | Already in Activity 1.2. |
| 2 | _handle_put_request: first line: if self.read_only: self._send_error(t, addr, 203, b"read-only node"); return. | Already in Activity 3.2. |
| 3 | Put size check: max_size = get_config().discovery.dht_max_storage_size if hasattr(get_config().discovery, "dht_max_storage_size") and get_config().discovery.dht_max_storage_size else 1000. Or import MAX_STORAGE_VALUE_SIZE from dht_storage and use getattr(..., dht_max_storage_size, MAX_STORAGE_VALUE_SIZE). | Explicit config in scope. |

**Line-level subtasks (Activity 5.1):**

- **dht.py** _handle_put_request: at top, max_size = getattr(get_config().discovery, "dht_max_storage_size", None); if max_size is None: from ccbt.discovery.dht_storage import MAX_STORAGE_VALUE_SIZE; max_size = MAX_STORAGE_VALUE_SIZE. Then use max_size in len(value_bytes) > max_size check.

### Activity 5.2: Cleanup of all server token and peer stores

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | _cleanup_old_data: after existing token cleanups, add cleanup for _storage_write_tokens (expired entries). | Activity 2.1. |
| 2 | _cleanup_old_data: add cleanup for _get_peers_tokens (expired entries). | Activity 4.1. |
| 3 | Optionally cap _peers_store size per info_hash (already in 4.4) and/or evict oldest info_hashes. | Can be same as 4.4 limit. |

**Line-level subtasks (Activity 5.2):**

- **dht.py** _cleanup_old_data: two blocks—(1) expired_write = [k for k, (_, exp) in self._storage_write_tokens.items() if current_time > exp]; for k in expired_write: del self._storage_write_tokens[k]; (2) expired_gp = [k for k, (_, exp) in self._get_peers_tokens.items() if current_time > exp]; for k in expired_gp: del self._get_peers_tokens[k].

---

## Project 6: Tests (full coverage)

**Goal:** Unit tests for dispatch, get (valid/invalid target), put (success, token/size/sig/seq/CAS/read_only), find_node, get_peers, announce_peer, and config/cleanup.

### Activity 6.1: File and test list

**File:** `tests/unit/discovery/test_dht_bep44_server.py` (new)

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Create test file. Use pytest, AsyncDHTClient, mock transport (MagicMock with sendto), mock or real routing table with at least one node so _build_compact_nodes returns non-empty. | New file. |
| 2 | Test handle_datagram y="q" q="get" with valid target: assert sendto called once; decode sent message; assert b"token" in r, b"nodes" in r, b"nodes6" in r; if key in _xet_mutable_store assert b"v" in r. | test_handle_datagram_get_valid. |
| 3 | Test handle_datagram y="q" q="get" with invalid target (missing or len != 20): assert sendto called with error message (y="e", e=[203, ...]). | test_handle_datagram_get_invalid_target. |
| 4 | Test handle_datagram y="q" q="put" with valid token (issue via prior get), immutable value: assert _xet_mutable_store updated, success response sent. | test_handle_datagram_put_immutable. |
| 5 | Test put without token: error 203. Put with wrong token: error 203. Put value > dht_max_storage_size: error 205. Put mutable invalid signature: error 206. Put mutable seq <= stored: error 302. Put mutable with cas mismatch: error 301. | test_handle_put_errors. |
| 6 | Test read_only: put handler sends 203 and does not update store. | test_handle_put_read_only. |
| 7 | Test dht_enable_storage False: _handle_request returns without sendto for get/put. | test_handle_request_storage_disabled. |
| 8 | Test _handle_find_node_request: valid target, assert response has id, nodes, nodes6. | test_handle_find_node. |
| 9 | Test _handle_get_peers_request: valid info_hash, assert response has token, nodes, nodes6; optionally values if _peers_store has peers. | test_handle_get_peers. |
| 10 | Test _handle_announce_peer_request: after get_peers to get token, announce_peer with token and port; assert _peers_store updated, success response. | test_handle_announce_peer. |
| 11 | Test _cleanup_old_data removes expired _storage_write_tokens and _get_peers_tokens. | test_cleanup_expired_server_tokens. |
| 12 | Test _build_compact_nodes returns nodes6 when routing table has node with ipv6/port6. | test_build_compact_nodes_ipv6. |

**Line-level subtasks (Activity 6.1):**

- **tests/unit/discovery/test_dht_bep44_server.py**: For each test: create client; set client.transport = MagicMock(); optionally add_node to routing table; call handle_datagram with bencoded message or call _handle_* directly; assert transport.sendto.call_count and decode first call args[0] to assert keys in response.

---

## Dependency order

1. **Project 1** (handle_datagram, _handle_request) — entry and dispatch.
2. **Project 2** (BEP 44 get: token store, _build_compact_nodes with nodes6, _handle_get_request, _send_error for invalid target).
3. **Project 3** (BEP 44 put: _send_error, _storage_seq, _handle_put_request with token/size/salt/signature/seq/CAS, dht_max_storage_size).
4. **Project 4** (BEP 5: _get_peers_tokens, _peers_store, _handle_find_node_request, _issue_get_peers_token, _handle_get_peers_request, _handle_announce_peer_request).
5. **Project 5** (config and cleanup explicit; cleanup _storage_write_tokens and _get_peers_tokens).
6. **Project 6** (tests).

---

## File-level task summary

| File | Tasks |
|------|--------|
| `ccbt/discovery/dht.py` | **__init__:** _storage_write_tokens, _storage_seq, _get_peers_tokens, _peers_store. **handle_datagram:** decode, branch y (q/r/e), response/error set_result. **DHTProtocol.datagram_received:** call handle_datagram. **_handle_request:** gate, add sender node, dispatch get/put/find_node/get_peers/announce_peer. **_send_error:** build and send error message. **_issue_storage_token:** HMAC, store, return. **_build_compact_nodes:** IPv4 + IPv6 (nodes6) compact. **_handle_get_request:** validate target (else _send_error 203), issue token, nodes, r with v if present, send. **_handle_put_request:** read_only, token/v/size/salt, key, token verify, mutable (sig, cas, seq), store, success. **_handle_find_node_request:** target, nodes, nodes6, send. **_issue_get_peers_token:** HMAC, store, return. **_handle_get_peers_request:** info_hash, token, nodes, values from _peers_store, send. **_handle_announce_peer_request:** token verify, append peer to _peers_store, send. **_cleanup_old_data:** expire _storage_write_tokens, _get_peers_tokens. |
| `tests/unit/discovery/test_dht_bep44_server.py` | New file: tests for handle_datagram get (valid/invalid), put (success, 203/205/206/301/302, read_only), storage disabled, find_node, get_peers, announce_peer, cleanup, _build_compact_nodes IPv6. |

---

## Line-level subtask summary (dht.py)

- **__init__ (~540):** Add four attributes: `self._storage_write_tokens: dict[tuple[tuple[str, int], bytes], tuple[bytes, float]] = {}`, `self._storage_seq: dict[bytes, int] = {}`, `self._get_peers_tokens: dict[tuple[tuple[str, int], bytes], tuple[bytes, float]] = {}`, `self._peers_store: dict[bytes, list[tuple[str, int]]] = {}`.
- **handle_datagram (new, after ~2199):** try/decode; y = message.get(b"y"); if y == b"q": _handle_request(message, addr); return; if y in (b"r", b"e"): tid = message.get(b"t"); if tid and tid in pending_queries: future = pending_queries[tid]; if not future.done(): future.set_result(message); return; except log.
- **DHTProtocol.datagram_received (~2493):** `self.client.handle_datagram(data, addr)`.
- **_handle_request (new):** a, t = message.get(b"a"), message.get(b"t"); if not isinstance(a, dict) or t is None: return; if not get_config().discovery.dht_enable_storage: return; node_id = a.get(b"id"); if node_id and len(node_id)==20: add_node(DHTNode(node_id, addr[0], addr[1])); q = message.get(b"q"); dispatch to _handle_get_request, _handle_put_request, _handle_find_node_request, _handle_get_peers_request, _handle_announce_peer_request.
- **_send_error (new):** (t, addr, code, msg) -> build {b"t", b"y": b"e", b"e": [code, msg]}, transport.sendto(encode(msg), addr), try/except log.
- **_issue_storage_token (new):** (addr, target) -> token = hmac.new(token_secret, addr+target, sha256).digest()[:32]; _storage_write_tokens[(addr,target)] = (token, time+900); return token.
- **_build_compact_nodes (new):** target_id, count=8 -> closest = get_closest_nodes; nodes = b"".join(26-byte per node IPv4); nodes6 = b"".join(38-byte per node IPv6 where has_ipv6); return (nodes, nodes6).
- **_handle_get_request (new):** target = a.get(b"target"); if not target or len(target)!=20: _send_error(t, addr, 203, b"invalid target"); return; token = _issue_storage_token(addr, target); nodes, nodes6 = _build_compact_nodes(target); r = {id, token, nodes, nodes6}; if target in _xet_mutable_store: r[b"v"] = store[target]; send {t, y:r, r}.
- **_handle_put_request (new):** read_only -> 203; token, v missing -> 203; value_bytes, len > max_size -> 205; salt len > 64 -> 207; key = immutable_key(v) or mutable_key(k,salt); token check (addr,key) -> 203; if mutable: k,seq,sig,salt; verify_sig -> 206; cas present and current_seq != cas -> 301; seq <= stored_seq -> 302; store; _storage_seq[key]=seq if mutable; send success.
- **_handle_find_node_request (new):** target; nodes, nodes6 = _build_compact_nodes(target); r = {id, nodes, nodes6}; send.
- **_issue_get_peers_token (new):** (addr, info_hash) -> token, store in _get_peers_tokens, return token.
- **_handle_get_peers_request (new):** info_hash; token = _issue_get_peers_token; nodes, nodes6; values from _peers_store; r = {id, token, nodes, nodes6 [, values]}; send.
- **_handle_announce_peer_request (new):** info_hash, token, port; token check (addr, info_hash); _peers_store.setdefault; append (addr[0], port); cap 100; send success.
- **_cleanup_old_data (~2301):** After existing cleanups, add: expired_write = [k for k, (_,e) in _storage_write_tokens.items() if current_time > e]; for k in expired_write: del _storage_write_tokens[k]; expired_gp = [k for k, (_,e) in _get_peers_tokens.items() if current_time > e]; for k in expired_gp: del _get_peers_tokens[k].

---

## BEP 44 and BEP 5 reference

- **Get response:** r = id, token, nodes, nodes6 [, v].
- **Put request:** immutable a = id, token, v; mutable a = id, token, k, seq, sig, v [, salt] [, cas].
- **Put response:** success r = {id}; error y="e", e=[code, msg]. Codes: 203 generic, 205 too big, 206 invalid sig, 207 salt too big, 301 cas mismatch, 302 seq.
- **find_node response:** r = id, nodes, nodes6.
- **get_peers response:** r = id, token, nodes, nodes6 [, values].
- **announce_peer request:** a = id, info_hash, token, port. Response: r = {id}.

This plan is complete with all optional items in scope and specific file-level tasks and line-level subtasks throughout.
