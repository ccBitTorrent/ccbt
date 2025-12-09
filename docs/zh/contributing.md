# 贡献指南

感谢您对 ccBitTorrent 的贡献兴趣！本文档概述了开发过程、代码标准和贡献工作流程。

!!! note "翻译状态"
    本文档需要从英文版本完整翻译。请参考 [docs/en/contributing.md](../en/contributing.md) 获取最新内容。

## 项目概述

ccBitTorrent 是用 Python 实现的高性能 BitTorrent 客户端。这是一个**参考 Python 实现**，在 **GPL** 许可下发布。该项目旨在提供一个完整、经过充分测试且高性能的 BitTorrent 客户端。

## 开发设置

### 先决条件

- Python 3.8 或更高版本
- [UV](https://github.com/astral-sh/uv) 包管理器（推荐）
- Git

### 初始设置

1. 克隆仓库:
```bash
git clone https://github.com/ccBittorrent/ccbt.git
cd ccbt
```

2. 使用 UV 安装依赖:
```bash
uv sync --dev
```

3. 安装 pre-commit 钩子:
```bash
uv run pre-commit install --config dev/pre-commit-config.yaml
```

## 代码质量标准

### 代码检查

我们使用 [Ruff](https://github.com/astral-sh/ruff) 进行快速代码检查和格式化。配置在 [dev/ruff.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ruff.toml)。

运行代码检查:
```bash
uv run ruff --config dev/ruff.toml check ccbt/ --fix --exit-non-zero-on-fix
```

格式化代码:
```bash
uv run ruff --config dev/ruff.toml format ccbt/
```

### 类型检查

我们使用 [Ty](https://github.com/astral-sh/ty) 进行快速类型检查。配置在 [dev/ty.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ty.toml)。

运行类型检查:
```bash
uv run ty check --config-file=dev/ty.toml --output-format=concise
```

### 测试

我们使用 [pytest](https://pytest.org/) 进行测试。配置在 [dev/pytest.ini](https://github.com/ccBittorrent/ccbt/blob/main/dev/pytest.ini)。

运行所有测试:
```bash
uv run pytest -c dev/pytest.ini tests/ -v
```

运行覆盖率测试:
```bash
uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=html --cov-report=xml
```

### Pre-commit 钩子

所有质量检查通过 [dev/pre-commit-config.yaml](https://github.com/ccBittorrent/ccbt/blob/main/dev/pre-commit-config.yaml) 中配置的 pre-commit 钩子自动运行。这包括:

- Ruff 代码检查和格式化
- Ty 类型检查
- Bandit 安全扫描
- 带覆盖率的 Pytest
- 基准测试冒烟测试
- MkDocs 构建验证: `uv run mkdocs build -f dev/mkdocs.yml`
- 翻译验证: `uv run python -m ccbt.i18n.scripts.validate_po`
- 翻译覆盖率检查: `uv run python -m ccbt.i18n.scripts.check_string_coverage --source-dir ccbt`

手动运行:
```bash
uv run pre-commit run --all-files -c dev/pre-commit-config.yaml
```

!!! note "翻译验证"
    在提交影响可翻译字符串的更改之前:
    1. 重新生成 `.pot` 模板: `uv run python -m ccbt.i18n.scripts.extract`
    2. 验证 PO 文件: `uv run python -m ccbt.i18n.scripts.validate_po`
    3. 检查翻译覆盖率: `uv run python -m ccbt.i18n.scripts.check_string_coverage --source-dir ccbt`

## 开发配置

所有开发配置文件位于 [dev/](dev/):

- [dev/pre-commit-config.yaml](https://github.com/ccBittorrent/ccbt/blob/main/dev/pre-commit-config.yaml) - Pre-commit 钩子配置
- [dev/ruff.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ruff.toml) - Ruff 代码检查和格式化
- [dev/ty.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ty.toml) - 类型检查配置
- [dev/pytest.ini](https://github.com/ccBittorrent/ccbt/blob/main/dev/pytest.ini) - 测试配置
- [dev/mkdocs.yml](https://github.com/ccBittorrent/ccbt/blob/main/dev/mkdocs.yml) - 文档配置

## 分支策略

### Main 分支

- `main` 分支用于发布
- 仅接受来自 `dev` 分支的合并
- 推送到 main 时自动构建发布

### Dev 分支

- `dev` 分支是主要开发分支
- **唯一合并到 main 的分支**
- 运行与 main 相同的所有检查，包括:
  - 所有代码检查和类型检查
  - 带覆盖率的完整测试套件
  - 来自 [dev/pre-commit-config.yaml:39-68](https://github.com/ccBittorrent/ccbt/blob/main/dev/pre-commit-config.yaml#L39-L68) 的所有基准测试检查
  - 文档构建

### 功能分支

直接从以下位置创建功能分支:
- **子问题**: 如果处理特定部分，直接从子问题分支
- **主问题**: 如果处理完整范围，从主问题分支
- **GitHub 模板**: 使用 GitHub 问题模板创建问题，然后通过 GitHub UI 创建分支

## 问题工作流程

### 讨论

开发领域和功能在 GitHub Discussions 中讨论。从这些讨论中产生:

1. **主问题**: 高级功能或改进请求
2. **子问题**: 与主问题相关的特定任务或组件

### 创建问题

1. 使用提供的 GitHub 问题模板
2. 如果适用，链接到相关讨论
3. 根据需要为主功能或子任务创建问题

### 分支创建

- 使用 GitHub UI 直接在子问题或主问题上创建分支
- 分支名称应具有描述性并引用问题编号
- 示例: `feature/dht-improvements-123` 或 `fix/peer-connection-bug-456`

## 贡献流程

### 进行更改

1. **Fork 或创建分支**: 从适当的问题创建分支
2. **进行更改**: 遵循代码质量标准
3. **本地测试**: 推送前运行所有检查:
   ```bash
   uv run pre-commit run --all-files -c dev/pre-commit-config.yaml
   ```
4. **提交**: 使用约定式提交消息
5. **推送**: 推送到您的分支
6. **创建 PR**: 向 `dev` 分支提交拉取请求

### 自动化检查

创建拉取请求时，CI/CD 将自动:

1. **数字 CLA 签名**: 贡献者需要在 CI/CD 中数字签名 CLA
2. 运行所有代码检查 (Ruff) - 参见 [Lint 工作流程](CI_CD.md#lint-workflow-githubworkflowslintyml)
3. 运行类型检查 (Ty) - 参见 [Lint 工作流程](CI_CD.md#lint-workflow-githubworkflowslintyml)
4. 运行带覆盖率要求的完整测试套件 - 参见 [测试工作流程](CI_CD.md#test-workflow-githubworkflowstestyml)
5. 运行基准测试冒烟测试 - 参见 [基准测试工作流程](CI_CD.md#benchmark-workflow-githubworkflowsbenchmarkyml)
6. 构建文档 - 参见 [文档工作流程](CI_CD.md#documentation-workflow-githubworkflowsdocsyml)
7. 检查代码覆盖率阈值 - 参见 [覆盖率要求](CI_CD.md#coverage-requirements)

详细的 CI/CD 文档，请参见 [CI/CD 文档](CI_CD.md)。

### 代码覆盖率

我们保持高代码覆盖率标准。生成覆盖率报告，必须满足最低阈值。在 [reports/coverage.md](reports/coverage.md) 中查看覆盖率报告。

### 基准测试要求

来自 [dev/pre-commit-config.yaml:39-68](https://github.com/ccBittorrent/ccbt/blob/main/dev/pre-commit-config.yaml#L39-L68) 的基准测试检查必须通过。这些包括:

- 哈希验证基准测试
- 磁盘 I/O 基准测试
- 片段组装基准测试
- 环回吞吐量基准测试

如果基准测试失败，贡献可能需要优化或讨论。

## 项目维护

### 自动接受

通过所有自动化检查（代码检查、类型检查、测试、基准测试、覆盖率）的贡献通常会自动接受，除非:

- 基准测试失败（可能需要优化）
- 与项目方向冲突（罕见）
- 安全问题（单独处理）

### 手动审查

维护者可能手动审查:
- 架构对齐
- 性能影响
- 安全考虑
- 文档质量

## 文档标准

- 所有公共 API 必须记录
- 使用 Google 风格的文档字符串
- 保持文档与代码更改同步
- 本地构建文档: `uv run mkdocs build --strict -f dev/mkdocs.yml`
- 文档源位于 [docs/](docs/)

### 贡献文档

贡献文档时:

1. **更新现有文档**: 保持文档与代码更改同步
2. **添加新文档**: 根据需要创建新的文档页面
3. **测试构建**: 提交前始终在本地测试文档构建
4. **遵循样式**: 保持与现有文档样式的一致性
5. **检查链接**: 验证所有内部和外部链接正常工作

文档在 CI/CD 中自动构建。详细信息请参见 [文档工作流程](CI_CD.md#documentation-workflow-githubworkflowsdocsyml)。

### 贡献翻译

通过贡献翻译帮助 ccBitTorrent 面向全球用户！

**翻译流程:**

1. **选择语言**: 从支持列表中选择语言（参见 [翻译指南](i18n/translation-guide.md)）
2. **选择内容**: 选择要翻译的文档页面
3. **创建翻译**: 翻译内容，同时保持:
   - Markdown 格式
   - 代码示例（保持原始语言）
   - 文件结构
   - 链接结构
4. **测试构建**: 验证翻译在文档构建中正常工作
5. **提交 PR**: 使用您的翻译创建拉取请求

**翻译指南:**

- 保持技术准确性
- 保持代码示例为原始语言
- 更新内部链接到翻译版本
- 遵循 [翻译指南](i18n/translation-guide.md) 获取详细说明
- 测试语言切换器功能

详细的翻译说明，请参见 [翻译指南](i18n/translation-guide.md)。

## 许可证

本项目在 **GPL**（GNU 通用公共许可证）下许可。通过贡献，您同意您的贡献将在同一许可证下许可。

## 获取帮助

- **问题**: 为错误或功能请求创建问题
- **讨论**: 使用 GitHub Discussions 进行问题和设计讨论
- **代码审查**: 所有 PR 都会收到维护者的代码审查

