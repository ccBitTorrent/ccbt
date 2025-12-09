# CI/CD 文档

本文档描述了 ccBitTorrent 的持续集成和持续部署 (CI/CD) 设置。

## 概述

ccBitTorrent 使用 GitHub Actions 进行自动化测试、构建和部署。CI/CD 管道确保代码质量、全面测试和自动化发布。

## 工作流程概述

### 核心工作流程

1. **Lint** (`.github/workflows/lint.yml`) - 代码质量检查
2. **Test** (`.github/workflows/test.yml`) - 全面测试套件
3. **Security** (`.github/workflows/security.yml`) - 安全扫描
4. **Benchmark** (`.github/workflows/benchmark.yml`) - 性能基准测试
5. **Build** (`.github/workflows/build.yml`) - 包和可执行文件构建
6. **Deploy** (`.github/workflows/deploy.yml`) - PyPI 和 GitHub Releases
7. **Documentation** (`.github/workflows/docs.yml`) - 文档构建和部署
8. **Compatibility** (`.github/workflows/compatibility.yml`) - 容器化测试

### 发布工作流程

9. **Release** (`.github/workflows/release.yml`) - 自动化发布流程
10. **Pre-Release** (`.github/workflows/pre-release.yml`) - 发布前验证
11. **Version Check** (`.github/workflows/version-check.yml`) - 版本一致性

## CI 中的测试

### 测试工作流程 (`.github/workflows/test.yml`)

测试工作流程在多个平台和 Python 版本上运行完整的测试套件。

#### 测试矩阵

- **操作系统**: Ubuntu, Windows, macOS
- **Python 版本**: 3.8, 3.9, 3.10, 3.11, 3.12
- **排除**: 为加快 CI 速度而减少矩阵（Windows/macOS 跳过 3.8/3.9）

#### 测试执行

```yaml
uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=xml --cov-report=html --cov-report=term-missing
```

#### 覆盖率报告

- 覆盖率从主要测试作业（Ubuntu + Python 3.11）上传到 Codecov
- 以 XML、HTML 和终端格式生成覆盖率报告
- 强制执行覆盖率阈值:
  - **项目**: 99% (±1%)
  - **补丁**: 90% (±2%)

#### 测试工件

测试工件上传用于调试:
- `coverage.xml` - Codecov 兼容的覆盖率报告
- `htmlcov/` - HTML 覆盖率报告
- `site/reports/junit.xml` - JUnit XML 测试结果
- `site/reports/pytest.log` - 测试执行日志

### 与测试模式的集成

CI 工作流程遵循项目中定义的测试模式:

#### 测试标记

CI 运行所有测试而不进行标记过滤，确保全面覆盖。测试套件包括:

- **单元测试** (`tests/unit/`) - 单个组件测试
- **集成测试** (`tests/integration/`) - 组件工作流程测试
- **基于属性的测试** (`tests/property/`) - 基于 Hypothesis 的测试
- **性能测试** (`tests/performance/`) - 基准验证
- **混沌测试** (`tests/chaos/`) - 弹性测试

#### 异步测试

所有异步测试使用 `asyncio_mode = auto`，如 `dev/pytest.ini` 中配置。CI 环境正确处理异步测试执行。

#### 超时

测试使用默认超时（每个测试 300 秒），如 pytest 中配置。覆盖率运行使用扩展超时（600 秒）以处理全面的测试套件。

### Pre-Commit vs CI

**Pre-commit 钩子**（本地开发）:
- 基于更改的文件运行选择性测试
- 使用 `tests/scripts/run_pytest_selective.py` 进行高效的本地测试
- 为开发人员提供快速反馈循环

**CI 工作流程**（远程验证）:
- 在所有平台上运行完整测试套件
- 全面的覆盖率报告
- 平台特定验证

## 代码质量检查

### Lint 工作流程 (`.github/workflows/lint.yml`)

运行代码质量检查:

1. **Ruff 代码检查**
   ```bash
   uv run ruff --config dev/ruff.toml check ccbt/ --fix --exit-non-zero-on-fix
   ```

2. **Ruff 格式化**
   ```bash
   uv run ruff --config dev/ruff.toml format --check ccbt/
   ```

3. **Ty 类型检查**
   ```bash
   uv run ty check --config-file=dev/ty.toml --output-format=concise
   ```

### 安全工作流程 (`.github/workflows/security.yml`)

运行安全扫描:

1. **Bandit 安全扫描**
   - 扫描常见安全问题
   - 生成 JSON 报告到 `docs/reports/bandit/bandit-report.json`
   - 中等严重性阈值

2. **Safety 依赖检查**
   - 检查依赖项中的已知漏洞
   - 每周按计划运行

## 性能基准测试

### 基准测试工作流程 (`.github/workflows/benchmark.yml`)

在代码更改时运行性能基准测试:

- **哈希验证基准测试** - SHA-1 验证性能
- **磁盘 I/O 基准测试** - 文件读写性能
- **片段组装基准测试** - 片段重建性能
- **环回吞吐量基准测试** - 网络吞吐量
- **加密基准测试** - 加密操作

基准测试在 CI 中以 `--quick` 模式运行，并记录结果以进行趋势分析。

## 构建和部署

### 构建工作流程 (`.github/workflows/build.yml`)

构建包和可执行文件:

1. **包构建**
   - 构建 wheel 和源分发
   - 使用 `twine check` 验证包
   - 在 Ubuntu、Windows 和 macOS 上运行

2. **Windows 可执行文件**
   - 使用 PyInstaller 构建 `bitonic.exe`（终端仪表板）
   - 如果可用，使用 `dev/pyinstaller.spec`，否则使用命令行参数
   - 仅在 Windows 运行器上构建
   - 作为工件上传以供发布

### 部署工作流程 (`.github/workflows/deploy.yml`)

部署到 PyPI 并创建 GitHub Releases:

1. **PyPI 部署**
   - 使用受信任发布 (OIDC) - 不需要令牌
   - 发布前验证包
   - 上传后验证发布

2. **GitHub Release**
   - 下载 Windows 可执行文件工件
   - 将包文件和可执行文件上传到发布
   - 使用自动化注释创建发布

## 文档

### 文档工作流程 (`.github/workflows/docs.yml`)

构建和部署文档:

1. **覆盖率报告生成**
   - 生成 HTML 覆盖率报告
   - 通过 `mkdocs-coverage` 插件与 MkDocs 集成

2. **Bandit 报告生成**
   - 生成安全扫描报告
   - 包含在文档中

3. **MkDocs 构建**
   - 构建文档站点
   - 使用 `--strict` 模式验证

4. **GitHub Pages 部署**
   - 在 `main` 分支上部署到 GitHub Pages
   - 使用自定义域: `ccbittorrent.readthedocs.io`

### 文档和翻译验证

CI 工作流程包括:
- MkDocs 构建验证: `uv run mkdocs build -f dev/mkdocs.yml`
- 翻译验证: `uv run python -m ccbt.i18n.scripts.validate_po`

## 覆盖率要求

### Codecov 集成

通过 Codecov 跟踪覆盖率，具有以下目标:

- **项目覆盖率**: 99% (±1% 容差)
- **补丁覆盖率**: 90% (±2% 容差)

覆盖率通过标志按域分类（来自 `dev/.codecov.yml`）:
- `unittests` - 单元测试覆盖率
- `security` - 安全相关代码覆盖率
- `ml` - 机器学习功能覆盖率
- `core` - 核心 BitTorrent 功能
- `peer` - 对等节点管理
- `piece` - 片段管理
- `tracker` - Tracker 通信
- `network` - 网络层
- `metadata` - 元数据处理
- `disk` - 磁盘 I/O 操作
- `file` - 文件操作
- `session` - 会话管理
- `resilience` - 弹性功能

