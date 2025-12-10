# Dependency Injection in ccBitTorrent

The `ccbt.utils.di.DIContainer` provides optional factories for wiring core services (security manager, DHT, NAT, TCP server, etc.). All DI is optional and non-breaking. When DI is not provided, the code falls back to the existing constructions using `get_config()` and concrete classes.

## Quick start

```python
from ccbt.utils.di import DIContainer
from ccbt.session.session import AsyncSessionManager

di = DIContainer(
    # security_manager_factory=lambda: MySecurityManager(),
    # dht_client_factory=lambda **kw: MyDHTClient(**kw),
    # tcp_server_factory=lambda session, config: MyTCPServer(session, config),
)

session = AsyncSessionManager(output_dir=".", di=di)
await session.start()
```

## Notes

- The canonical session manager is `ccbt.session.session.AsyncSessionManager`. The legacy `ccbt.session.async_main` module has been removed; use the canonical manager instead.
- Utilities added under `ccbt.utils` include: `backoff`, `tasks`, `bitfield`, `tracker_utils`, `dht_utils`, `metadata_utils`, and `time`.


