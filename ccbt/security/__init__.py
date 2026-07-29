"""Security enhancements for ccBitTorrent.

from __future__ import annotations

Provides comprehensive security features including:
- Peer validation and reputation system
- Rate limiting and DDoS protection
- Malicious behavior detection
- MSE/PE (BEP 3) peer traffic obfuscation / interop (not peer authentication)
- IP blacklist/whitelist management
"""

from ccbt.security.anomaly_detector import AnomalyDetector
from ccbt.security.encryption import EncryptionManager
from ccbt.security.ip_filter import FilterMode, IPFilter, IPFilterRule
from ccbt.security.peer_validator import PeerValidator
from ccbt.security.rate_limiter import RateLimiter
from ccbt.security.security_manager import SecurityManager
from ccbt.security.swarm_auth_policy import (
    SWARM_AUTH_DISCOVERY_SUPPRESSED_TOTAL,
    SWARM_AUTH_METRIC_BY_MODE,
    SWARM_AUTH_METRIC_REASONS,
    SWARM_AUTH_METRIC_TOTAL,
    SWARM_AUTH_OPPORTUNISTIC_VERIFY_FAILED_TOTAL,
    SWARM_AUTH_REJECTION_REASON_LABEL,
    SWARM_AUTH_REVOCATION_HITS_TOTAL,
    SWARM_AUTH_STRICT_LTEP_TIMEOUT_TOTAL,
    SWARM_AUTH_TRUSTSTORE_RELOAD_TOTAL,
    AuthDecision,
    SwarmAuthPolicy,
    evaluate_inbound_admission,
    evaluate_outbound_admission,
)
from ccbt.security.swarm_certificate_binding import (
    CertificateBindingDecision,
    evaluate_certificate_binding,
)
from ccbt.security.swarm_revocation import (
    SwarmRevocationCache,
    SwarmRevocationProfile,
    allow_after_parse_failure,
    load_swarm_revocation_cache,
    load_swarm_revocation_profile,
    parse_swarm_revocation_payload,
)
from ccbt.security.swarm_trust_store import (
    SUPPORTED_ANCHOR_TYPES,
    SwarmTrustAnchor,
    SwarmTrustStore,
    current_swarm_anchors,
    load_swarm_trust_store,
    merge_swarm_anchor_maps,
    parse_swarm_trust_store,
)

__all__ = [
    "SUPPORTED_ANCHOR_TYPES",
    "SWARM_AUTH_DISCOVERY_SUPPRESSED_TOTAL",
    "SWARM_AUTH_METRIC_BY_MODE",
    "SWARM_AUTH_METRIC_REASONS",
    "SWARM_AUTH_METRIC_TOTAL",
    "SWARM_AUTH_OPPORTUNISTIC_VERIFY_FAILED_TOTAL",
    "SWARM_AUTH_REJECTION_REASON_LABEL",
    "SWARM_AUTH_REVOCATION_HITS_TOTAL",
    "SWARM_AUTH_STRICT_LTEP_TIMEOUT_TOTAL",
    "SWARM_AUTH_TRUSTSTORE_RELOAD_TOTAL",
    "AnomalyDetector",
    "AuthDecision",
    "CertificateBindingDecision",
    "EncryptionManager",
    "FilterMode",
    "IPFilter",
    "IPFilterRule",
    "PeerValidator",
    "RateLimiter",
    "SecurityManager",
    "SwarmAuthPolicy",
    "SwarmRevocationCache",
    "SwarmRevocationProfile",
    "SwarmTrustAnchor",
    "SwarmTrustStore",
    "allow_after_parse_failure",
    "current_swarm_anchors",
    "evaluate_certificate_binding",
    "evaluate_inbound_admission",
    "evaluate_outbound_admission",
    "load_swarm_revocation_cache",
    "load_swarm_revocation_profile",
    "load_swarm_trust_store",
    "merge_swarm_anchor_maps",
    "parse_swarm_revocation_payload",
    "parse_swarm_trust_store",
]
