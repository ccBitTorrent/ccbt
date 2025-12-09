# 配置指南

ccBitTorrent 使用具有 TOML 支持、验证、热重载和从多个源进行分层加载的综合配置系统。

配置系统: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## 配置源和优先级

配置按以下顺序加载（后面的源会覆盖前面的源）：

1. **默认值**: 来自 [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) 的内置合理默认值
2. **配置文件**: 当前目录或 `~/.config/ccbt/ccbt.toml` 中的 `ccbt.toml`。参见: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **环境变量**: `CCBT_*` 前缀变量。参见: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI 参数**: 命令行覆盖。参见: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **每个 Torrent**: 单个 torrent 设置（未来功能）

配置加载: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## 配置文件

### 默认配置

参考默认配置文件: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

配置按部分组织：

### 网络配置

网络设置: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- 连接限制: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- 请求管道: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- Socket 调优: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- 超时: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- 监听设置: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- 传输协议: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- 速率限制: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- 阻塞策略: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- Tracker 设置: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

网络配置模型: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 磁盘配置

磁盘设置: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- 预分配: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- 写入优化: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- 哈希验证: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O 线程: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- 高级设置: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- 存储服务设置: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: 存储服务的最大文件大小限制（MB）（0 或 None = 无限制，最大 1048576 = 1TB）。防止测试期间无限制的磁盘写入，可为生产使用进行配置。
- 检查点设置: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

磁盘配置模型: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 策略配置

策略设置: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- 片段选择: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- 高级策略: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- 片段优先级: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

策略配置模型: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 发现配置

发现设置: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT 设置: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX 设置: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- Tracker 设置: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Tracker 通告间隔（秒）（默认: 1800.0，范围: 60.0-86400.0）
  - `tracker_scrape_interval`: 定期抓取的 Tracker 抓取间隔（秒）（默认: 3600.0，范围: 60.0-86400.0）
  - `tracker_auto_scrape`: 添加 torrent 时自动抓取 tracker（BEP 48）（默认: false）
  - 环境变量: `CCBT_TRACKER_ANNOUNCE_INTERVAL`、`CCBT_TRACKER_SCRAPE_INTERVAL`、`CCBT_TRACKER_AUTO_SCRAPE`

发现配置模型: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 限制配置

速率限制: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- 全局限制: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- 每个 Torrent 限制: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- 每个对等节点限制: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- 调度器设置: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

限制配置模型: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 可观测性配置

可观测性设置: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- 日志记录: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- 指标: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- 跟踪和警报: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

可观测性配置模型: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 安全配置

安全设置: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

安全配置模型: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### 加密配置

ccBitTorrent 支持 BEP 3 Message Stream Encryption (MSE) 和 Protocol Encryption (PE) 以实现安全的对等节点连接。

**加密设置:**

- `enable_encryption` (bool, 默认: `false`): 启用协议加密支持
- `encryption_mode` (str, 默认: `"preferred"`): 加密模式
  - `"disabled"`: 无加密（仅纯文本连接）
  - `"preferred"`: 尝试加密，如果不可用则回退到纯文本
  - `"required"`: 加密必需，如果加密不可用则连接失败
- `encryption_dh_key_size` (int, 默认: `768`): Diffie-Hellman 密钥大小（位）（768 或 1024）
- `encryption_prefer_rc4` (bool, 默认: `true`): 为与旧客户端兼容而优先使用 RC4 密码
- `encryption_allowed_ciphers` (list[str], 默认: `["rc4", "aes"]`): 允许的密码类型
  - `"rc4"`: RC4 流密码（最兼容）
  - `"aes"`: CFB 模式下的 AES 密码（更安全）
  - `"chacha20"`: ChaCha20 密码（尚未实现）
- `encryption_allow_plain_fallback` (bool, 默认: `true`): 如果加密失败，允许回退到纯文本连接（仅在 `encryption_mode` 为 `"preferred"` 时适用）

**环境变量:**

- `CCBT_ENABLE_ENCRYPTION`: 启用/禁用加密 (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: 加密模式 (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DH 密钥大小 (`768` 或 `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: 优先使用 RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: 逗号分隔列表（例如 `"rc4,aes"`）
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: 允许纯文本回退 (`true`/`false`)

**配置示例:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**安全注意事项:**

1. **RC4 兼容性**: RC4 为兼容性而支持，但加密强度较弱。尽可能使用 AES 以获得更好的安全性。
2. **DH 密钥大小**: 768 位 DH 密钥为大多数用例提供足够的安全性。1024 位提供更强的安全性，但会增加握手延迟。
3. **加密模式**:
   - `preferred`: 最适合兼容性 - 尝试加密但优雅地回退
   - `required`: 最安全，但可能无法连接到不支持加密的对等节点
4. **性能影响**: 加密增加最小开销（RC4 约 1-5%，AES 约 2-8%），但提高隐私性并有助于避免流量整形。

**实现细节:**

加密实现: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE 握手: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- 密码套件: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman 交换: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML 配置

机器学习设置: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML 配置模型: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 仪表板配置

仪表板设置: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

仪表板配置模型: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## 环境变量

环境变量使用 `CCBT_` 前缀并遵循分层命名方案。

参考: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

格式: `CCBT_<SECTION>_<OPTION>=<value>`

示例:
- 网络: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- 磁盘: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- 策略: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- 发现: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- 可观测性: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- 限制: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- 安全: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

环境变量解析: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## 配置架构

配置架构和验证: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

架构定义:
- 字段类型和约束
- 默认值
- 验证规则
- 文档

## 配置功能

配置功能和特性检测: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## 配置模板

预定义配置模板: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

模板:
- 高性能设置
- 低资源设置
- 安全优先设置
- 开发设置

## 配置示例

示例配置在 [examples/](examples/) 目录中可用：

- 基本配置: [example-config-basic.toml](examples/example-config-basic.toml)
- 高级配置: [example-config-advanced.toml](examples/example-config-advanced.toml)
- 性能配置: [example-config-performance.toml](examples/example-config-performance.toml)
- 安全配置: [example-config-security.toml](examples/example-config-security.toml)

## 热重载

配置热重载支持: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

配置系统支持在不重启客户端的情况下重新加载更改。

## 配置迁移

配置迁移实用工具: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

在配置版本之间迁移的工具。

## 配置备份和差异

配置管理实用工具:
- 备份: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- 差异: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## 条件配置

条件配置支持: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## 提示和最佳实践

### 性能调优

- 增加 `disk.write_buffer_kib` 用于大型顺序写入: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- 在 Linux/NVMe 上启用 `direct_io` 以提高写入吞吐量: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- 根据您的网络调整 `network.pipeline_depth` 和 `network.block_size_kib`: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### 资源优化

- 根据 CPU 核心数调整 `disk.hash_workers`: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- 根据可用 RAM 配置 `disk.cache_size_mb`: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- 根据带宽设置 `network.max_global_peers`: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### 网络配置

- 根据网络条件配置超时: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- 根据需要启用/禁用协议: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- 适当设置速率限制: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

有关详细的性能调优，请参阅 [性能调优指南](performance.md)。






ccBitTorrent 使用具有 TOML 支持、验证、热重载和从多个源进行分层加载的综合配置系统。

配置系统: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## 配置源和优先级

配置按以下顺序加载（后面的源会覆盖前面的源）：

1. **默认值**: 来自 [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) 的内置合理默认值
2. **配置文件**: 当前目录或 `~/.config/ccbt/ccbt.toml` 中的 `ccbt.toml`。参见: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **环境变量**: `CCBT_*` 前缀变量。参见: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI 参数**: 命令行覆盖。参见: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **每个 Torrent**: 单个 torrent 设置（未来功能）

配置加载: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## 配置文件

### 默认配置

参考默认配置文件: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

配置按部分组织：

### 网络配置

网络设置: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- 连接限制: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- 请求管道: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- Socket 调优: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- 超时: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- 监听设置: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- 传输协议: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- 速率限制: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- 阻塞策略: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- Tracker 设置: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

网络配置模型: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 磁盘配置

磁盘设置: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- 预分配: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- 写入优化: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- 哈希验证: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O 线程: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- 高级设置: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- 存储服务设置: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: 存储服务的最大文件大小限制（MB）（0 或 None = 无限制，最大 1048576 = 1TB）。防止测试期间无限制的磁盘写入，可为生产使用进行配置。
- 检查点设置: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

磁盘配置模型: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 策略配置

策略设置: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- 片段选择: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- 高级策略: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- 片段优先级: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

策略配置模型: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 发现配置

发现设置: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT 设置: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX 设置: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- Tracker 设置: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Tracker 通告间隔（秒）（默认: 1800.0，范围: 60.0-86400.0）
  - `tracker_scrape_interval`: 定期抓取的 Tracker 抓取间隔（秒）（默认: 3600.0，范围: 60.0-86400.0）
  - `tracker_auto_scrape`: 添加 torrent 时自动抓取 tracker（BEP 48）（默认: false）
  - 环境变量: `CCBT_TRACKER_ANNOUNCE_INTERVAL`、`CCBT_TRACKER_SCRAPE_INTERVAL`、`CCBT_TRACKER_AUTO_SCRAPE`

发现配置模型: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 限制配置

速率限制: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- 全局限制: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- 每个 Torrent 限制: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- 每个对等节点限制: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- 调度器设置: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

限制配置模型: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 可观测性配置

可观测性设置: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- 日志记录: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- 指标: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- 跟踪和警报: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

可观测性配置模型: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 安全配置

安全设置: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

安全配置模型: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### 加密配置

ccBitTorrent 支持 BEP 3 Message Stream Encryption (MSE) 和 Protocol Encryption (PE) 以实现安全的对等节点连接。

**加密设置:**

- `enable_encryption` (bool, 默认: `false`): 启用协议加密支持
- `encryption_mode` (str, 默认: `"preferred"`): 加密模式
  - `"disabled"`: 无加密（仅纯文本连接）
  - `"preferred"`: 尝试加密，如果不可用则回退到纯文本
  - `"required"`: 加密必需，如果加密不可用则连接失败
- `encryption_dh_key_size` (int, 默认: `768`): Diffie-Hellman 密钥大小（位）（768 或 1024）
- `encryption_prefer_rc4` (bool, 默认: `true`): 为与旧客户端兼容而优先使用 RC4 密码
- `encryption_allowed_ciphers` (list[str], 默认: `["rc4", "aes"]`): 允许的密码类型
  - `"rc4"`: RC4 流密码（最兼容）
  - `"aes"`: CFB 模式下的 AES 密码（更安全）
  - `"chacha20"`: ChaCha20 密码（尚未实现）
- `encryption_allow_plain_fallback` (bool, 默认: `true`): 如果加密失败，允许回退到纯文本连接（仅在 `encryption_mode` 为 `"preferred"` 时适用）

**环境变量:**

- `CCBT_ENABLE_ENCRYPTION`: 启用/禁用加密 (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: 加密模式 (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DH 密钥大小 (`768` 或 `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: 优先使用 RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: 逗号分隔列表（例如 `"rc4,aes"`）
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: 允许纯文本回退 (`true`/`false`)

**配置示例:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**安全注意事项:**

1. **RC4 兼容性**: RC4 为兼容性而支持，但加密强度较弱。尽可能使用 AES 以获得更好的安全性。
2. **DH 密钥大小**: 768 位 DH 密钥为大多数用例提供足够的安全性。1024 位提供更强的安全性，但会增加握手延迟。
3. **加密模式**:
   - `preferred`: 最适合兼容性 - 尝试加密但优雅地回退
   - `required`: 最安全，但可能无法连接到不支持加密的对等节点
4. **性能影响**: 加密增加最小开销（RC4 约 1-5%，AES 约 2-8%），但提高隐私性并有助于避免流量整形。

**实现细节:**

加密实现: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE 握手: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- 密码套件: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman 交换: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML 配置

机器学习设置: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML 配置模型: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 仪表板配置

仪表板设置: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

仪表板配置模型: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## 环境变量

环境变量使用 `CCBT_` 前缀并遵循分层命名方案。

参考: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

格式: `CCBT_<SECTION>_<OPTION>=<value>`

示例:
- 网络: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- 磁盘: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- 策略: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- 发现: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- 可观测性: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- 限制: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- 安全: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

环境变量解析: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## 配置架构

配置架构和验证: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

架构定义:
- 字段类型和约束
- 默认值
- 验证规则
- 文档

## 配置功能

配置功能和特性检测: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## 配置模板

预定义配置模板: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

模板:
- 高性能设置
- 低资源设置
- 安全优先设置
- 开发设置

## 配置示例

示例配置在 [examples/](examples/) 目录中可用：

- 基本配置: [example-config-basic.toml](examples/example-config-basic.toml)
- 高级配置: [example-config-advanced.toml](examples/example-config-advanced.toml)
- 性能配置: [example-config-performance.toml](examples/example-config-performance.toml)
- 安全配置: [example-config-security.toml](examples/example-config-security.toml)

## 热重载

配置热重载支持: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

配置系统支持在不重启客户端的情况下重新加载更改。

## 配置迁移

配置迁移实用工具: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

在配置版本之间迁移的工具。

## 配置备份和差异

配置管理实用工具:
- 备份: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- 差异: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## 条件配置

条件配置支持: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## 提示和最佳实践

### 性能调优

- 增加 `disk.write_buffer_kib` 用于大型顺序写入: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- 在 Linux/NVMe 上启用 `direct_io` 以提高写入吞吐量: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- 根据您的网络调整 `network.pipeline_depth` 和 `network.block_size_kib`: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### 资源优化

- 根据 CPU 核心数调整 `disk.hash_workers`: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- 根据可用 RAM 配置 `disk.cache_size_mb`: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- 根据带宽设置 `network.max_global_peers`: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### 网络配置

- 根据网络条件配置超时: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- 根据需要启用/禁用协议: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- 适当设置速率限制: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

有关详细的性能调优，请参阅 [性能调优指南](performance.md)。
































































































































































































