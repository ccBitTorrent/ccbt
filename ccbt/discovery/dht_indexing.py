"""DHT Infohash Indexing (BEP 51).

Provides support for indexing infohashes in the DHT,
enabling efficient torrent discovery without downloading metadata first.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ccbt.discovery.dht_storage import (
    DHTMutableData,
    sign_mutable_data,
    verify_mutable_data_signature,
)

if TYPE_CHECKING:
    from ccbt.discovery.dht import AsyncDHTClient

logger = logging.getLogger(__name__)


@dataclass
class DHTInfohashSample:
    """Infohash sample for indexing (BEP 51)."""

    info_hash: bytes
    name: str
    size: int
    created_time: float = field(default_factory=time.time)


@dataclass
class DHTIndexEntry:
    """Index entry containing multiple infohash samples (BEP 51)."""

    samples: list[DHTInfohashSample] = field(default_factory=list)
    updated_time: float = field(default_factory=time.time)


def calculate_index_key(query: str) -> bytes:
    """Calculate index key from query string (BEP 51).

    Args:
        query: Query string (e.g., torrent name)

    Returns:
        20-byte index key (SHA-1 hash of normalized query)

    """
    # Normalize query: lowercase and strip whitespace
    normalized = query.lower().strip()

    # BEP 51: key = SHA-1(query)
    # Note: SHA-1 is required by BEP 51 specification
    digest = hashlib.sha1()  # nosec B324 - Required by BEP 51 spec
    digest.update(normalized.encode("utf-8"))
    return digest.digest()


async def store_infohash_sample(
    info_hash: bytes,
    name: str,
    size: int,
    public_key: bytes,
    private_key: bytes,
    salt: bytes = b"",
    dht_client: AsyncDHTClient | None = None,
) -> bytes:
    """Store an infohash sample in the index (BEP 51) using BEP 44.

    Args:
        info_hash: Torrent info hash (20 bytes)
        name: Torrent name
        size: Torrent size in bytes
        public_key: Public key for signing
        private_key: Private key for signing
        salt: Optional salt
        dht_client: Optional DHT client instance. If None, will attempt to get
            from global DHT client singleton.

    Returns:
        Index key (20 bytes)

    Raises:
        ValueError: If parameters are invalid
        RuntimeError: If DHT client is not available and cannot be obtained

    """
    if len(info_hash) != 20:
        msg = f"Info hash must be 20 bytes, got {len(info_hash)}"
        raise ValueError(msg)

    # Calculate index key from name
    index_key = calculate_index_key(name)

    # Get DHT client if not provided
    if dht_client is None:
        try:
            from ccbt.discovery.dht import get_dht_client

            dht_client = get_dht_client()
        except Exception as e:
            logger.warning(
                "Could not get DHT client for index storage: %s. Returning index key only.",
                e,
            )
            # Return key even if storage fails (backward compatibility)
            return index_key

    # Create index entry structure
    sample = DHTInfohashSample(
        info_hash=info_hash,
        name=name,
        size=size,
    )

    # Try to get existing entry to update it
    existing_entry = None
    seq = 0
    try:
        existing_data = await dht_client.get_data(index_key, public_key=public_key)
        if existing_data:
            from ccbt.discovery.dht_storage import (
                DHTMutableData,
                DHTStorageKeyType,
                decode_storage_value,
            )

            decoded = decode_storage_value(existing_data, DHTStorageKeyType.MUTABLE)
            if isinstance(decoded, DHTMutableData):
                existing_entry = decode_index_entry(decoded)
                seq = decoded.seq + 1  # Increment sequence for update
    except Exception as e:
        logger.debug("Could not retrieve existing index entry: %s", e)
        # Continue with new entry

    # Update index entry with new sample
    updated_entry = update_index_entry(
        index_key,
        sample,
        existing_entry,
        max_samples=8,  # Default max samples per entry
    )

    # Sign entry with DHT node's private key
    mutable_data = encode_index_entry(
        updated_entry,
        public_key,
        private_key,
        seq,
        salt,
    )

    # Store via DHT put_mutable() using BEP 44
    try:
        from ccbt.discovery.dht_storage import encode_storage_value

        encoded_value = encode_storage_value(mutable_data)
        success_count = await dht_client.put_data(index_key, encoded_value)
        if success_count > 0:
            logger.debug(
                "Stored infohash sample in DHT index: key=%s, name=%s",
                index_key.hex()[:16],
                name,
            )
        else:
            logger.warning(
                "Failed to store infohash sample in DHT: no nodes accepted the value"
            )
    except Exception as e:
        logger.warning(
            "Failed to store infohash sample via BEP 44: %s. Returning index key only.",
            e,
        )
        # Return key even if storage fails (backward compatibility)

    return index_key


async def query_index(
    query: str,
    max_results: int = 50,
    dht_client: AsyncDHTClient | None = None,
    public_key: bytes | None = None,
) -> list[DHTInfohashSample]:
    """Query the index for matching infohash samples (BEP 51) using BEP 44.

    Args:
        query: Query string (e.g., torrent name)
        max_results: Maximum number of results to return
        dht_client: Optional DHT client instance. If None, will attempt to get
            from global DHT client singleton.
        public_key: Optional public key for querying mutable items. If None,
            will attempt to get from DHT node.

    Returns:
        List of matching infohash samples, sorted by relevance (exact match >
        prefix match > substring match). Returns empty list on failure.

    Note:
        This implements BEP 44 get_mutable() query to retrieve index entries
        from the DHT network.

    """
    # Get DHT client if not provided
    if dht_client is None:
        try:
            from ccbt.discovery.dht import get_dht_client

            dht_client = get_dht_client()
        except Exception as e:
            logger.warning("Could not get DHT client for index query: %s", e)
            return []

    # Calculate index key from query string
    index_key = calculate_index_key(query)

    # Get public key if not provided (needed for mutable item queries)
    if public_key is None:
        # Try to get from DHT node's key pair
        # This is a simplified approach - in practice, the public key should
        # be provided or retrieved from the DHT node configuration
        logger.debug("No public key provided for index query, attempting query anyway")

    # Query DHT using get_mutable() with timeout
    try:
        import asyncio

        # Wrap DHT query in timeout (10 seconds)
        existing_data = await asyncio.wait_for(
            dht_client.get_data(index_key, public_key=public_key),
            timeout=10.0,
        )

        if not existing_data:
            logger.debug("No index entry found for query: %s", query)
            return []

        # Decode retrieved mutable data
        from ccbt.discovery.dht_storage import (
            DHTMutableData,
            DHTStorageKeyType,
            decode_storage_value,
        )

        decoded = decode_storage_value(existing_data, DHTStorageKeyType.MUTABLE)
        if not isinstance(decoded, DHTMutableData):
            logger.debug("Retrieved data is not a mutable DHT item")
            return []

        # Decode index entry
        index_entry = decode_index_entry(decoded)

        # Extract samples from decoded entry
        samples = index_entry.samples

        # Filter samples by query string (name matching)
        query_lower = query.lower().strip()
        matching_samples: list[tuple[int, DHTInfohashSample]] = []

        for sample in samples:
            name_lower = sample.name.lower()
            # Calculate relevance score: exact match = 3, prefix = 2, substring = 1
            if name_lower == query_lower:
                relevance = 3  # Exact match
            elif name_lower.startswith(query_lower):
                relevance = 2  # Prefix match
            elif query_lower in name_lower:
                relevance = 1  # Substring match
            else:
                continue  # No match, skip

            matching_samples.append((relevance, sample))

        # Sort by relevance (descending) and limit to max_results
        matching_samples.sort(key=lambda x: x[0], reverse=True)
        results = [sample for _, sample in matching_samples[:max_results]]

        logger.debug(
            "Found %d matching samples for query '%s' (from %d total samples)",
            len(results),
            query,
            len(samples),
        )

        return results

    except asyncio.TimeoutError:
        logger.warning("DHT query timeout for index key: %s", index_key.hex()[:16])
        return []
    except Exception as e:
        logger.warning("Failed to query DHT index: %s", e)
        return []


def update_index_entry(
    key: bytes,  # noqa: ARG001
    sample: DHTInfohashSample,
    existing_entry: DHTIndexEntry | None = None,
    max_samples: int = 8,
) -> DHTIndexEntry:
    """Update an index entry with a new sample (BEP 51).

    Args:
        key: Index key (currently unused, reserved for future use)
        sample: New sample to add
        existing_entry: Existing index entry (if any)
        max_samples: Maximum samples per index entry

    Returns:
        Updated index entry

    """
    if existing_entry is None:
        existing_entry = DHTIndexEntry()

    # Add sample if not already present
    existing_hashes = {s.info_hash for s in existing_entry.samples}
    if sample.info_hash not in existing_hashes:
        existing_entry.samples.append(sample)

    # Limit to max_samples (keep most recent)
    if len(existing_entry.samples) > max_samples:
        # Sort by created_time, keep most recent
        existing_entry.samples.sort(key=lambda s: s.created_time, reverse=True)
        existing_entry.samples = existing_entry.samples[:max_samples]

    existing_entry.updated_time = time.time()
    return existing_entry


def encode_index_entry(
    entry: DHTIndexEntry,
    public_key: bytes,
    private_key: bytes,
    seq: int,
    salt: bytes = b"",
) -> DHTMutableData:
    """Encode index entry for storage (BEP 51, uses BEP 44).

    Args:
        entry: Index entry to encode
        public_key: Public key for signing
        private_key: Private key for signing
        seq: Sequence number
        salt: Optional salt

    Returns:
        Mutable data ready for BEP 44 storage

    Raises:
        ValueError: If encoding fails

    """
    from ccbt.core.bencode import BencodeEncoder

    # Encode samples as list of dictionaries
    samples_data = [
        {
            b"h": sample.info_hash,
            b"n": sample.name.encode("utf-8"),
            b"s": sample.size,
            b"t": int(sample.created_time),
        }
        for sample in entry.samples
    ]

    entry_data = {
        b"samples": samples_data,
        b"updated": int(entry.updated_time),
    }

    # Bencode the data
    data_bytes = BencodeEncoder().encode(entry_data)

    # Sign the data
    signature = sign_mutable_data(
        data_bytes,
        public_key,
        private_key,
        seq,
        salt,
    )

    return DHTMutableData(
        data=data_bytes,
        public_key=public_key,
        seq=seq,
        signature=signature,
        salt=salt,
    )


def decode_index_entry(
    mutable_data: DHTMutableData,
) -> DHTIndexEntry:
    """Decode index entry from stored data (BEP 51, uses BEP 44).

    Args:
        mutable_data: Mutable data from BEP 44 storage

    Returns:
        Decoded index entry

    Raises:
        ValueError: If decoding fails or signature is invalid

    """
    from ccbt.core.bencode import BencodeDecoder

    # Verify signature
    if not verify_mutable_data_signature(
        mutable_data.data,
        mutable_data.public_key,
        mutable_data.signature,
        mutable_data.seq,
        mutable_data.salt,
    ):
        msg = "Invalid signature in index entry"
        raise ValueError(msg)

    # Decode bencoded data
    decoder = BencodeDecoder(mutable_data.data)
    entry_data = decoder.decode()

    # Decode samples
    samples = []
    samples_list = entry_data.get(b"samples", [])
    for sample_data in samples_list:
        if not isinstance(sample_data, dict):
            continue

        info_hash = sample_data.get(b"h")
        name_bytes = sample_data.get(b"n", b"")
        size = sample_data.get(b"s", 0)
        created_time = sample_data.get(b"t", time.time())

        if info_hash and len(info_hash) == 20:
            try:
                name = (
                    name_bytes.decode("utf-8")
                    if isinstance(name_bytes, bytes)
                    else str(name_bytes)
                )
                sample = DHTInfohashSample(
                    info_hash=info_hash,
                    name=name,
                    size=size,
                    created_time=float(created_time),
                )
                samples.append(sample)
            except Exception as e:
                logger.debug("Failed to decode sample: %s", e)

    updated_time = entry_data.get(b"updated", time.time())

    return DHTIndexEntry(
        samples=samples,
        updated_time=float(updated_time),
    )
