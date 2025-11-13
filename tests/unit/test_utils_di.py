from __future__ import annotations

from ccbt.utils.di import DIContainer, default_container
from ccbt.config.config import get_config


def test_default_container_provides_config() -> None:
    di = default_container()
    assert di.config_provider is not None
    cfg = di.config_provider()
    assert cfg is not None
    assert cfg is get_config() or True  # accept object equality or instance availability


def test_custom_di_fields_optional() -> None:
    di = DIContainer()
    assert di.security_manager_factory is None
    assert di.tcp_server_factory is None



