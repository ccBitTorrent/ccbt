# 示例

本节提供使用 ccBitTorrent 的实用示例和代码示例。

## 配置示例

### 基本配置

用于开始的最小配置文件：

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

完整的基本配置请参阅 [example-config-basic.toml](examples/example-config-basic.toml)。

### 高级配置

适用于需要精细控制的高级用户：

高级配置选项请参阅 [example-config-advanced.toml](examples/example-config-advanced.toml)。

### 性能配置

为最大性能优化的设置：

性能调优请参阅 [example-config-performance.toml](examples/example-config-performance.toml)。

### 安全配置

具有加密和验证的安全优先配置：

安全设置请参阅 [example-config-security.toml](examples/example-config-security.toml)。

## BEP 52 示例

### 创建 v2 Torrent

创建 BitTorrent v2 torrent 文件：

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# 创建 v2 torrent
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # 16KB 片段
)
```

完整示例请参阅 [create_v2_torrent.py](examples/bep52/create_v2_torrent.py)。

### 创建混合 Torrent

创建可在 v1 和 v2 客户端上工作的混合 torrent：

完整示例请参阅 [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py)。

### 解析 v2 Torrent

解析并检查 BitTorrent v2 torrent 文件：

完整示例请参阅 [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py)。

### 协议 v2 会话

在会话中使用 BitTorrent v2 协议：

完整示例请参阅 [protocol_v2_session.py](examples/bep52/protocol_v2_session.py)。

## 入门

有关开始使用 ccBitTorrent 的更多信息，请参阅 [入门指南](getting-started.md)。






本节提供使用 ccBitTorrent 的实用示例和代码示例。

## 配置示例

### 基本配置

用于开始的最小配置文件：

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

完整的基本配置请参阅 [example-config-basic.toml](examples/example-config-basic.toml)。

### 高级配置

适用于需要精细控制的高级用户：

高级配置选项请参阅 [example-config-advanced.toml](examples/example-config-advanced.toml)。

### 性能配置

为最大性能优化的设置：

性能调优请参阅 [example-config-performance.toml](examples/example-config-performance.toml)。

### 安全配置

具有加密和验证的安全优先配置：

安全设置请参阅 [example-config-security.toml](examples/example-config-security.toml)。

## BEP 52 示例

### 创建 v2 Torrent

创建 BitTorrent v2 torrent 文件：

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# 创建 v2 torrent
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # 16KB 片段
)
```

完整示例请参阅 [create_v2_torrent.py](examples/bep52/create_v2_torrent.py)。

### 创建混合 Torrent

创建可在 v1 和 v2 客户端上工作的混合 torrent：

完整示例请参阅 [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py)。

### 解析 v2 Torrent

解析并检查 BitTorrent v2 torrent 文件：

完整示例请参阅 [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py)。

### 协议 v2 会话

在会话中使用 BitTorrent v2 协议：

完整示例请参阅 [protocol_v2_session.py](examples/bep52/protocol_v2_session.py)。

## 入门

有关开始使用 ccBitTorrent 的更多信息，请参阅 [入门指南](getting-started.md)。
































































































































































































