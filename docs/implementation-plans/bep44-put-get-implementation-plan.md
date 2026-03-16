# BEP 44 put_mutable / get_mutable Implementation Plan

Complete implementation plan for real DHT get/put (BEP 44) so that XET chunk peer discovery and BEP 51 infohash indexing work across the swarm instead of being local-only.

**Current state:** Data is stored only in `AsyncDHTClient._xet_mutable_store` (in-memory dict). No BEP 44 get/put RPCs are sent; XET chunk discovery and BEP 51 index storage are local-only and a no-op across the swarm.

**Target state:** Client sends BEP 44 `get` and `put` RPCs over the DHT; optionally this node responds to incoming `get`/`put` (storage node). Config `dht_enable_storage` gates storage behavior.

---

## Project 1: BEP 44 client — iterative get (find_value)

**Goal:** Implement iterative DHT **get** (BEP 44) so that `get_data()` can retrieve values from the DHT network, not only from local store.

### Activity 1.1: DHT get RPC send and response parsing

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add `_query_node_for_get(key: bytes, public_key: Optional[bytes], seq: Optional[int])` that sends a single BEP 44 `get` query to one node. | New method near `_query_node_for_peers` (~line 989). |
| 2 | Build get request: `q="get"`, `a={"id": node_id, "target": key}`; for mutable, target is already SHA-1(pubkey+salt). Optionally include `a["seq"]` for mutable “only if seq > N”. | Inside `_query_node_for_get`. |
| 3 | Call `_send_query(addr, "get", args)` and return response dict or None. | Reuse existing `_send_query` (line 1753). |
| 4 | Parse get response: extract `r["v"]` (immutable value), or `r["k"]`, `r["v"]`, `r["seq"]`, `r["sig"]`, `r["salt"]` (mutable). Extract `r["token"]` for subsequent put. Extract `r["nodes"]` / `r["nodes6"]` for iterative lookup. | New helper `_parse_get_response(response: dict) -> Optional[tuple[Any, Optional[bytes], Optional[bytes]]]` (value, token, nodes_raw). |
| 5 | Validate immutable: SHA-1(encoded v) == target. Validate mutable: verify signature; key = SHA-1(k [+ salt]) == target. Reject invalid. | Use `ccbt.discovery.dht_storage`: `calculate_immutable_key`, `calculate_mutable_key`, `verify_mutable_data_signature`. |
| 6 | Store token per (key or target) for use by put: e.g. `self._storage_tokens[key] = (token, time.time() + 900)`. | New attribute `_storage_tokens: dict[bytes, tuple[bytes, float]]` (key -> (token, expires)); add in `__init__` near `self.tokens` (~line 523). |

**Line-level subtasks (Activity 1.1):**

- **dht.py `__init__`:** After `self.tokens` (line ~523), add `self._storage_tokens: dict[bytes, tuple[bytes, float]] = {}`.
- **dht.py `_query_node_for_get`:** Build `args = {b"id": self.node_id, b"target": key}`. If `public_key` is not None (mutable), target is already the 20-byte key (SHA-1(public_key+salt)); do not add `seq` to args unless implementing “get if seq > N” later. Call `_send_query((node.ip, node.port), "get", args)`. Return response.
- **dht.py `_parse_get_response`:** If `response.get(b"y") != b"r"`: return None. `r = response.get(b"r", {})`. Read `v = r.get(b"v")`, `token = r.get(b"token")`, `nodes = r.get(b"nodes", b"")`, `nodes6 = r.get(b"nodes6", b"")`. For mutable, read `k`, `seq`, `sig`, `salt`. Return structured result (value + token + nodes).
- **dht.py:** In cleanup loop `_cleanup_old_data` (line ~1942), add cleanup of expired entries in `_storage_tokens`.

---

### Activity 1.2: Iterative get (find_value) algorithm

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Implement `_get_data_iterative(key: bytes, public_key: Optional[bytes] = None, seq: Optional[int] = None)` that runs iterative find_value. | New method; mirror structure of `get_peers` (lines 1049–1462). |
| 2 | Get initial k closest nodes to `key`: `closest_nodes = self.routing_table.get_closest_nodes(key, k)`. Use same alpha/k/max_depth semantics as get_peers. | Same pattern as get_peers loop. |
| 3 | In each round: query alpha unqueried closest nodes in parallel with `_query_node_for_get(node, key, public_key, seq)`. | asyncio.gather of `_query_node_for_get`. |
| 4 | For each response: if value returned and valid (hash/signature check), collect it and store token in `_storage_tokens[key]`. Parse `nodes`/`nodes6` and add to routing table and to closest set (by distance to key). | Reuse 26-byte compact node format parsing (see get_peers ~1251–1270). |
| 5 | Stop when: (a) at least one valid value found and we have tokens from enough nodes, or (b) no closer nodes and queried >= k nodes / max depth. | Prefer stopping when we have one good value + token for put; optionally continue to collect more copies. |
| 6 | Return best value (e.g. mutable: highest seq; immutable: first valid) and optionally list of (token, addr) for put. | Return type: e.g. `tuple[Optional[bytes], list[tuple[bytes, tuple[str, int]]]]`. |

**Line-level subtasks (Activity 1.2):**

- **dht.py `_get_data_iterative`:** Use `queried_nodes: set[bytes]`, `closest_set: set[DHTNode]`, `found_value = None`, `found_tokens: list[tuple[bytes, tuple[str,int]]]`. Loop: `unqueried = [n for n in closest_set if n.node_id not in queried_nodes]`, take `alpha` nodes, await gather `_query_node_for_get`, process each response (validate, store token, merge nodes into closest_set), break when value found and enough tokens or convergence.

---

### Activity 1.3: Integrate iterative get into get_data

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | In `get_data()` (line ~1539): if config `dht_enable_storage` is True, call `_get_data_iterative(key, _public_key)` and return decoded value if found. | After local lookup. |
| 2 | Keep local fallback: if DHT get returns nothing, still return `self._xet_mutable_store.get(key)`. | Preserve backward compatibility. |
| 3 | Optional: merge DHT result into local cache for subsequent fast path. | `_xet_mutable_store[key] = value` when from DHT. |
| 4 | Update docstring: remove “BEP 44 get_mutable not implemented” and state that iterative get is used when `dht_enable_storage` is True. | Lines 1545–1549. |

**Line-level subtasks (Activity 1.3):**

- **dht.py `get_data`:** After `self.logger.debug("get_data called for key: %s", ...)`, add: `if get_config().discovery.dht_enable_storage: value, _ = await self._get_data_iterative(key, _public_key); if value is not None: return value`. Then keep `return self._xet_mutable_store.get(key)`.

---

## Project 2: BEP 44 client — put (immutable and mutable)

**Goal:** Implement DHT **put** so that `put_data()` replicates data to k closest nodes, not only to local store.

### Activity 2.1: Obtain write token via get

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Before put, we need a write token from nodes responsible for the key. BEP 44: “Responses to get should always include … token.” So run a get first (or use tokens from a previous get). | Reuse `_get_data_iterative`; ensure we collect and store tokens per (addr, key). |
| 2 | Add helper `_get_storage_tokens_for_key(key: bytes, min_count: int = 1)` that runs `_get_data_iterative(key)` and returns list of (token, addr) for nodes that returned a response (even if empty). If no get performed yet, run get; then return `[(t, addr) for (addr, t) in self._storage_tokens.get(key, [])]` or equivalent. | Token storage must be keyed by key and store (token, addr, expires). |
| 3 | Extend token storage: when parsing get response, store (token, addr) per key. Structure: `_storage_tokens[key] = [(token_bytes, addr), ...]` with expiry. | Adjust Activity 1.1 item 6: store list of (token, addr) per key; expiry per key (e.g. one expiry time for the whole key). |

**Line-level subtasks (Activity 2.1):**

- **dht.py:** Change `_storage_tokens` to `dict[bytes, tuple[list[tuple[bytes, tuple[str, int]]], float]]` (key -> (list of (token, addr), expires_at)). When parsing get response in iterative get, append `(token, addr)` to this list for the key.
- **dht.py `_get_storage_tokens_for_key(key, min_count)`:** If key not in `_storage_tokens` or expired or len(tokens) < min_count, call `_get_data_iterative(key)`; then return up to k (token, addr) from `_storage_tokens[key]`.

---

### Activity 2.2: Send put RPC (immutable and mutable)

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add `_send_put(addr: tuple[str, int], key: bytes, token: bytes, value: Union[bytes, dict], is_mutable: bool, public_key: Optional[bytes], seq: int, signature: Optional[bytes], salt: Optional[bytes])` that builds BEP 44 put request and sends it. | New method. |
| 2 | Immutable put: `a = {"id", "token", "v": value}`. Value must be bencoded; size ≤ 1000 bytes. Key for immutable is SHA-1(value); caller passes key for routing. | BEP 44 immutable put. |
| 3 | Mutable put: `a = {"id", "token", "k": public_key, "seq": seq, "sig": signature, "v": value}`; optional `salt`. No target in put; key is implied by k (+ salt). | BEP 44 mutable put. |
| 4 | Encode value: if dict, bencode it (sorted keys); ensure total size ≤ 1000. Use `BencodeEncoder` and `dht_storage.encode_storage_value` / raw bytes. | Reuse `ccbt.discovery.dht_storage.encode_storage_value` for typed mutable; for raw bytes use bencode directly. |
| 5 | Call `_send_query(addr, "put", a)` and return success if `response.get(b"y") == b"r"`. Handle error response (y="e", e=[code, msg]): 205 (too big), 206 (invalid sig), 301 (CAS), 302 (seq). | After `_send_query`; check for error reply. |

**Line-level subtasks (Activity 2.2):**

- **dht.py `_send_put`:** Build message `{b"t": tid, b"y": b"q", b"q": b"put", b"a": a}`. For immutable: `a = {b"id": self.node_id, b"token": token, b"v": value}`. For mutable: add b"k", b"seq", b"sig", b"v"; optionally b"salt". Encode with BencodeEncoder; send via transport.sendto. Wait for response (reuse _wait_for_response pattern or _send_query if we add put to it). Note: _send_query currently takes query name as string; extend to support "put" with custom args.
- **dht.py:** Either extend `_send_query` to accept pre-built `a` for put, or implement `_send_put` that builds the message and uses the same pending_queries/tid pattern as `_send_query`.

---

### Activity 2.3: Iterative put to k closest nodes

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Implement `_put_data_iterative(key, value, is_mutable, public_key, seq, signature, salt)` that: (1) gets tokens via `_get_storage_tokens_for_key(key, min_count=8)` (run get if needed), (2) sends put to each of up to k nodes with their token. | New method. |
| 2 | Get k closest nodes to key; for each we need a token. If we have fewer than k tokens, run get to more nodes (iterate get until we have k nodes that returned token). | Reuse get logic; collect (token, addr) for k nodes. |
| 3 | Call `_send_put(addr, key, token, value, ...)` for each (token, addr). Count successes. | Loop over list from step 1. |
| 4 | Return number of successful stores (0 to k). | Return int. |

**Line-level subtasks (Activity 2.3):**

- **dht.py `_put_data_iterative`:** Call `_get_storage_tokens_for_key(key, 8)`. If list length < 8, optionally run another get round to more nodes. Then for each (token, addr) in list[:8]: await _send_put(addr, key, token, value, ...); success_count += 1 on success. Return success_count.

---

### Activity 2.4: Integrate iterative put into put_data and store_chunk_hash

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | In `put_data()` (line ~1561): if not read_only and config `dht_enable_storage` is True, after storing locally, call `_put_data_iterative` with the encoded value. For XET chunk format we use immutable put (key = chunk_hash) or mutable (if we add pubkey/signature). | Current XET store uses raw key (chunk hash) and JSON value; BEP 44 immutable key = SHA-1(value). So for XET we may use immutable put with key = SHA-1(encoded_value) and store under that, or use mutable with a fixed key derivation. Decide: XET chunk key = 20-byte truncation of 32-byte chunk hash or SHA-1(chunk_hash)? BEP 44 immutable key is SHA-1(v). So for “put under chunk_hash” we need mutable (key = SHA-1(pubkey+salt)) with salt derived from chunk_hash, or we use immutable and key = SHA-1(encoded_value) — then lookup by key requires knowing the value. So XET should use mutable with salt = chunk_hash (or similar) so key = SHA-1(pubkey + chunk_hash). Document this in plan. | See “XET key strategy” below. |
| 2 | Keep local store: `self._xet_mutable_store[key] = encoded_value`; then if dht_enable_storage, call _put_data_iterative. | Preserve local-first behavior. |
| 3 | Update docstring for put_data: remove “no BEP 44 put_mutable RPC is sent” and state that when dht_enable_storage is True, data is also replicated to the DHT. | Lines 1567–1571. |
| 4 | `store_chunk_hash` (line 1615): already calls put_data; no change needed if put_data does the network put. Ensure key passed to put_data is the 20-byte key used for DHT (chunk hash truncated or SHA-1(chunk_hash) or mutable key). | XET chunk_hash is 32 bytes; DHT key is 20 bytes. So we must derive 20-byte key: e.g. first 20 bytes of chunk_hash, or SHA-1(chunk_hash). Use first 20 bytes for simplicity (or SHA-1 for BEP 44 alignment). |

**XET key strategy (clarification):**

- **Option A (immutable):** key = SHA-1(encoded_value). Then get_data(key) cannot be used with chunk_hash as key; we’d need to store a mapping. So not ideal for “lookup by chunk hash.”
- **Option B (mutable):** One global Ed25519 key for the client; salt = chunk_hash (or first 20 bytes). Then key = SHA-1(public_key + salt). Lookup: given chunk_hash, compute salt = chunk_hash[:20], key = SHA-1(pubkey + salt), get(key). So we need to pass public_key (and optionally salt) into get_data for XET. Current get_data(key, _public_key) already has _public_key. So: XET uses mutable with salt = chunk_hash[:20]; key = calculate_mutable_key(public_key, salt). Put: sign value with seq; put_mutable. Get: get_data(key, public_key) where key = calculate_mutable_key(public_key, chunk_hash[:20]). 
- **Option C (immutable, key = SHA-1(chunk_hash)):** Not in BEP 44; key for immutable is SHA-1(value). So we cannot use key = SHA-1(chunk_hash) for immutable. So use Option B (mutable) for XET chunk storage.

**Line-level subtasks (Activity 2.4):**

- **dht.py `store_chunk_hash`:** Ensure key is 20 bytes. If chunk_hash is 32 bytes, use `key = chunk_hash[:20]` or `hashlib.sha1(chunk_hash).digest()`. If we switch to mutable for XET, key = calculate_mutable_key(public_key, chunk_hash[:20]); we need key_manager or public_key in scope in store_chunk_hash (already have metadata; could add ed25519_public_key and use that for key derivation).
- **dht.py `put_data`:** After writing to _xet_mutable_store, if config.discovery.dht_enable_storage and not self.read_only: n = await self._put_data_iterative(key, encoded_value, ...). Return 1 for local + n for network, or keep return 1 when local stored and optionally return 1 + n.

---

## Project 3: BEP 44 server — handle incoming get/put (optional but recommended)

**Goal:** This node can act as a storage node: respond to incoming BEP 44 `get` and `put` from other nodes.

### Activity 3.1: Dispatch incoming queries (y="q")

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | In `handle_response` (or rename to `handle_datagram`), first decode the message. If `message.get(b"y") == b"q"` (query), call new `_handle_request(message, addr)` and return; else keep current response handling (y="r"). | Line ~1841; `datagram_received` calls `handle_response(data, addr)`. |
| 2 | Rename or split: e.g. `handle_datagram(data, addr)` that decodes once; if y=="q" then _handle_request; if y=="r" then existing response logic; if y=="e" then error. | Avoid double decode. |

**Line-level subtasks (Activity 3.1):**

- **dht.py:** Add `def handle_datagram(self, data: bytes, addr: tuple[str, int]) -> None`. Decode message. If `message.get(b"y") == b"q"`: call `self._handle_request(message, addr)`. Elif `message.get(b"y") == b"r"`: call current `handle_response` logic (set future result). Elif `message.get(b"y") == b"e"`: set future with error. Replace `handle_response` usage in DHTProtocol.datagram_received with `handle_datagram`.
- **dht.py `_handle_request`:** Extract `q = message.get(b"q")`, `a = message.get(b"a", {})`, `t = message.get(b"t")`. If q == b"get": call _handle_get_request(a, t, addr). If q == b"put": call _handle_put_request(a, t, addr). If q in (b"get_peers", b"find_node", b"announce_peer"): keep existing behavior if any (or add handlers). For now only add get/put.

---

### Activity 3.2: Handle incoming get

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | `_handle_get_request(a, t, addr)`: read `target = a.get(b"target")` (20 bytes). Look up in local store: `_xet_mutable_store.get(target)` and optionally in a BEP 44 storage cache (immutable/mutable by key). | Use _xet_mutable_store for now; later can add separate storage. |
| 2 | If we have a value: build response `r = {"id": self.node_id, "v": value}` (immutable) or include k, seq, sig, salt for mutable. Include "token" (generate and store per (addr, target) for put validation). Include "nodes" and "nodes6" (closest nodes to target from routing table). | BEP 44: get response always includes nodes, nodes6, token. |
| 3 | If we don’t have value: return response with token and nodes/nodes6 only (so requester can iterate and also use token for put). | Same structure, no v. |
| 4 | Send response back to addr with transaction id t. | Encode {b"t": t, b"y": b"r", b"r": r}; transport.sendto. |
| 5 | Token generation: same as get_peers (e.g. HMAC or random); store in a structure keyed by (addr, target) with expiry. | Reuse or mirror token logic from announce_peer. |

**Line-level subtasks (Activity 3.2):**

- **dht.py `_handle_get_request`:** Generate token (e.g. store in self._storage_write_tokens[(addr, target)] = token, expiry). Response r = {b"id": self.node_id, b"token": token, b"nodes": compact_nodes, b"nodes6": compact_nodes6}. If target in _xet_mutable_store: r[b"v"] = _xet_mutable_store[target]. Encode and send response.

---

### Activity 3.3: Handle incoming put

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | `_handle_put_request(a, t, addr)`: read token, value v, and for mutable: k, seq, sig, salt. Verify token (must have been issued for this key; key = target from token or from k+salt). | Reject if token missing or invalid. |
| 2 | If mutable: verify signature; verify seq >= stored_seq for that key (reject with 302 if lower). Optionally support cas. | Use dht_storage.verify_mutable_data_signature. |
| 3 | If immutable: verify SHA-1(v) == target (target must be sent in get; for put we don’t have target in message — BEP 44 put for immutable doesn’t have target; key is implied by value. So storing node must compute key = SHA-1(v) and store under that key). Store in _xet_mutable_store[key] = v (or in a dedicated BEP 44 store). | BEP 44: immutable put has no target; we store under SHA-1(v). |
| 4 | Enforce value size ≤ 1000 bytes. Return error 205 if too big. Return error 206 if signature invalid, 302 if seq outdated. | BEP 44 error codes. |
| 5 | Send success response {b"t": t, b"y": b"r", b"r": {b"id": self.node_id}} or error {b"y": b"e", b"e": [code, msg]}. | Send back to addr. |

**Line-level subtasks (Activity 3.3):**

- **dht.py `_handle_put_request`:** Check token: (addr, key) in _storage_write_tokens and token matches; key for mutable = calculate_mutable_key(k, salt). Verify signature for mutable. Compare seq with stored seq; reject if lower. Store value; send success or error.

---

## Project 4: DHT storage layer and XET key strategy

**Goal:** Align key derivation, signing, and value format with BEP 44 and XET requirements; ensure dht_storage is used correctly.

### Activity 4.1: XET chunk key and mutable format

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Define XET chunk DHT key: use mutable with one client key; salt = chunk_hash[:20] (or full 32 bytes hashed to 20). So key = calculate_mutable_key(xet_public_key, salt). | Central place (e.g. module-level or AsyncDHTClient method) to compute key from chunk_hash and public_key. |
| 2 | In `store_chunk_hash`: obtain public_key (from key_manager or config); salt = chunk_hash[:20]; key = calculate_mutable_key(public_key, salt). Build DHTMutableData with seq (increment per key or global), sign with key_manager, then encode and put. | dht_indexing already uses sign_mutable_data; mirror for XET. |
| 3 | In `get_chunk_peers`: key = calculate_mutable_key(public_key, chunk_hash[:20]); call get_data(key, public_key). Decode JSON list of peer records. | get_chunk_peers currently uses get_data(chunk_hash); change to key derived from chunk_hash + pubkey. |

**File:** `ccbt/discovery/xet_cas.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | When calling DHT store_chunk_hash, ensure key_manager is set so that public_key is available for key derivation. | Already passes metadata; dht.store_chunk_hash will need public_key for mutable key. |
| 2 | When calling DHT get_chunk_peers(chunk_hash), ensure we pass the same public_key (or let DHT client use default XET key). | get_chunk_peers may need to accept optional public_key or get it from key_manager. |

**Line-level subtasks (Activity 4.1):**

- **dht.py:** Add `def _xet_chunk_dht_key(self, chunk_hash: bytes) -> bytes` that returns calculate_mutable_key(self._xet_storage_public_key, chunk_hash[:20]). Require _xet_storage_public_key to be set (from config or key_manager). If no key, fall back to chunk_hash[:20] for backward compat and log warning.
- **dht.py store_chunk_hash:** Compute key = _xet_chunk_dht_key(chunk_hash). Get current seq from local state (e.g. self._xet_seq[key] or 1). Build DHTMutableData; sign; call put_data with mutable payload (or new put_mutable_data method).
- **dht.py get_chunk_peers:** key = _xet_chunk_dht_key(chunk_hash); encoded = await self.get_data(key, self._xet_storage_public_key); parse JSON and return list of PeerInfo.

---

### Activity 4.2: BEP 44 sign/verify format vs BEP 44 spec

**File:** `ccbt/discovery/dht_storage.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | BEP 44 signing: buffer is bencoded "4:salt" + len(salt) + ":" + salt + "3:seqi" + seq + "e1:v" + len(v) + ":" + v. Current sign_mutable_data uses raw salt + seq.to_bytes(8) + data. Verify against BEP 44 test vector (seq=1, v="Hello World!") and fix if needed. | Lines 184–186 (message construction). |
| 2 | If changed, update verify_mutable_data_signature to use same buffer format. | Lines 243–244. |

**Line-level subtasks (Activity 4.2):**

- **dht_storage.py sign_mutable_data:** Build message per BEP 44: if salt: msg = b"4:salt" + str(len(salt)).encode() + b":" + salt; else msg = b""; msg += b"3:seqi" + str(seq).encode() + b"e1:v" + str(len(data)).encode() + b":" + data. Sign message.
- **dht_storage.py verify_mutable_data_signature:** Same message construction; then verify.

---

## Project 5: Configuration and feature flag

**Goal:** Gate BEP 44 network behavior with `dht_enable_storage`; respect read-only and size limits.

### Activity 5.1: Config and gating

**File:** `ccbt/discovery/dht.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Before any network get/put, check `get_config().discovery.dht_enable_storage`. If False, keep current local-only behavior. | get_data, put_data. |
| 2 | Respect BEP 43 read_only: do not send put, do not store incoming put (or store but do not announce). | Already skip put_data when read_only; keep. |
| 3 | Use config dht_storage_ttl and dht_max_storage_size (1000) when encoding and when accepting incoming put. | dht_storage.py already has MAX_STORAGE_VALUE_SIZE; wire config. |

**File:** `ccbt/config/config.py` / `ccbt/models.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Ensure dht_enable_storage, dht_storage_ttl, dht_max_storage_size are defined and mapped from env. | Already present; verify. |

---

## Project 6: BEP 51 indexing over real BEP 44

**Goal:** BEP 51 index storage/query uses the new iterative put/get so index entries are visible across the swarm.

### Activity 6.1: dht_indexing to use network put/get

**File:** `ccbt/discovery/dht_indexing.py`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | store_infohash_sample already calls dht_client.put_data(index_key, encoded_bytes). No change needed once put_data in dht.py does iterative put. | Verify that index_key is 20 bytes and format is mutable (already uses DHTMutableData and sign_mutable_data). |
| 2 | query_index currently calls dht_client.get_data(index_key). Once get_data does iterative get, it will automatically use the network. Ensure index key is calculated from query string (already) and public_key is passed for mutable get. | query_index: pass public_key to get_data if mutable. |

**Line-level subtasks (Activity 6.1):**

- **dht_indexing.py store_infohash_sample:** No code change; rely on dht.put_data doing network put when dht_enable_storage is True.
- **dht_indexing.py query_index:** When calling dht_client.get_data(index_key), pass public_key for mutable verification (get_data(key, public_key)).

---

## Project 7: Tests and documentation

**Goal:** Unit and integration tests for get/put; update docs to reflect BEP 44 behavior.

### Activity 7.1: Unit tests

**Files:** `tests/unit/discovery/test_dht_bep44.py` (new), `tests/unit/discovery/test_dht_storage.py` (existing or new)

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Test _parse_get_response: valid immutable response, valid mutable response, missing token, invalid format. | New test file. |
| 2 | Test _query_node_for_get with mock _send_query: correct args, response parsing. | Mock transport and _send_query. |
| 3 | Test _get_data_iterative with mock nodes: no nodes, one node returns value, token stored. | Mock routing table and _query_node_for_get. |
| 4 | Test _send_put: immutable and mutable message format; error response handling. | Mock transport. |
| 5 | Test put_data/get_data with dht_enable_storage=False: only local store. With True and mock iterative: network called. | Mock config and _put_data_iterative/_get_data_iterative. |
| 6 | Test dht_storage sign/verify with BEP 44 test vector (mutable, seq=1, v="Hello World!"). | test_dht_storage.py. |

### Activity 7.2: Integration tests

**File:** `tests/integration/test_dht_enhancements_integration.py` (existing) or new

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Two DHT nodes; node A puts (immutable and mutable); node B gets. Verify value and token. | Use real UDP sockets or in-process mocks. |
| 2 | XET: announce_chunk on node A; find_chunk_peers on node B (with BEP 44 enabled). Expect peers when both use network get/put. | Requires full DHT + XET setup. |

### Activity 7.3: Documentation

**Files:** `docs/en/bep_xet.md`, `docs/bep44.md` (new), `.cursor/rules/dht-patterns.mdc`

| # | Task | Location / notes |
|---|------|------------------|
| 1 | Add docs/bep44.md: BEP 44 summary, key derivation, get/put flow, config options, XET usage. | New file. |
| 2 | Update docs/en/bep_xet.md: DHT (BEP 44) section to state that when dht_enable_storage is True, chunk metadata is stored in and retrieved from the DHT network; link to bep44.md. | Existing section on DHT integration. |
| 3 | Update dht-patterns.mdc: Storage (BEP 44) subsection to describe iterative get/put and server-side handling. | Storage (BEP 44) bullet list. |

---

## Dependency order (critical path)

1. **Project 4.2** (sign/verify format) — do first so keys and signatures are correct.
2. **Project 1** (iterative get) — required for token collection and for get_data.
3. **Project 2.1–2.2** (tokens, send put) — then **Activity 2.3–2.4** (iterative put, put_data integration).
4. **Project 4.1** (XET key strategy) — can be done in parallel with 2; required for store_chunk_hash/get_chunk_peers.
5. **Project 3** (server get/put) — can be done after client get/put.
6. **Project 5** (config) — wire throughout.
7. **Project 6** (BEP 51) — verification only once put_data/get_data are done.
8. **Project 7** (tests and docs) — ongoing.

---

## File-level task summary

| File | Tasks |
|------|--------|
| `ccbt/discovery/dht.py` | Add _storage_tokens; _query_node_for_get; _parse_get_response; _get_data_iterative; get_data integration; _get_storage_tokens_for_key; _send_put; _put_data_iterative; put_data and store_chunk_hash integration; handle_datagram and _handle_request; _handle_get_request; _handle_put_request; _xet_chunk_dht_key; cleanup _storage_tokens; XET mutable key in store_chunk_hash/get_chunk_peers. |
| `ccbt/discovery/dht_storage.py` | Fix sign/verify message format to match BEP 44 test vector. |
| `ccbt/discovery/dht_indexing.py` | query_index: pass public_key to get_data. |
| `ccbt/discovery/xet_cas.py` | Ensure key_manager/public_key available for DHT; optional pass-through for get_chunk_peers. |
| `ccbt/config/config.py` / `ccbt/models.py` | Verify dht_enable_storage, TTL, max size. |
| `tests/unit/discovery/test_dht_bep44.py` | New unit tests for get/put parsing and iterative logic. |
| `tests/unit/discovery/test_dht_storage.py` | BEP 44 test vector for sign/verify. |
| `tests/integration/test_dht_enhancements_integration.py` | Integration tests for put/get and XET. |
| `docs/bep44.md` | New BEP 44 implementation note. |
| `docs/en/bep_xet.md` | Update DHT section. |
| `.cursor/rules/dht-patterns.mdc` | Update Storage (BEP 44) subsection. |

---

## Line-level subtask summary (key locations in dht.py)

- **~523:** Add `self._storage_tokens` and (for server) `self._storage_write_tokens`.
- **~989:** Add `_query_node_for_get(node, key, public_key, seq)`.
- **~1539:** `get_data`: add iterative get when dht_enable_storage; keep local fallback.
- **~1561:** `put_data`: add iterative put when dht_enable_storage and not read_only; keep local store.
- **~1615:** `store_chunk_hash`: use 20-byte key (chunk_hash[:20] or mutable key); ensure mutable format and seq/signature.
- **~1635:** `get_chunk_peers`: use key = _xet_chunk_dht_key(chunk_hash); get_data(key, public_key).
- **~1841:** `handle_response` → `handle_datagram`; dispatch y="q" to _handle_request.
- **New:** _handle_request; _handle_get_request; _handle_put_request; _get_data_iterative; _put_data_iterative; _send_put; _get_storage_tokens_for_key; _parse_get_response; _xet_chunk_dht_key.
- **~1942:** _cleanup_old_data: expire _storage_tokens (and _storage_write_tokens).

This plan is complete at project, activity, file-level, and line-level granularity and can be used to implement BEP 44 put_mutable/get_mutable end-to-end.
