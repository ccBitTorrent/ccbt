# 入门

欢迎使用 ccBitTorrent！本指南将帮助您快速开始使用我们的高性能 BitTorrent 客户端。

!!! tip "关键功能：BEP XET 协议扩展"
    ccBitTorrent 包含 **Xet 协议扩展 (BEP XET)**，它支持内容定义分块和跨 Torrent 去重。这使 BitTorrent 转变为为协作优化的超快速、可更新的点对点文件系统。[了解更多关于 BEP XET →](bep_xet.md)

## 安装

### 先决条件

- Python 3.8 或更高版本
- [UV](https://astral.sh/uv) 包管理器（推荐）

### 安装 UV

从官方安装脚本安装 UV：
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### 安装 ccBitTorrent

从 PyPI 安装：
```bash
uv pip install ccbittorrent
```

或从源代码安装：
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

入口点定义在 [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81)。

## 主要入口点

ccBitTorrent 提供三个主要入口点：

### 1. Bitonic（推荐）

**Bitonic** 是主终端仪表板界面。它提供所有 torrent、对等节点和系统指标的实时交互视图。

- 入口点: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- 定义位置: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- 启动: `uv run bitonic` 或 `uv run ccbt dashboard`

详细用法请参阅 [Bitonic 指南](bitonic.md)。

### 2. btbt CLI

**btbt** 是具有丰富功能的增强命令行界面。

- 入口点: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- 定义位置: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- 启动: `uv run btbt`

所有可用命令请参阅 [btbt CLI 参考](btbt-cli.md)。

### 3. ccbt（基本 CLI）

**ccbt** 是基本命令行界面。

- 入口点: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- 定义位置: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- 启动: `uv run ccbt`

## 快速开始

### 启动 Bitonic（推荐）

启动终端仪表板：
```bash
uv run bitonic
```

或通过 CLI：
```bash
uv run ccbt dashboard
```

使用自定义刷新率：
```bash
uv run ccbt dashboard --refresh 2.0
```

### 下载 Torrent

使用 CLI：
```bash
# 从 torrent 文件下载
uv run btbt download movie.torrent

# 从磁力链接下载
uv run btbt magnet "magnet:?xt=urn:btih:..."

# 带速率限制
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

所有下载选项请参阅 [btbt CLI 参考](btbt-cli.md)。

### 配置 ccBitTorrent

在工作目录中创建 `ccbt.toml` 文件。参考示例配置：
- 默认配置: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- 环境变量: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- 配置系统: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

详细配置选项请参阅 [配置指南](configuration.md)。

## 项目报告

查看项目质量指标和报告：

- **代码覆盖率**: [reports/coverage.md](reports/coverage.md) - 全面的代码覆盖率分析
- **安全报告**: [reports/bandit/index.md](reports/bandit/index.md) - Bandit 的安全扫描结果
- **基准测试**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - 性能基准测试结果

这些报告作为我们持续集成流程的一部分自动生成和更新。

## 下一步

- [Bitonic](bitonic.md) - 了解终端仪表板界面
- [btbt CLI](btbt-cli.md) - 完整的命令行界面参考
- [配置](configuration.md) - 详细的配置选项
- [性能调优](performance.md) - 优化指南
- [API 参考](API.md) - 包含监控功能的 Python API 文档

## 获取帮助

- 使用 `uv run bitonic --help` 或 `uv run btbt --help` 获取命令帮助
- 查看 [btbt CLI 参考](btbt-cli.md) 了解详细选项
- 访问我们的 [GitHub 仓库](https://github.com/yourusername/ccbittorrent) 获取问题和讨论






欢迎使用 ccBitTorrent！本指南将帮助您快速开始使用我们的高性能 BitTorrent 客户端。

!!! tip "关键功能：BEP XET 协议扩展"
    ccBitTorrent 包含 **Xet 协议扩展 (BEP XET)**，它支持内容定义分块和跨 Torrent 去重。这使 BitTorrent 转变为为协作优化的超快速、可更新的点对点文件系统。[了解更多关于 BEP XET →](bep_xet.md)

## 安装

### 先决条件

- Python 3.8 或更高版本
- [UV](https://astral.sh/uv) 包管理器（推荐）

### 安装 UV

从官方安装脚本安装 UV：
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### 安装 ccBitTorrent

从 PyPI 安装：
```bash
uv pip install ccbittorrent
```

或从源代码安装：
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

入口点定义在 [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81)。

## 主要入口点

ccBitTorrent 提供三个主要入口点：

### 1. Bitonic（推荐）

**Bitonic** 是主终端仪表板界面。它提供所有 torrent、对等节点和系统指标的实时交互视图。

- 入口点: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- 定义位置: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- 启动: `uv run bitonic` 或 `uv run ccbt dashboard`

详细用法请参阅 [Bitonic 指南](bitonic.md)。

### 2. btbt CLI

**btbt** 是具有丰富功能的增强命令行界面。

- 入口点: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- 定义位置: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- 启动: `uv run btbt`

所有可用命令请参阅 [btbt CLI 参考](btbt-cli.md)。

### 3. ccbt（基本 CLI）

**ccbt** 是基本命令行界面。

- 入口点: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- 定义位置: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- 启动: `uv run ccbt`

## 快速开始

### 启动 Bitonic（推荐）

启动终端仪表板：
```bash
uv run bitonic
```

或通过 CLI：
```bash
uv run ccbt dashboard
```

使用自定义刷新率：
```bash
uv run ccbt dashboard --refresh 2.0
```

### 下载 Torrent

使用 CLI：
```bash
# 从 torrent 文件下载
uv run btbt download movie.torrent

# 从磁力链接下载
uv run btbt magnet "magnet:?xt=urn:btih:..."

# 带速率限制
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

所有下载选项请参阅 [btbt CLI 参考](btbt-cli.md)。

### 配置 ccBitTorrent

在工作目录中创建 `ccbt.toml` 文件。参考示例配置：
- 默认配置: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- 环境变量: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- 配置系统: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

详细配置选项请参阅 [配置指南](configuration.md)。

## 项目报告

查看项目质量指标和报告：

- **代码覆盖率**: [reports/coverage.md](reports/coverage.md) - 全面的代码覆盖率分析
- **安全报告**: [reports/bandit/index.md](reports/bandit/index.md) - Bandit 的安全扫描结果
- **基准测试**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - 性能基准测试结果

这些报告作为我们持续集成流程的一部分自动生成和更新。

## 下一步

- [Bitonic](bitonic.md) - 了解终端仪表板界面
- [btbt CLI](btbt-cli.md) - 完整的命令行界面参考
- [配置](configuration.md) - 详细的配置选项
- [性能调优](performance.md) - 优化指南
- [API 参考](API.md) - 包含监控功能的 Python API 文档

## 获取帮助

- 使用 `uv run bitonic --help` 或 `uv run btbt --help` 获取命令帮助
- 查看 [btbt CLI 参考](btbt-cli.md) 了解详细选项
- 访问我们的 [GitHub 仓库](https://github.com/yourusername/ccbittorrent) 获取问题和讨论
































































































































































































