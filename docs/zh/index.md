# ccBitTorrent - 高性能 BitTorrent 客户端

使用 Python asyncio 构建的现代高性能 BitTorrent 客户端，具有高级片段选择算法、并行元数据交换和优化的磁盘 I/O。

## 功能

### 性能优化
- **异步 I/O**: 完整的 asyncio 实现，提供卓越的并发性
- **Rarest-First 选择**: 智能片段选择，优化群组健康
- **终局模式**: 重复请求以加快完成速度
- **请求流水线**: 深度请求队列（每个对等节点 16-64 个未完成请求）
- **Tit-for-Tat Choking**: 通过乐观 unchoke 实现公平带宽分配
- **并行元数据**: 从多个对等节点并发获取 ut_metadata
- **磁盘 I/O 优化**: 文件预分配、批量写入、环形缓冲区暂存、内存映射 I/O
- **哈希验证池**: 在工作线程中并行 SHA-1 验证

### 高级配置
- **TOML 配置**: 具有热重载功能的综合配置系统
- **每个 Torrent 设置**: 单个 torrent 配置覆盖
- **速率限制**: 全局和每个 torrent 的上传/下载限制
- **策略选择**: 轮询、rarest-first 或顺序片段选择
- **流式模式**: 基于优先级的媒体文件片段选择

### 网络功能
- **UDP Tracker 支持**: 符合 BEP 15 的 UDP tracker 通信
- **增强 DHT**: 具有迭代查找的完整 Kademlia 路由表
- **对等节点交换 (PEX)**: 符合 BEP 11 的对等节点发现
- **连接管理**: 自适应对等节点选择和连接限制
- **协议优化**: 使用零复制路径的高效内存消息处理

## Xet 协议扩展 (BEP XET)

Xet 协议扩展是一个关键差异化功能，将 BitTorrent 转换为为协作优化的超快速、可更新的点对点文件系统。BEP XET 支持：

- **内容定义分块**: 基于 Gearhash 的智能文件分段（8KB-128KB 块）以实现高效更新
- **跨 Torrent 去重**: 多个 torrent 之间的块级去重
- **点对点 CAS**: 使用 DHT 和 trackers 的分散式内容可寻址存储
- **超快速更新**: 只需重新分发已更改的块，实现快速协作文件共享
- **P2P 文件系统**: 将 BitTorrent 转换为为协作优化的可更新点对点文件系统
- **Merkle 树验证**: BLAKE3-256 哈希与 SHA-256 回退以确保完整性

[了解更多关于 BEP XET →](bep_xet.md)

### 可观测性
- **指标导出**: 用于监控的 Prometheus 兼容指标
- **结构化日志**: 具有每个对等节点跟踪的可配置日志
- **性能统计**: 实时吞吐量、延迟和队列深度跟踪
- **健康监控**: 连接质量和对等节点可靠性评分
- **终端仪表板**: 基于 Textual 的实时仪表板 (Bitonic)
- **警报管理器**: 通过 CLI 进行持久化和测试的基于规则的警报

## 快速开始

### 使用 UV 安装

从 [astral.sh/uv](https://astral.sh/uv) 安装 UV，然后安装 ccBitTorrent。

### 主要入口点

**Bitonic** - 主终端仪表板界面（推荐）：
- 启动: `uv run bitonic` 或 `uv run ccbt dashboard`

**btbt CLI** - 增强的命令行界面：
- 启动: `uv run btbt`

**ccbt** - 基本 CLI 界面：
- 启动: `uv run ccbt`

有关详细用法，请参阅：
- [入门指南](getting-started.md) - 分步教程
- [Bitonic](bitonic.md) - 终端仪表板指南
- [btbt CLI](btbt-cli.md) - 完整命令参考

## 文档

- [BEP XET](bep_xet.md) - 用于内容定义分块和去重的 Xet 协议扩展
- [入门](getting-started.md) - 安装和第一步
- [Bitonic](bitonic.md) - 终端仪表板（主界面）
- [btbt CLI](btbt-cli.md) - 命令行界面参考
- [配置](configuration.md) - 配置选项和设置
- [性能调优](performance.md) - 优化指南
- [ccBT API 参考](API.md) - Python API 文档
- [贡献](contributing.md) - 如何贡献
- [资助](funding.md) - 支持项目

## 许可证

本项目根据 **GNU General Public License v2 (GPL-2.0)** 许可 - 有关详细信息，请参阅 [license.md](license.md)。

此外，本项目受 **ccBT RAIL-AMS 许可证**下的额外使用限制 - 有关完整条款和使用限制，请参阅 [ccBT-RAIL.md](ccBT-RAIL.md)。

**重要**: 两个许可证都适用于此软件。您必须遵守 GPL-2.0 许可证和 RAIL 许可证中的所有条款和限制。

## 报告

在文档中查看项目报告：
- [覆盖率报告](reports/coverage.md) - 代码覆盖率分析
- [Bandit 安全报告](reports/bandit/index.md) - 安全扫描结果
- [基准测试](reports/benchmarks/index.md) - 性能基准测试结果

## 致谢

- BitTorrent 协议规范 (BEP 5, 10, 11, 15, 52)
- Xet 协议用于内容定义分块的灵感
- Python asyncio 用于高性能 I/O
- BitTorrent 社区用于协议开发






使用 Python asyncio 构建的现代高性能 BitTorrent 客户端，具有高级片段选择算法、并行元数据交换和优化的磁盘 I/O。

## 功能

### 性能优化
- **异步 I/O**: 完整的 asyncio 实现，提供卓越的并发性
- **Rarest-First 选择**: 智能片段选择，优化群组健康
- **终局模式**: 重复请求以加快完成速度
- **请求流水线**: 深度请求队列（每个对等节点 16-64 个未完成请求）
- **Tit-for-Tat Choking**: 通过乐观 unchoke 实现公平带宽分配
- **并行元数据**: 从多个对等节点并发获取 ut_metadata
- **磁盘 I/O 优化**: 文件预分配、批量写入、环形缓冲区暂存、内存映射 I/O
- **哈希验证池**: 在工作线程中并行 SHA-1 验证

### 高级配置
- **TOML 配置**: 具有热重载功能的综合配置系统
- **每个 Torrent 设置**: 单个 torrent 配置覆盖
- **速率限制**: 全局和每个 torrent 的上传/下载限制
- **策略选择**: 轮询、rarest-first 或顺序片段选择
- **流式模式**: 基于优先级的媒体文件片段选择

### 网络功能
- **UDP Tracker 支持**: 符合 BEP 15 的 UDP tracker 通信
- **增强 DHT**: 具有迭代查找的完整 Kademlia 路由表
- **对等节点交换 (PEX)**: 符合 BEP 11 的对等节点发现
- **连接管理**: 自适应对等节点选择和连接限制
- **协议优化**: 使用零复制路径的高效内存消息处理

## Xet 协议扩展 (BEP XET)

Xet 协议扩展是一个关键差异化功能，将 BitTorrent 转换为为协作优化的超快速、可更新的点对点文件系统。BEP XET 支持：

- **内容定义分块**: 基于 Gearhash 的智能文件分段（8KB-128KB 块）以实现高效更新
- **跨 Torrent 去重**: 多个 torrent 之间的块级去重
- **点对点 CAS**: 使用 DHT 和 trackers 的分散式内容可寻址存储
- **超快速更新**: 只需重新分发已更改的块，实现快速协作文件共享
- **P2P 文件系统**: 将 BitTorrent 转换为为协作优化的可更新点对点文件系统
- **Merkle 树验证**: BLAKE3-256 哈希与 SHA-256 回退以确保完整性

[了解更多关于 BEP XET →](bep_xet.md)

### 可观测性
- **指标导出**: 用于监控的 Prometheus 兼容指标
- **结构化日志**: 具有每个对等节点跟踪的可配置日志
- **性能统计**: 实时吞吐量、延迟和队列深度跟踪
- **健康监控**: 连接质量和对等节点可靠性评分
- **终端仪表板**: 基于 Textual 的实时仪表板 (Bitonic)
- **警报管理器**: 通过 CLI 进行持久化和测试的基于规则的警报

## 快速开始

### 使用 UV 安装

从 [astral.sh/uv](https://astral.sh/uv) 安装 UV，然后安装 ccBitTorrent。

### 主要入口点

**Bitonic** - 主终端仪表板界面（推荐）：
- 启动: `uv run bitonic` 或 `uv run ccbt dashboard`

**btbt CLI** - 增强的命令行界面：
- 启动: `uv run btbt`

**ccbt** - 基本 CLI 界面：
- 启动: `uv run ccbt`

有关详细用法，请参阅：
- [入门指南](getting-started.md) - 分步教程
- [Bitonic](bitonic.md) - 终端仪表板指南
- [btbt CLI](btbt-cli.md) - 完整命令参考

## 文档

- [BEP XET](bep_xet.md) - 用于内容定义分块和去重的 Xet 协议扩展
- [入门](getting-started.md) - 安装和第一步
- [Bitonic](bitonic.md) - 终端仪表板（主界面）
- [btbt CLI](btbt-cli.md) - 命令行界面参考
- [配置](configuration.md) - 配置选项和设置
- [性能调优](performance.md) - 优化指南
- [ccBT API 参考](API.md) - Python API 文档
- [贡献](contributing.md) - 如何贡献
- [资助](funding.md) - 支持项目

## 许可证

本项目根据 **GNU General Public License v2 (GPL-2.0)** 许可 - 有关详细信息，请参阅 [license.md](license.md)。

此外，本项目受 **ccBT RAIL-AMS 许可证**下的额外使用限制 - 有关完整条款和使用限制，请参阅 [ccBT-RAIL.md](ccBT-RAIL.md)。

**重要**: 两个许可证都适用于此软件。您必须遵守 GPL-2.0 许可证和 RAIL 许可证中的所有条款和限制。

## 报告

在文档中查看项目报告：
- [覆盖率报告](reports/coverage.md) - 代码覆盖率分析
- [Bandit 安全报告](reports/bandit/index.md) - 安全扫描结果
- [基准测试](reports/benchmarks/index.md) - 性能基准测试结果

## 致谢

- BitTorrent 协议规范 (BEP 5, 10, 11, 15, 52)
- Xet 协议用于内容定义分块的灵感
- Python asyncio 用于高性能 I/O
- BitTorrent 社区用于协议开发
































































































































































































