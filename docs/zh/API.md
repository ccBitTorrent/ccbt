# ccBT API 参考

ccBitTorrent 的完整 API 文档，包含实际实现文件的引用。

## 入口点

### 主入口点 (ccbt)

用于基本 torrent 操作的主命令行入口点。

实现: [ccbt/__main__.py:main](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L18)

功能:
- 单 torrent 下载模式
- 守护进程模式用于多 torrent 会话: [ccbt/__main__.py:52](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L52)
- Magnet URI 支持: [ccbt/__main__.py:73](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L73)
- Tracker 公告: [ccbt/__main__.py:89](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L89)

入口点配置: [pyproject.toml:79](https://github.com/ccBitTorrent/ccbt/blob/main/pyproject.toml#L79)

### 异步下载助手

用于高级操作的高性能异步助手和下载管理器。

实现: [ccbt/session/download_manager.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/download_manager.py)

主要导出:
- `AsyncDownloadManager`
- `download_torrent()`
- `download_magnet()`

### AsyncDownloadManager

用于单个 torrent 的高性能异步下载管理器。

实现: [ccbt/session/download_manager.py:AsyncDownloadManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/download_manager.py)

方法:
- `__init__()`: [ccbt/session/async_main.py:41](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L41) - 使用 torrent 数据初始化
- `start()`: [ccbt/session/async_main.py:110](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L110) - 启动下载管理器
- `stop()`: [ccbt/session/async_main.py:115](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L115) - 停止下载管理器
- `start_download()`: [ccbt/session/async_main.py:122](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L122) - 与对等节点开始下载

功能:
- 通过 AsyncPeerConnectionManager 进行对等连接管理: [ccbt/session/async_main.py:127](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L127)
- 通过 AsyncPieceManager 进行片段管理: [ccbt/session/async_main.py:94](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L94)
- 事件回调系统: [ccbt/session/async_main.py:103](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L103)

## 核心模块

### Torrent 解析和元数据

#### TorrentParser

解析 BitTorrent torrent 文件并提取元数据。

::: ccbt.core.torrent.TorrentParser
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**主要方法:**

- `parse()`: [ccbt/core/torrent.py:34](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/torrent.py#L34) - 从路径或 URL 解析 torrent 文件
- `_validate_torrent()`: [ccbt/core/torrent.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/torrent.py) - 验证 torrent 结构
- `_extract_torrent_data()`: [ccbt/core/torrent.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/torrent.py) - 提取和处理 torrent 数据

#### Bencode 编码/解码

BitTorrent 协议的 Bencode 编解码器 (BEP 3)。

**类:**

- `BencodeDecoder`: [ccbt/core/bencode.py:BencodeDecoder](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L24) - Bencode 数据解码器
- `BencodeEncoder`: [ccbt/core/bencode.py:BencodeEncoder](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L156) - Python 对象到 bencode 的编码器

**函数:**
- `decode()`: [ccbt/core/bencode.py:decode](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L221) - 将 bencode 字节解码为 Python 对象
- `encode()`: [ccbt/core/bencode.py:encode](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L227) - 将 Python 对象编码为 bencode 格式

**支持的类型:**
- 整数: `i<数字>e`
- 字符串: `<长度>:<数据>`
- 列表: `l<项目>e`
- 字典: `d<键值对>e`

**异常:**
- `BencodeDecodeError`: [ccbt/core/bencode.py:BencodeDecodeError](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L16) - 解码错误
- `BencodeEncodeError`: [ccbt/core/bencode.py:BencodeEncodeError](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L20) - 编码错误

#### Magnet URI 解析

解析 Magnet URI (BEP 9)，支持 BEP 53 文件选择。

**函数:**
- `parse_magnet()`: [ccbt/core/magnet.py:parse_magnet](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/magnet.py#L178) - 解析 magnet URI 并提取组件

**数据模型:**
- `MagnetInfo`: [ccbt/core/magnet.py:MagnetInfo](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/magnet.py#L17) - 支持 BEP 53 的 Magnet 信息数据模型

**功能:**
- Info hash 提取: [ccbt/core/magnet.py:_hex_or_base32_to_bytes](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/magnet.py#L28) - 支持十六进制 (40 字符) 和 base32 (32 字符)
- Tracker URL: 提取 `tr` 参数
- Web seeds: 提取 `ws` 参数
- BEP 53 文件选择: [ccbt/core/magnet.py:_parse_index_list](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/magnet.py#L40) - 解析 `so` (已选择) 和 `x.pe` (优先) 参数
- 显示名称: 提取 `dn` 参数

**辅助函数:**
- `build_minimal_torrent_data()`: [ccbt/core/magnet.py:build_minimal_torrent_data](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/magnet.py) - 从 magnet 信息构建最小 torrent
- `build_torrent_data_from_metadata()`: [ccbt/core/magnet.py:build_torrent_data_from_metadata](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/magnet.py) - 从元数据交换构建 torrent

## 会话管理

### AsyncSessionManager

用于多个 torrent 的高性能异步会话管理器。

::: ccbt.session.session.AsyncSessionManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

#### 初始化

构造函数: [ccbt/session/session.py:608](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L608)

--8<-- "ccbt/session/session.py:608:620"

#### 生命周期方法

- `start()`: [ccbt/session/session.py:637](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L637) - 启动异步会话管理器

  --8<-- "ccbt/session/session.py:637:655"

- `stop()`: [ccbt/session/session.py:657](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L657) - 停止异步会话管理器

  --8<-- "ccbt/session/session.py:657:682"

#### Torrent 管理

- `add_torrent()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 添加 torrent 文件
- `add_magnet()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 添加 magnet 链接
- `remove()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 移除 torrent
- `pause_torrent()`: [ccbt/session/session.py:684](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L684) - 暂停 torrent
- `resume_torrent()`: [ccbt/session/session.py:701](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L701) - 恢复 torrent
- `set_rate_limits()`: [ccbt/session/session.py:715](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L715) - 设置每个 torrent 的速率限制

#### 状态和监控

- `get_global_stats()`: [ccbt/session/session.py:739](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L739) - 聚合全局统计信息
- `get_status()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 获取所有或特定 torrent 的状态
- `get_peers_for_torrent()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 获取 torrent 的对等节点

#### 高级操作

- `force_announce()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 强制 tracker 公告
- `force_scrape()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 强制 tracker 抓取
- `refresh_pex()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 刷新对等节点交换
- `rehash_torrent()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 重新哈希 torrent
- `export_session_state()`: [ccbt/session/session.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 导出会话状态

### AsyncTorrentSession

表示单个活动 torrent 生命周期的单个 torrent 会话，具有异步操作。

::: ccbt.session.session.AsyncTorrentSession
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**主要方法:**

- `start()`: [ccbt/session/session.py:start](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L400) - 启动 torrent 会话，初始化下载管理器、tracker 和 PEX
- `stop()`: [ccbt/session/session.py:stop](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L678) - 停止 torrent 会话，保存检查点，清理资源
- `pause()`: [ccbt/session/session.py:pause](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 暂停下载
- `resume()`: [ccbt/session/session.py:resume](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 恢复下载
- `get_status()`: [ccbt/session/session.py:get_status](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - 获取 torrent 状态

**组件:**
- `download_manager`: [ccbt/session/session.py:78](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L78) - 用于片段管理的 AsyncDownloadManager
- `file_selection_manager`: [ccbt/session/session.py:86](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L86) - 用于多文件 torrent 的 FileSelectionManager
- `piece_manager`: [ccbt/session/session.py:92](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L92) - 用于片段选择的 AsyncPieceManager
- `checkpoint_manager`: [ccbt/session/session.py:102](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L102) - 用于恢复功能的 CheckpointManager

**数据模型:** [ccbt/session/session.py:TorrentSessionInfo](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L47)

## 对等节点管理

### Peer

表示对等节点连接。

实现: [ccbt/peer/peer.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/peer/peer.py)

属性和方法:
- 对等节点信息: IP、端口、对等节点 ID、客户端标识
- 连接状态: 已连接、阻塞、感兴趣
- 传输速率: 下载/上传速度

### AsyncPeerConnectionManager

管理多个对等节点连接，具有连接池和生命周期管理。

::: ccbt.peer.async_peer_connection.AsyncPeerConnectionManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

## 片段管理

### AsyncPieceManager

具有最稀有优先和终局模式的高级片段选择。

::: ccbt.piece.async_piece_manager.AsyncPieceManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**功能:**
- 最稀有优先片段选择
- 顺序片段选择
- 轮询片段选择
- 具有重复请求的终局模式
- 文件选择集成: [ccbt/piece/async_piece_manager.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py#L308) - 根据文件选择状态过滤片段

**配置:** [ccbt.toml:99-114](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt.toml#L99-L114)

## 配置

### ConfigManager

具有热重载、分层加载和验证的配置管理。

::: ccbt.config.config.ConfigManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**功能:**
- 配置加载: [ccbt/config/config.py:_load_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L76)
- 文件发现: [ccbt/config/config.py:_find_config_file](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L55)
- 环境变量解析: [ccbt/config/config.py:_get_env_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py)
- 热重载支持: [ccbt/config/config.py:ConfigManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L40)
- CLI 覆盖: [ccbt/cli/overrides.py:apply_cli_overrides](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/overrides.py)

**配置优先级:**
1. 来自 `ccbt/models.py:Config` 的默认值
2. 配置文件（当前目录中的 `ccbt.toml` 或 `~/.config/ccbt/ccbt.toml`）
3. 环境变量（`CCBT_*` 前缀）
4. CLI 参数（通过 `apply_cli_overrides()`）
5. 每个 torrent 的默认值
6. 每个 torrent 的覆盖

**使用示例:**
```python
from ccbt.config.config import ConfigManager, get_config, init_config

# 初始化配置
config_manager = init_config()

# 获取当前配置
config = get_config()

# 访问配置部分
network_config = config.network
disk_config = config.disk
```

## 更多资源

- [入门指南](getting-started.md) - 快速入门指南
- [配置指南](configuration.md) - 详细配置
- [性能调优](performance.md) - 性能优化
- [Bitonic 指南](bitonic.md) - 终端仪表板
- [btbt CLI 参考](btbt-cli.md) - CLI 文档
- [BEP 52: 协议 v2](bep52.md) - BitTorrent 协议 v2 指南

