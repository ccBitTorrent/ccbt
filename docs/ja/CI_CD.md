# CI/CD ドキュメント

このドキュメントでは、ccBitTorrent の継続的インテグレーションと継続的デプロイメント (CI/CD) の設定について説明します。

!!! note "翻訳状況"
    このドキュメントは英語版から完全に翻訳する必要があります。最新の内容については [docs/en/CI_CD.md](../en/CI_CD.md) を参照してください。

## ワークフロー概要

### コアワークフロー

1. **Lint** (`.github/workflows/lint.yml`) - コード品質チェック
2. **Test** (`.github/workflows/test.yml`) - 包括的なテストスイート
3. **Security** (`.github/workflows/security.yml`) - セキュリティスキャン
4. **Benchmark** (`.github/workflows/benchmark.yml`) - パフォーマンスベンチマーク
5. **Build** (`.github/workflows/build.yml`) - パッケージと実行可能ファイルのビルド
6. **Deploy** (`.github/workflows/deploy.yml`) - PyPI と GitHub Releases
7. **Documentation** (`.github/workflows/docs.yml`) - ドキュメントビルドとデプロイ
8. **Compatibility** (`.github/workflows/compatibility.yml`) - コンテナ化テスト

## CI でのテスト

### テストワークフロー (`.github/workflows/test.yml`)

テストワークフローは、複数のプラットフォームと Python バージョンで完全なテストスイートを実行します。

#### テストマトリックス

- **オペレーティングシステム**: Ubuntu, Windows, macOS
- **Python バージョン**: 3.8, 3.9, 3.10, 3.11, 3.12
- **除外**: より高速な CI のための縮小マトリックス（Windows/macOS は 3.8/3.9 をスキップ）

#### テスト実行

```yaml
uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=xml --cov-report=html --cov-report=term-missing
```

#### カバレッジレポート

- カバレッジは主要なテストジョブ（Ubuntu + Python 3.11）から Codecov にアップロードされます
- カバレッジレポートは XML、HTML、ターミナル形式で生成されます
- カバレッジしきい値が強制されます:
  - **プロジェクト**: 99% (±1%)
  - **パッチ**: 90% (±2%)

## コード品質チェック

### Lint ワークフロー (`.github/workflows/lint.yml`)

コード品質チェックを実行:

1. **Ruff リンティング**
   ```bash
   uv run ruff --config dev/ruff.toml check ccbt/ --fix --exit-non-zero-on-fix
   ```

2. **Ruff フォーマット**
   ```bash
   uv run ruff --config dev/ruff.toml format --check ccbt/
   ```

3. **Ty 型チェック**
   ```bash
   uv run ty check --config-file=dev/ty.toml --output-format=concise
   ```

### セキュリティワークフロー (`.github/workflows/security.yml`)

セキュリティスキャンを実行:

1. **Bandit セキュリティスキャン**
   - 一般的なセキュリティ問題をスキャン
   - `docs/reports/bandit/bandit-report.json` に JSON レポートを生成
   - 中程度の重大度しきい値

## ドキュメントと翻訳検証

CI ワークフローには以下が含まれます:
- MkDocs ビルド検証: `uv run mkdocs build -f dev/mkdocs.yml`
- 翻訳検証: `uv run python -m ccbt.i18n.scripts.validate_po`

## カバレッジ要件

### Codecov 統合

カバレッジは Codecov で追跡され、以下の目標があります:

- **プロジェクトカバレッジ**: 99% (±1% 許容範囲)
- **パッチカバレッジ**: 90% (±2% 許容範囲)

