# btbt CLI - 命令参考

**btbt** 是 ccBitTorrent 的增强命令行界面，提供对种子操作、监控、配置和高级功能的全面控制。

- 入口点: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- 定义位置: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- 主CLI组: [ccbt/cli/main.py:cli](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L243)

## 基本命令

### download

下载种子文件。

实现: [ccbt/cli/main.py:download](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L369)

用法:
```bash
uv run btbt download <torrent_file> [options]
```

选项:
- `--output <dir>`: 输出目录
- `--interactive`: 交互模式
- `--monitor`: 监控模式
- `--resume`: 从检查点恢复
- `--no-checkpoint`: 禁用检查点
- `--checkpoint-dir <dir>`: 检查点目录
- `--files <indices...>`: 选择要下载的特定文件（可多次指定，例如 `--files 0 --files 1`）
- `--file-priority <spec>`: 将文件优先级设置为 `file_index=priority`（例如 `0=high,1=low`）。可多次指定。

网络选项（参见 [ccbt/cli/main.py:_apply_network_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L67)）:
- `--listen-port <int>`: 监听端口
- `--max-peers <int>`: 最大全局对等节点数
- `--max-peers-per-torrent <int>`: 每个种子的最大对等节点数
- `--pipeline-depth <int>`: 请求管道深度
- `--block-size-kib <int>`: 块大小（KiB）
- `--connection-timeout <float>`: 连接超时
- `--global-down-kib <int>`: 全局下载限制（KiB/s）
- `--global-up-kib <int>`: 全局上传限制（KiB/s）

磁盘选项（参见 [ccbt/cli/main.py:_apply_disk_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L179)）:
- `--hash-workers <int>`: 哈希验证工作线程数
- `--disk-workers <int>`: 磁盘I/O工作线程数
- `--use-mmap`: 启用内存映射
- `--no-mmap`: 禁用内存映射
- `--write-batch-kib <int>`: 写入批处理大小（KiB）
- `--write-buffer-kib <int>`: 写入缓冲区大小（KiB）
- `--preallocate <str>`: 预分配策略（none|sparse|full）

策略选项（参见 [ccbt/cli/main.py:_apply_strategy_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L151)）:
- `--piece-selection <str>`: 片段选择策略（round_robin|rarest_first|sequential）
- `--endgame-duplicates <int>`: 终局重复请求
- `--endgame-threshold <float>`: 终局阈值
- `--streaming`: 启用流式传输模式

发现选项（参见 [ccbt/cli/main.py:_apply_discovery_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L123)）:
- `--enable-dht`: 启用DHT
- `--disable-dht`: 禁用DHT
- `--enable-pex`: 启用PEX
- `--disable-pex`: 禁用PEX
- `--enable-http-trackers`: 启用HTTP跟踪器
- `--disable-http-trackers`: 禁用HTTP跟踪器
- `--enable-udp-trackers`: 启用UDP跟踪器
- `--disable-udp-trackers`: 禁用UDP跟踪器

可观测性选项（参见 [ccbt/cli/main.py:_apply_observability_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L217)）:
- `--log-level <str>`: 日志级别（DEBUG|INFO|WARNING|ERROR|CRITICAL）
- `--log-file <path>`: 日志文件路径
- `--enable-metrics`: 启用指标收集
- `--disable-metrics`: 禁用指标收集
- `--metrics-port <int>`: 指标端口

### magnet

从磁力链接下载。

实现: [ccbt/cli/main.py:magnet](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L608)

用法:
```bash
uv run btbt magnet <magnet_link> [options]
```

选项: 与 `download` 命令相同。

### interactive

启动交互式CLI模式。

实现: [ccbt/cli/main.py:interactive](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L767)

用法:
```bash
uv run btbt interactive
```

交互式CLI: [ccbt/cli/interactive.py:InteractiveCLI](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/interactive.py#L41)

### status

显示当前会话状态。

实现: [ccbt/cli/main.py:status](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L789)

用法:
```bash
uv run btbt status
```

## 检查点命令

检查点管理组: [ccbt/cli/main.py:checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L849)

### checkpoints list

列出所有可用的检查点。

实现: [ccbt/cli/main.py:list_checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L863)

用法:
```bash
uv run btbt checkpoints list [--format json|table]
```

### checkpoints clean

清理旧检查点。

实现: [ccbt/cli/main.py:clean_checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L930)

用法:
```bash
uv run btbt checkpoints clean [--days <n>] [--dry-run]
```

### checkpoints delete

删除特定检查点。

实现: [ccbt/cli/main.py:delete_checkpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L978)

用法:
```bash
uv run btbt checkpoints delete <info_hash>
```

### checkpoints verify

验证检查点。

实现: [ccbt/cli/main.py:verify_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1016)

用法:
```bash
uv run btbt checkpoints verify <info_hash>
```

### checkpoints export

将检查点导出到文件。

实现: [ccbt/cli/main.py:export_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1058)

用法:
```bash
uv run btbt checkpoints export <info_hash> [--format json|binary] [--output <path>]
```

### checkpoints backup

将检查点备份到位置。

实现: [ccbt/cli/main.py:backup_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1099)

用法:
```bash
uv run btbt checkpoints backup <info_hash> <destination> [--compress] [--encrypt]
```

### checkpoints restore

从备份恢复检查点。

实现: [ccbt/cli/main.py:restore_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1138)

用法:
```bash
uv run btbt checkpoints restore <backup_file> [--info-hash <hash>]
```

### checkpoints migrate

在格式之间迁移检查点。

实现: [ccbt/cli/main.py:migrate_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1173)

用法:
```bash
uv run btbt checkpoints migrate <info_hash> --from <format> --to <format>
```

### resume

从检查点恢复下载。

实现: [ccbt/cli/main.py:resume](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1204)

用法:
```bash
uv run btbt resume <info_hash> [--output <dir>] [--interactive]
```

## 监控命令

监控命令组: [ccbt/cli/monitoring_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py)

### dashboard

启动终端监控仪表板（Bitonic）。

实现: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L20)

用法:
```bash
uv run btbt dashboard [--refresh <seconds>] [--rules <path>]
```

详细用法请参见 [Bitonic指南](bitonic.md)。

### alerts

管理警报规则和活动警报。

实现: [ccbt/cli/monitoring_commands.py:alerts](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L48)

用法:
```bash
# 列出警报规则
uv run btbt alerts --list

# 列出活动警报
uv run btbt alerts --list-active

# 添加警报规则
uv run btbt alerts --add --name <name> --metric <metric> --condition "<condition>" --severity <severity>

# 删除警报规则
uv run btbt alerts --remove --name <name>

# 清除所有活动警报
uv run btbt alerts --clear-active

# 测试警报规则
uv run btbt alerts --test --name <name> --value <value>

# 从文件加载规则
uv run btbt alerts --load <path>

# 将规则保存到文件
uv run btbt alerts --save <path>
```

更多信息请参见 [API参考](API.md#monitoring)。

### metrics

收集和导出指标。

实现: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L229)

用法:
```bash
uv run btbt metrics [--format json|prometheus] [--output <path>] [--duration <seconds>] [--interval <seconds>] [--include-system] [--include-performance]
```

示例:
```bash
# 导出JSON指标
uv run btbt metrics --format json --include-system --include-performance

# 导出Prometheus格式
uv run btbt metrics --format prometheus > metrics.txt
```

更多信息请参见 [API参考](API.md#monitoring)。

## 文件选择命令

文件选择命令组: [ccbt/cli/file_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py)

管理多文件种子的文件选择和优先级。

### files list

列出种子中的所有文件及其选择状态、优先级和下载进度。

实现: [ccbt/cli/file_commands.py:files_list](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L28)

用法:
```bash
uv run btbt files list <info_hash>
```

输出包括:
- 文件索引和名称
- 文件大小
- 选择状态（已选择/未选择）
- 优先级级别
- 下载进度

### files select

选择一个或多个文件进行下载。

实现: [ccbt/cli/file_commands.py:files_select](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L72)

用法:
```bash
uv run btbt files select <info_hash> <file_index> [<file_index> ...]
```

示例:
```bash
# 选择文件0、2和5
uv run btbt files select abc123... 0 2 5

# 选择单个文件
uv run btbt files select abc123... 0
```

### files deselect

从下载中取消选择一个或多个文件。

实现: [ccbt/cli/file_commands.py:files_deselect](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L108)

用法:
```bash
uv run btbt files deselect <info_hash> <file_index> [<file_index> ...]
```

### files select-all

选择种子中的所有文件。

实现: [ccbt/cli/file_commands.py:files_select_all](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L144)

用法:
```bash
uv run btbt files select-all <info_hash>
```

### files deselect-all

取消选择种子中的所有文件。

实现: [ccbt/cli/file_commands.py:files_deselect_all](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L161)

用法:
```bash
uv run btbt files deselect-all <info_hash>
```

### files priority

设置特定文件的优先级。

实现: [ccbt/cli/file_commands.py:files_priority](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L178)

用法:
```bash
uv run btbt files priority <info_hash> <file_index> <priority>
```

优先级级别:
- `do_not_download`: 不下载（等同于未选择）
- `low`: 低优先级
- `normal`: 正常优先级（默认）
- `high`: 高优先级
- `maximum`: 最高优先级

示例:
```bash
# 将文件0设置为高优先级
uv run btbt files priority abc123... 0 high

# 将文件2设置为最高优先级
uv run btbt files priority abc123... 2 maximum
```

## 配置命令

配置命令组: [ccbt/cli/config_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/config_commands.py)

### config

管理配置。

实现: [ccbt/cli/main.py:config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L810)

用法:
```bash
uv run btbt config [subcommand]
```

扩展配置命令: [ccbt/cli/config_commands_extended.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/config_commands_extended.py)

详细配置选项请参见 [配置指南](configuration.md)。

## 高级命令

高级命令组: [ccbt/cli/advanced_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py)

### performance

性能分析和基准测试。

实现: [ccbt/cli/advanced_commands.py:performance](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L73)

用法:
```bash
uv run btbt performance [--analyze] [--benchmark]
```

### security

安全分析和验证。

实现: [ccbt/cli/advanced_commands.py:security](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L170)

用法:
```bash
uv run btbt security [options]
```

### recover

恢复操作。

实现: [ccbt/cli/advanced_commands.py:recover](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L209)

用法:
```bash
uv run btbt recover [options]
```

### test

运行测试和诊断。

实现: [ccbt/cli/advanced_commands.py:test](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L248)

用法:
```bash
uv run btbt test [options]
```

## 命令行选项

### 全局选项

全局选项定义位置: [ccbt/cli/main.py:cli](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L243)

- `--config <path>`: 配置文件路径
- `--verbose`: 详细输出
- `--debug`: 调试模式

### CLI覆盖

所有CLI选项按以下顺序覆盖配置:
1. [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py) 的默认值
2. 配置文件（[ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)）
3. 环境变量（[env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)）
4. CLI参数

覆盖实现: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)

## 示例

### 基本下载
```bash
uv run btbt download movie.torrent
```

### 带选项的下载
```bash
uv run btbt download movie.torrent \
  --listen-port 7001 \
  --enable-dht \
  --use-mmap \
  --download-limit 1024 \
  --upload-limit 512
```

### 选择性文件下载
```bash
# 仅下载特定文件
uv run btbt download torrent.torrent --files 0 --files 2 --files 5

# 带文件优先级的下载
uv run btbt download torrent.torrent \
  --file-priority 0=high \
  --file-priority 1=maximum \
  --file-priority 2=low

# 组合: 选择文件并设置优先级
uv run btbt download torrent.torrent \
  --files 0 1 2 \
  --file-priority 0=maximum \
  --file-priority 1=high
```

### 从磁力链接下载
```bash
uv run btbt magnet "magnet:?xt=urn:btih:..." \
  --download-limit 1024 \
  --upload-limit 256
```

### 文件选择管理
```bash
# 列出种子中的文件
uv run btbt files list abc123def456789...

# 下载开始后选择特定文件
uv run btbt files select abc123... 3 4

# 设置文件优先级
uv run btbt files priority abc123... 0 high
uv run btbt files priority abc123... 2 maximum

# 选择/取消选择所有文件
uv run btbt files select-all abc123...
uv run btbt files deselect-all abc123...
```

### 检查点管理
```bash
# 列出检查点
uv run btbt checkpoints list --format json

# 导出检查点
uv run btbt checkpoints export <infohash> --format json --output checkpoint.json

# 清理旧检查点
uv run btbt checkpoints clean --days 7
```

### 每个种子的配置

管理每个种子的配置选项和速率限制。这些设置会持久化到检查点和守护进程状态中。

实现: [ccbt/cli/torrent_config_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/torrent_config_commands.py)

#### 设置每个种子的选项

为特定种子设置配置选项:

```bash
uv run btbt torrent config set <info_hash> <key> <value> [--save-checkpoint]
```

示例:
```bash
# 设置片段选择策略
uv run btbt torrent config set abc123... piece_selection sequential

# 启用流式传输模式
uv run btbt torrent config set abc123... streaming_mode true

# 设置每个种子的最大对等节点数
uv run btbt torrent config set abc123... max_peers_per_torrent 50

# 设置选项并立即保存检查点
uv run btbt torrent config set abc123... piece_selection rarest_first --save-checkpoint
```

#### 获取每个种子的选项

获取特定种子的配置选项值:

```bash
uv run btbt torrent config get <info_hash> <key>
```

示例:
```bash
uv run btbt torrent config get abc123... piece_selection
```

#### 列出所有每个种子的配置

列出种子的所有配置选项和速率限制:

```bash
uv run btbt torrent config list <info_hash>
```

示例:
```bash
uv run btbt torrent config list abc123...
```

输出显示:
- 所有每个种子的选项（piece_selection、streaming_mode等）
- 速率限制（下载/上传，KiB/s）

#### 重置每个种子的配置

重置种子的配置选项:

```bash
uv run btbt torrent config reset <info_hash> [--key <key>]
```

示例:
```bash
# 重置所有每个种子的选项
uv run btbt torrent config reset abc123...

# 重置特定选项
uv run btbt torrent config reset abc123... --key piece_selection
```

**注意**: 每个种子的配置选项在创建检查点时会自动保存到检查点。使用 `set` 时使用 `--save-checkpoint` 可立即持久化更改。在守护进程模式下运行时，这些设置也会持久化到守护进程状态中。

### 监控
```bash
# 启动仪表板
uv run btbt dashboard --refresh 2.0

# 添加警报规则
uv run btbt alerts --add --name cpu_high --metric system.cpu --condition "value > 80" --severity warning

# 导出指标
uv run btbt metrics --format json --include-system --include-performance
```

## 获取帮助

获取任何命令的帮助:
```bash
uv run btbt --help
uv run btbt <command> --help
```

更多信息:
- [Bitonic指南](bitonic.md) - 终端仪表板
- [配置指南](configuration.md) - 配置选项
- [API参考](API.md#monitoring) - 监控和指标
- [性能调优](performance.md) - 优化指南
