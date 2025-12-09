# 性能调优指南

本指南介绍ccBitTorrent的性能优化技术，以实现最大下载速度和高效的资源使用。

## 网络优化

### 连接设置

#### 管道深度

控制每个对等节点的未完成请求数。

配置: [ccbt.toml:12](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L12)

**推荐:**
- **高延迟连接**: 32-64（卫星、移动）
- **低延迟连接**: 16-32（光纤、电缆）
- **本地网络**: 8-16（LAN传输）

实现: [ccbt/peer/async_peer_connection.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/peer/async_peer_connection.py) - 请求管道

#### 块大小

从对等节点请求的数据块大小。

配置: [ccbt.toml:13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L13)

**推荐:**
- **高带宽**: 32-64 KiB（光纤、电缆）
- **中等带宽**: 16-32 KiB（DSL、移动）
- **低带宽**: 4-16 KiB（拨号、慢速移动）

最小/最大块大小: [ccbt.toml:14-15](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L14-L15)

#### 套接字缓冲区

在高吞吐量场景中增加。

配置: [ccbt.toml:17-18](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L18)

默认值: [ccbt.toml:17-18](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L18)（每个256 KiB）

TCP_NODELAY设置: [ccbt.toml:19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L19)

### 连接限制

#### 全局对等节点限制

配置: [ccbt.toml:6-7](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L7)

**调优指南:**
- **高带宽**: 增加全局对等节点（200-500）
- **低带宽**: 减少全局对等节点（50-100）
- **多种子**: 减少每个种子的限制（10-25）
- **少种子**: 增加每个种子的限制（50-100）

实现: [ccbt/peer/connection_pool.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/peer/connection_pool.py) - 连接池管理

每个对等节点的最大连接数: [ccbt.toml:8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L8)

#### 连接超时

配置: [ccbt.toml:22-25](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L25)

- 连接超时: [ccbt.toml:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22)
- 握手超时: [ccbt.toml:23](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L23)
- 保持活动间隔: [ccbt.toml:24](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L24)
- 对等节点超时: [ccbt.toml:25](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L25)

## 磁盘I/O优化

### 预分配策略

配置: [ccbt.toml:59](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59)

**推荐:**
- **SSD**: 使用"full"以获得更好的性能
- **HDD**: 使用"sparse"以节省空间
- **网络存储**: 使用"none"以避免延迟

稀疏文件选项: [ccbt.toml:60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L60)

实现: [ccbt/storage/disk_io.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - 磁盘I/O操作

### 写入优化

配置: [ccbt.toml:63-64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L64)

**调优指南:**
- **快速存储**: 增加批处理大小（128-256 KiB）
- **慢速存储**: 减少批处理大小（32-64 KiB）
- **关键数据**: 启用sync_writes
- **性能**: 禁用sync_writes

写入批处理大小: [ccbt.toml:63](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63)

写入缓冲区大小: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)

同步写入设置: [ccbt.toml:82](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L82)

文件组装器: [ccbt/storage/file_assembler.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/file_assembler.py)

### 内存映射

配置: [ccbt.toml:65-66](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L65-L66)

**优势:**
- 已完成片段的读取更快
- 减少内存使用
- 更好的操作系统缓存

**注意事项:**
- 需要足够的RAM
- 可能导致内存压力
- 最适合读取密集型工作负载

使用MMAP: [ccbt.toml:65](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L65)

MMAP缓存大小: [ccbt.toml:66](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L66)

MMAP缓存清理间隔: [ccbt.toml:67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L67)

### 高级I/O功能

#### io_uring（Linux）

配置: [ccbt.toml:84](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L84)

**要求:**
- Linux内核5.1+
- 现代存储设备
- 足够的系统资源

#### 直接I/O

配置: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)

**使用场景:**
- 高性能存储
- 绕过操作系统页面缓存
- 一致的性能

预读大小: [ccbt.toml:83](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L83)

## 策略选择

### 片段选择算法

配置: [ccbt.toml:101](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101)

#### Rarest-First（推荐）

**优势:**
- 最优的群组健康度
- 更快的完成时间
- 更好的对等节点协作

实现: [ccbt/piece/async_piece_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/async_piece_manager.py) - 片段选择逻辑

Rarest first阈值: [ccbt.toml:107](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107)

#### 顺序

**使用场景:**
- 流式传输媒体文件
- 顺序访问模式
- 基于优先级的下载

顺序窗口: [ccbt.toml:108](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L108)

流式传输模式: [ccbt.toml:104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L104)

#### 轮询

**使用场景:**
- 简单场景
- 调试
- 遗留兼容性

实现: [ccbt/piece/piece_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/piece_manager.py)

### 终局优化

配置: [ccbt.toml:102-103](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L102-L103)

**调优:**
- **快速连接**: 降低阈值（0.85-0.9）
- **慢速连接**: 提高阈值（0.95-0.98）
- **多对等节点**: 增加重复（3-5）
- **少对等节点**: 减少重复（1-2）

终局阈值: [ccbt.toml:103](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L103)

终局重复: [ccbt.toml:102](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L102)

管道容量: [ccbt.toml:109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L109)

### 片段优先级

配置: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

第一个片段优先级: [ccbt.toml:112](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112)

最后一个片段优先级: [ccbt.toml:113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L113)

## 速率限制

### 全局限制

配置: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)

全局下载限制: [ccbt.toml:140](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140)（0 = 无限制）

全局上传限制: [ccbt.toml:141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L141)（0 = 无限制）

网络级别限制: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

实现: [ccbt/security/rate_limiter.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/rate_limiter.py) - 速率限制逻辑

### 每个种子的限制

使用CLI通过[ccbt/cli/main.py:download](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L369)设置限制，使用`--download-limit`和`--upload-limit`选项。

每个种子的配置: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)

每个对等节点的限制: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)

### 调度器设置

调度器时间片: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

## 哈希验证

### 工作线程

配置: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)

**调优指南:**
- **CPU核心**: 匹配或超过核心数
- **SSD存储**: 可以处理更多工作线程
- **HDD存储**: 限制工作线程（2-4）

哈希块大小: [ccbt.toml:71](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L71)

哈希批处理大小: [ccbt.toml:72](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L72)

哈希队列大小: [ccbt.toml:73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L73)

实现: [ccbt/storage/disk_io.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - 哈希验证工作线程

## 内存管理

### 缓冲区大小

写入缓冲区: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)

预读: [ccbt.toml:83](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L83)

### 缓存设置

缓存大小: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)

MMAP缓存: [ccbt.toml:66](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L66)

磁盘队列大小: [ccbt.toml:77](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L77)

磁盘工作线程: [ccbt.toml:76](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76)

## 系统级优化

### 文件系统调优

对于系统级优化，请参考操作系统的文档。这些是在ccBitTorrent配置之外应用的一般建议。

### 网络堆栈调优

对于网络堆栈优化，请参考操作系统的文档。这些是影响整体网络性能的系统级设置。

## 性能监控

### 关键指标

通过Prometheus监控这些关键指标:

- **下载速度**: `ccbt_download_rate_bytes_per_second` - 参见 [ccbt/utils/metrics.py:142](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/metrics.py#L142)
- **上传速度**: `ccbt_upload_rate_bytes_per_second` - 参见 [ccbt/utils/metrics.py:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/metrics.py#L148)
- **连接的对等节点**: 通过MetricsCollector可用
- **磁盘队列深度**: 通过MetricsCollector可用 - 参见 [ccbt/monitoring/metrics_collector.py]
- **哈希队列深度**: 通过MetricsCollector可用

Prometheus指标端点: [ccbt/utils/metrics.py:179](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/metrics.py#L179)

### 性能分析

启用指标: [ccbt.toml:164](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L164)

指标端口: [ccbt.toml:165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L165)

启用时可在`http://localhost:9090/metrics`访问指标。

通过CLI查看指标: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L229)

## 性能问题故障排除

### 下载速度低

1. **检查对等节点连接**:
   启动Bitonic仪表板: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L20)

2. **验证片段选择**:
   在[ccbt.toml:101](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101)中配置
   
   实现: [ccbt/piece/async_piece_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/async_piece_manager.py)

3. **增加管道深度**:
   在[ccbt.toml:12](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L12)中配置
   
   实现: [ccbt/peer/async_peer_connection.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/peer/async_peer_connection.py)

4. **检查速率限制**:
   配置: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
   
   CLI状态命令: [ccbt/cli/main.py:status](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L789)

### CPU使用率高

1. **减少哈希工作线程**:
   在[ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)中配置

2. **禁用内存映射**:
   在[ccbt.toml:65](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L65)中配置

3. **增加刷新间隔**:
   Bitonic刷新间隔: [ccbt/interface/terminal_dashboard.py:303](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L303)
   
   仪表板配置: [ccbt.toml:189](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L189)

### 磁盘I/O瓶颈

1. **启用写入批处理**:
   配置写入批处理大小: [ccbt.toml:63](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63)
   
   实现: [ccbt/storage/disk_io.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py)

2. **使用更快的存储**:
   - 将下载移动到SSD
   - 使用RAID 0以提高性能

3. **优化文件系统**:
   - 使用适当的文件系统
   - 调整挂载选项

## 基准测试

### 基准测试脚本

性能基准测试脚本位于`tests/performance/`:

- 哈希验证: `tests/performance/bench_hash_verify.py`
- 磁盘I/O: `tests/performance/bench_disk_io.py`
- 片段组装: `tests/performance/bench_piece_assembly.py`
- 环回吞吐量: `tests/performance/bench_loopback_throughput.py`
- 加密: `tests/performance/bench_encryption.py`

运行所有基准测试: [tests/scripts/bench_all.py](https://github.com/yourusername/ccbittorrent/blob/main/tests/scripts/bench_all.py)

基准测试配置示例: [example-config-performance.toml](examples/example-config-performance.toml)

### 基准测试记录

基准测试可以用不同的模式记录，以跟踪时间性能:

#### 记录模式

- **`pre-commit`**: 在pre-commit钩子运行期间记录（快速冒烟测试）
- **`commit`**: 在实际提交期间记录（完整基准测试，在每次运行和时序列中记录）
- **`both`**: 在pre-commit和commit上下文中都记录
- **`auto`**: 自动检测上下文（使用`PRE_COMMIT`环境变量）
- **`none`**: 不记录（基准测试运行但不保存结果）

#### 使用记录运行基准测试

```bash
# Pre-commit模式（快速冒烟测试）
uv run python tests/performance/bench_hash_verify.py --quick --record-mode=pre-commit

# Commit模式（完整基准测试）
uv run python tests/performance/bench_hash_verify.py --record-mode=commit

# 两种模式
uv run python tests/performance/bench_hash_verify.py --record-mode=both

# 自动检测模式（默认）
uv run python tests/performance/bench_hash_verify.py --record-mode=auto
```

#### 基准测试数据存储

基准测试结果以两种格式存储:

1. **每次运行文件**（`docs/reports/benchmarks/runs/`）:
   - 每次基准测试运行的单独JSON文件
   - 文件名格式: `{benchmark_name}-{timestamp}-{commit_hash_short}.json`
   - 包含完整元数据: git提交哈希、分支、作者、平台信息、结果

2. **时序列文件**（`docs/reports/benchmarks/timeseries/`）:
   - JSON格式的聚合历史数据
   - 文件名格式: `{benchmark_name}_timeseries.json`
   - 便于查询时间性能趋势

有关查询历史数据和基准测试报告的详细信息，请参见[基准测试报告](reports/benchmarks/index.md)。

### 测试和覆盖率工件

运行完整测试套件（pre-push/CI）时，工件输出到:

- `tests/.reports/junit.xml`（JUnit报告）
- `tests/.reports/pytest.log`（测试日志）
- `coverage.xml`和`htmlcov/`（覆盖率报告）

这些与Codecov集成；`dev/.codecov.yml`中的标志与`ccbt/`子包对齐，以准确归因覆盖率（例如`peer`、`piece`、`protocols`、`extensions`）。覆盖率HTML报告通过`mkdocs-coverage`插件自动集成到文档中，该插件从`site/reports/htmlcov/`读取并在[reports/coverage.md](reports/coverage.md)中呈现。

#### 遗留基准测试工件

遗留基准测试工件仍写入`site/reports/benchmarks/artifacts/`，以便在使用`--output-dir`参数时向后兼容。但是，建议使用新的记录系统来跟踪时间性能。

## 最佳实践

1. **从默认值开始**: 从[ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)的默认设置开始
2. **测量基线**: 使用[ccbt/cli/monitoring_commands.py:metrics](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L229)建立性能基线
3. **一次更改一个设置**: 在[ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)中一次修改一个设置
4. **彻底测试**: 验证改进
5. **监控资源**: 通过[Bitonic](bitonic.md)监控CPU、内存、磁盘使用情况
6. **记录更改**: 跟踪有效设置

## 配置模板

### 高性能设置

参考高性能配置模板: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

关键设置:
- 网络: [ccbt.toml:11-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L42)
- 磁盘: [ccbt.toml:57-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L85)
- 策略: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

示例: [example-config-performance.toml](examples/example-config-performance.toml)

### 低资源设置

参考低资源配置模板: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

关键设置:
- 网络: [ccbt.toml:6-7](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L7) - 减少对等节点限制
- 磁盘: [ccbt.toml:59-65](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L65) - 使用稀疏预分配，禁用MMAP
- 策略: [ccbt.toml:101](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101) - Rarest-first仍然是最优的

有关更详细的配置选项，请参见[配置](configuration.md)文档。
