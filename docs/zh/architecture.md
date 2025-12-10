# 架构概述

本文档提供了ccBitTorrent的架构、组件和数据流的技术概述。

## 入口点

ccBitTorrent为不同的用例提供多个入口点：

1. **基本CLI (`ccbt`)**：用于单个种子下载的简单命令行界面
   - 入口点：`ccbt/__main__.py:main`
   - 用法：`python -m ccbt torrent.torrent` 或 `python -m ccbt "magnet:..."`

2. **异步CLI (`ccbt async`)**：具有完整会话管理的高性能异步界面
   - 入口点：`ccbt/session/async_main.py:main`
   - 支持守护进程模式、多个种子和高级功能

3. **增强CLI (`btbt`)**：具有全面功能的丰富命令行界面
   - 入口点：`ccbt/cli/main.py:main`
   - 提供交互式命令、监控和高级配置

4. **终端仪表板 (`bitonic`)**：实时交互式终端仪表板（TUI）
   - 入口点：`ccbt/interface/terminal_dashboard.py:main`
   - 种子、对等节点和系统指标的实时可视化

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    ccBitTorrent Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│  CLI Interface                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Basic     │ │ Interactive │ │  Dashboard   │              │
│  │   Commands  │ │     CLI     │ │   (TUI)     │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Session Management                                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              AsyncSessionManager                           │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │ │
│  │  │   Config    │ │   Events    │ │  Checkpoint │          │ │
│  │  │  Manager    │ │   System    │ │   Manager   │          │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘          │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Core Components                                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │    Peer     │ │    Piece    │ │    Disk     │              │
│  │  Connection │ │   Manager   │ │     I/O     │              │
│  │  Manager    │ │             │ │   Manager   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Tracker   │ │     DHT     │ │  Metadata   │              │
│  │   Client    │ │   Manager   │ │  Exchange   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Network Layer                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │    TCP      │ │     UDP     │ │   WebRTC    │              │
│  │ Connections │ │  Trackers   │ │ (WebTorrent)│              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Monitoring & Observability                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Metrics   │ │   Alerts    │ │   Tracing   │              │
│  │  Collector  │ │   Manager   │ │   Manager   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 服务架构

ccBitTorrent使用面向服务的架构，具有多个核心服务：

- **PeerService**：管理对等节点连接和通信
  - 实现：`ccbt/services/peer_service.py`
  - 跟踪对等节点连接、带宽和片段统计
  
- **StorageService**：管理具有高性能分块写入的文件系统操作
  - 实现：`ccbt/services/storage_service.py`
  - 处理文件创建、数据读写操作
  
- **TrackerService**：管理跟踪器通信和健康监控
  - 实现：`ccbt/services/tracker_service.py`
  - 支持HTTP和UDP跟踪器，支持scrape（BEP 48）

所有服务都继承自基础`Service`类，该类提供生命周期管理、健康检查和状态跟踪。

**实现：** `ccbt/services/base.py`

### AsyncSessionManager

管理整个BitTorrent会话的中央编排器。有两个实现：

1. **`ccbt/session/async_main.py`中的AsyncSessionManager**：由异步CLI入口点使用，管理具有协议支持的多个种子。

`AsyncSessionManager`类在`ccbt/session/async_main.py`的第319行开始定义。关键初始化属性包括：

- `config`：配置实例（如果未提供则使用全局配置）
- `torrents`：将种子ID映射到`AsyncDownloadManager`实例的字典
- `metrics`：`MetricsCollector`实例（如果启用，在`start()`中初始化）
- `disk_io_manager`：磁盘I/O管理器（在`start()`中初始化）
- `security_manager`：安全管理器（在`start()`中初始化）
- `protocol_manager`：用于管理多个协议的`ProtocolManager`
- `protocols`：活动协议实例列表

查看完整实现：

```python
--8<-- "ccbt/session/async_main.py:319:374"
```

2. **`ccbt/session/session.py`中的AsyncSessionManager**：更全面的实现，包括DHT、队列管理、NAT遍历和scrape支持。

`ccbt/session/session.py`中更全面的`AsyncSessionManager`（从第1317行开始）包括其他组件：

- `dht_client`：用于对等节点发现的DHT客户端
- `peer_service`：用于管理对等节点连接的`PeerService`实例
- `queue_manager`：用于优先级排序的种子队列管理器
- `nat_manager`：用于端口映射的NAT遍历管理器
- `private_torrents`：跟踪私有种子的集合（BEP 27）
- `scrape_cache`：跟踪器scrape结果的缓存（BEP 48）
- 用于清理、指标收集和定期scraping的后台任务

查看完整实现：

```python
--8<-- "ccbt/session/session.py:1317:1367"
```

**职责：**
- 种子生命周期管理
- 通过`PeerService`协调对等节点连接
- 协议管理（`BitTorrentProtocol`、`IPFSProtocol`）
- 资源分配和限制
- 通过`EventBus`分发事件
- 检查点管理
- DHT客户端管理
- 种子优先级排序的队列管理
- 通过`NATManager`进行NAT遍历
- 跟踪器scraping（BEP 48）

#### 会话控制器（重构）

为了提高可维护性，会话逻辑正在逐步提取到`ccbt/session/`下的专注控制器中：

- `models.py`：`TorrentStatus`枚举和`SessionContext`
- `types.py`：协议（`DHTClientProtocol`、`TrackerClientProtocol`、`PeerManagerProtocol`、`PieceManagerProtocol`）
- `tasks.py`：用于后台任务管理的`TaskSupervisor`
- `checkpointing.py`：用于保存/加载和批处理的`CheckpointController`
- `discovery.py`：用于DHT/跟踪器发现和去重的`DiscoveryController`
- `peer_events.py`：用于回调连接的`PeerEventsBinder`
- `lifecycle.py`：用于启动/暂停/恢复/停止序列的`LifecycleController`
- `metrics_status.py`：指标和状态聚合助手
- `adapters.py`：`DHTAdapter`和`TrackerAdapter`，用于在协议后面统一具体客户端

### 对等节点连接管理器

处理所有对等节点连接，具有高级流水线处理。`AsyncPeerConnectionManager`管理种子会话的各个对等节点连接。

**实现：** `ccbt/peer/async_peer_connection.py`

**功能：**
- 异步TCP连接
- 请求流水线处理（16-64个未完成请求）
- 自适应块大小
- 连接池
- Choking/unchoking算法
- BitTorrent协议握手
- 扩展协议支持（Fast、PEX、DHT、WebSeed、SSL、XET）

### 片段管理器

实现高级片段选择算法。`AsyncPieceManager`协调片段下载、验证和完成跟踪。

**实现：** `ccbt/piece/async_piece_manager.py`

**算法：**
- **Rarest-First**：最优群组健康度
- **Sequential**：用于流媒体
- **Round-Robin**：简单回退
- **Endgame Mode**：完成时的重复请求
- 部分下载的文件选择支持

### 磁盘I/O管理器

具有多种策略的优化磁盘操作。磁盘I/O系统通过`init_disk_io()`初始化，并通过会话管理器进行管理。

**实现：** `ccbt/storage/disk_io.py`

**优化：**
- 文件预分配（sparse/full）
- 写入批处理和缓冲
- 内存映射I/O
- io_uring支持（Linux）
- 高性能存储的直接I/O
- 并行哈希验证
- 用于恢复功能的检查点管理

## 数据流

### 下载过程

```
1. 种子加载
   ┌─────────────┐
   │ Torrent File│ ──┐
   │ or Magnet   │   │
   └─────────────┘   │
                     │
2. 跟踪器公告      │
   ┌─────────────┐   │
   │   Tracker  │ ◄──┘
   │   Client   │
   └─────────────┘
           │
           ▼
3. 对等节点发现
   ┌─────────────┐
   │    DHT     │
   │   Manager  │
   └─────────────┘
           │
           ▼
4. 对等节点连接
   ┌─────────────┐
   │    Peer    │
   │ Connection │
   │   Manager  │
   └─────────────┘
           │
           ▼
5. 片段选择
   ┌─────────────┐
   │    Piece    │
   │   Manager   │
   └─────────────┘
           │
           ▼
6. 数据传输
   ┌─────────────┐
   │    Disk     │
   │     I/O     │
   │   Manager   │
   └─────────────┘
```

### 事件系统

系统使用事件驱动架构实现松耦合。事件通过全局`EventBus`发出，任何组件都可以订阅。

**实现：** `ccbt/utils/events.py`

事件系统包括全面的事件类型：

`EventType`枚举定义了所有系统事件，包括对等节点、片段、种子、跟踪器、DHT、协议、扩展和安全事件。包含所有事件类型的完整枚举：

```python
--8<-- "ccbt/utils/events.py:34:152"
```

事件通过`emit_event()`函数使用全局事件总线发出：

```python
--8<-- "ccbt/utils/events.py:658:661"
```

## 配置系统

### 分层配置

配置由`ConfigManager`管理，它按优先级顺序从多个源加载设置。

**实现：** `ccbt/config/config.py`

`ConfigManager`类处理配置加载、验证和热重载。它在标准位置搜索配置文件，并支持加密的代理密码。查看初始化：

```python
--8<-- "ccbt/config/config.py:46:60"
```

**配置源（按顺序）：**
1. 默认值（来自Pydantic模型）
2. 配置文件（当前目录中的`ccbt.toml`、`~/.config/ccbt/ccbt.toml`或`~/.ccbt.toml`）
3. 环境变量（`CCBT_*`）
4. CLI参数
5. 每个种子的覆盖

### 热重载

`ConfigManager`支持在不重启应用程序的情况下热重载配置文件。检测到配置文件时，热重载会自动启动。

## 监控和可观测性

### 指标收集

指标收集通过`init_metrics()`初始化，并提供Prometheus兼容的指标。

**实现：** `ccbt/monitoring/metrics_collector.py`

指标在会话管理器的`start()`方法中初始化，如果配置中启用，可以通过`session.metrics`访问。

### 警报系统

警报系统为各种系统条件提供基于规则的警报。

**实现：** `ccbt/monitoring/alert_manager.py`

### 跟踪

用于性能分析和调试的分布式跟踪支持。

**实现：** `ccbt/monitoring/tracing.py`

## 安全功能

### 安全管理器

`SecurityManager`提供全面的安全功能，包括IP过滤、对等节点验证、速率限制和异常检测。

**实现：** `ccbt/security/security_manager.py`

安全管理器在会话管理器的`start()`方法中初始化，可以从配置加载IP过滤器。

### 对等节点验证

对等节点验证由`PeerValidator`处理，它检查被阻止的IP和可疑行为模式。

**实现：** `ccbt/security/peer_validator.py`

### 速率限制

用于带宽管理的自适应速率限制由`RateLimiter`和`AdaptiveLimiter`（基于ML）提供。

**实现：** `ccbt/security/rate_limiter.py`、`ccbt/ml/adaptive_limiter.py`

## 可扩展性

### 插件系统

插件系统允许注册和管理可选的插件和扩展。

**实现：** `ccbt/plugins/base.py`

插件可以在`PluginManager`中注册，并为各种系统事件提供钩子。

### 协议扩展

BitTorrent协议扩展由`ExtensionManager`管理，它处理Fast Extension、PEX、DHT、WebSeed、SSL和XET扩展。

**实现：** `ccbt/extensions/manager.py`

`ExtensionManager`初始化所有支持的BitTorrent扩展，包括Protocol、SSL、Fast、PEX和DHT扩展。每个扩展都以其功能和状态注册。查看初始化逻辑：

```python
--8<-- "ccbt/extensions/manager.py:51:110"
```

### 协议管理器

`ProtocolManager`管理多个协议（BitTorrent、IPFS、WebTorrent、XET、Hybrid），具有断路器支持和性能跟踪。

**实现：** `ccbt/protocols/base.py`

`ProtocolManager`管理具有断路器支持、性能跟踪和自动事件发出的多个协议。协议按其类型注册，统计信息按协议跟踪。查看初始化和注册：

```python
--8<-- "ccbt/protocols/base.py:286:324"
```

## 性能优化

### 全面使用Async/Await

所有I/O操作都是异步的：
- 网络操作
- 磁盘I/O
- 哈希验证
- 配置加载

### 内存管理

- 尽可能使用零拷贝消息处理
- 高吞吐量场景的环形缓冲区
- 内存映射文件I/O
- 高效的数据结构

### 连接池

连接池在对等节点连接层实现，以高效地重用TCP连接并管理连接限制。

**实现：** `ccbt/peer/connection_pool.py`

## 测试架构

### 测试类别

- **单元测试**：单个组件测试
- **集成测试**：组件交互测试
- **性能测试**：基准测试和分析
- **混沌测试**：故障注入和弹性测试

### 测试工具

测试工具和模拟对象在`tests/`目录中可用于单元、集成、属性和性能测试。

## 未来架构考虑

### 可扩展性

- 使用多个会话管理器进行水平扩展
- 分布式对等节点发现
- 跨实例的负载平衡

### 云集成

- 云存储后端
- 无服务器部署选项
- 容器编排

### 高级功能

- 用于对等节点选择的机器学习
- 基于区块链的对等节点发现
- **IPFS集成**（已实现）
- WebTorrent兼容性

## IPFS协议集成

### 架构概述

IPFS协议集成通过IPFS守护进程提供分散式内容寻址和对等网络功能。

**实现：** `ccbt/protocols/ipfs.py`

### 集成点

```
┌─────────────────────────────────────────────────────────────┐
│                    IPFS Protocol Integration                  │
├─────────────────────────────────────────────────────────────┤
│  Session Manager                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         AsyncSessionManager                           │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │         ProtocolManager                         │ │  │
│  │  │  ┌──────────────┐  ┌──────────────┐           │ │  │
│  │  │  │ BitTorrent   │  │    IPFS      │           │ │  │
│  │  │  │  Protocol    │  │  Protocol    │           │ │  │
│  │  │  └──────────────┘  └──────────────┘           │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  IPFS Protocol                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   HTTP API   │  │   Pubsub     │  │     DHT      │     │
│  │  Client      │  │  Messaging   │  │  Discovery   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Content    │  │   Gateway    │  │   Pinning    │     │
│  │  Operations  │  │   Fallback   │  │   Manager    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────────────────────────┤
│  IPFS Daemon (External)                                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  IPFS Node (libp2p, Bitswap, DHT, Gateway)          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 协议生命周期

1. **初始化**：协议创建并在`ProtocolManager`中注册
2. **连接**：`start()`通过HTTP API连接到IPFS守护进程
3. **验证**：查询节点ID以验证连接
4. **操作**：内容操作、对等节点连接、消息传递
5. **清理**：`stop()`断开连接并清理资源

### 会话管理器集成

如果配置中启用了IPFS协议，它会在会话管理器启动期间自动注册。协议在协议管理器中注册并启动，具有优雅的错误处理，如果IPFS不可用，不会阻止会话启动。查看初始化：

```python
--8<-- "ccbt/session/async_main.py:441:462"
```

### 内容寻址

IPFS使用内容标识符（CIDs）进行不可变的内容寻址：

- **CIDv0**：Base58编码，传统格式（例如，`Qm...`）
- **CIDv1**：Multibase编码，现代格式（例如，`bafybei...`）
- 内容由其加密哈希寻址
- 相同的内容总是产生相同的CID

### 种子到IPFS的转换

种子可以转换为IPFS内容：

1. 种子元数据序列化为JSON
2. 元数据添加到IPFS，生成CID
3. 片段哈希作为块引用
4. 如果配置，内容自动固定

### 对等节点通信

- **Pubsub**：基于主题的消息传递（`/ccbt/peer/{peer_id}`）
- **Multiaddr**：对等节点地址的标准格式
- **DHT**：用于对等节点发现的分布式哈希表
- **消息队列**：每个对等节点的队列，用于可靠传递

### 内容操作

- **Add**：内容添加到IPFS，返回CID
- **Get**：通过CID检索内容
- **Pin**：内容固定以防止垃圾回收
- **Unpin**：内容取消固定，可能被垃圾回收
- **Stats**：内容统计（大小、块、链接）

### 配置

IPFS配置是主`Config`模型的一部分。有关IPFS设置的详细信息，请参阅配置文档。

### 错误处理

- 连接失败：使用指数退避自动重试
- 超时：每个操作可配置的超时
- 守护进程不可用：优雅降级，协议保持注册
- 内容未找到：返回`None`，记录警告

### 性能考虑

- **异步操作**：所有IPFS API调用都使用`asyncio.to_thread`来避免阻塞
- **缓存**：发现结果和内容统计使用TTL缓存
- **网关回退**：如果守护进程不可用，使用公共网关
- **连接池**：重用与IPFS守护进程的HTTP连接

### 序列图

```
Session Manager          IPFS Protocol          IPFS Daemon
     │                         │                      │
     │  start()                │                      │
     ├────────────────────────>│                      │
     │                         │  connect()           │
     │                         ├─────────────────────>│
     │                         │  id()                │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │                         │                      │
     │  add_content()           │                      │
     ├────────────────────────>│  add_bytes()         │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │  <CID>                  │                      │
     │<────────────────────────┤                      │
     │                         │                      │
     │  get_content(CID)       │                      │
     ├────────────────────────>│  cat(CID)            │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │  <content>               │                      │
     │<────────────────────────┤                      │
     │                         │                      │
     │  stop()                  │                      │
     ├────────────────────────>│  close()             │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │                         │                      │
```

有关特定组件的更详细信息，请参阅各个文档文件和源代码。

