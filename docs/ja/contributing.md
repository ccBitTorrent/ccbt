# ccBitTorrent への貢献

ccBitTorrent への貢献にご興味をお持ちいただき、ありがとうございます！このドキュメントでは、開発プロセス、コード標準、貢献ワークフローについて説明します。

!!! note "翻訳状況"
    このドキュメントは英語版から完全に翻訳する必要があります。最新の内容については [docs/en/contributing.md](../en/contributing.md) を参照してください。

## プロジェクト概要

ccBitTorrent は Python で実装された高性能 BitTorrent クライアントです。これは **GPL** ライセンスの下でリリースされる**参照 Python 実装**です。このプロジェクトは、完全で、十分にテストされ、高性能な BitTorrent クライアントを提供することを目的としています。

## 開発設定

### 前提条件

- Python 3.8 以上
- [UV](https://github.com/astral-sh/uv) パッケージマネージャー（推奨）
- Git

### 初期設定

1. リポジトリをクローン:
```bash
git clone https://github.com/ccBittorrent/ccbt.git
cd ccbt
```

2. UV を使用して依存関係をインストール:
```bash
uv sync --dev
```

3. pre-commit フックをインストール:
```bash
uv run pre-commit install --config dev/pre-commit-config.yaml
```

## コード品質基準

### リンティング

高速リンティングとフォーマットには [Ruff](https://github.com/astral-sh/ruff) を使用します。設定は [dev/ruff.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ruff.toml) にあります。

リンティングを実行:
```bash
uv run ruff --config dev/ruff.toml check ccbt/ --fix --exit-non-zero-on-fix
```

コードをフォーマット:
```bash
uv run ruff --config dev/ruff.toml format ccbt/
```

### 型チェック

高速型チェックには [Ty](https://github.com/astral-sh/ty) を使用します。設定は [dev/ty.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ty.toml) にあります。

型チェックを実行:
```bash
uv run ty check --config-file=dev/ty.toml --output-format=concise
```

### テスト

テストには [pytest](https://pytest.org/) を使用します。設定は [dev/pytest.ini](https://github.com/ccBittorrent/ccbt/blob/main/dev/pytest.ini) にあります。

すべてのテストを実行:
```bash
uv run pytest -c dev/pytest.ini tests/ -v
```

カバレッジ付きで実行:
```bash
uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-report=html --cov-report=xml
```

### Pre-commit フック

すべての品質チェックは [dev/pre-commit-config.yaml](https://github.com/ccBittorrent/ccbt/blob/main/dev/pre-commit-config.yaml) で設定された pre-commit フックを介して自動的に実行されます。これには以下が含まれます:

- Ruff リンティングとフォーマット
- Ty 型チェック
- Bandit セキュリティスキャン
- カバレッジ付き Pytest
- ベンチマークスモークテスト
- MkDocs ビルド検証: `uv run mkdocs build -f dev/mkdocs.yml`
- 翻訳検証: `uv run python -m ccbt.i18n.scripts.validate_po`
- 翻訳カバレッジチェック: `uv run python -m ccbt.i18n.scripts.check_string_coverage --source-dir ccbt`

手動で実行:
```bash
uv run pre-commit run --all-files -c dev/pre-commit-config.yaml
```

!!! note "翻訳検証"
    翻訳可能な文字列に影響する変更をコミットする前に:
    1. `.pot` テンプレートを再生成: `uv run python -m ccbt.i18n.scripts.extract`
    2. PO ファイルを検証: `uv run python -m ccbt.i18n.scripts.validate_po`
    3. 翻訳カバレッジをチェック: `uv run python -m ccbt.i18n.scripts.check_string_coverage --source-dir ccbt`

## 開発設定

すべての開発設定ファイルは [dev/](dev/) にあります:

- [dev/pre-commit-config.yaml](https://github.com/ccBittorrent/ccbt/blob/main/dev/pre-commit-config.yaml) - Pre-commit フック設定
- [dev/ruff.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ruff.toml) - Ruff リンティングとフォーマット
- [dev/ty.toml](https://github.com/ccBittorrent/ccbt/blob/main/dev/ty.toml) - 型チェック設定
- [dev/pytest.ini](https://github.com/ccBittorrent/ccbt/blob/main/dev/pytest.ini) - テスト設定
- [dev/mkdocs.yml](https://github.com/ccBittorrent/ccbt/blob/main/dev/mkdocs.yml) - ドキュメント設定

## ブランチ戦略

### Main ブランチ

- `main` ブランチはリリースに使用されます
- `dev` ブランチからのマージのみを受け入れます
- main へのプッシュ時に自動的にリリースをビルドします

### Dev ブランチ

- `dev` ブランチは主要な開発ブランチです
- **main にマージされる唯一のブランチ**
- main と同様にすべてのチェックを実行します:
  - すべてのリンティングと型チェック
  - カバレッジ付きの完全なテストスイート
  - [dev/pre-commit-config.yaml:39-68](https://github.com/ccBittorrent/ccbt/blob/main/dev/pre-commit-config.yaml#L39-L68) からのすべてのベンチマークチェック
  - ドキュメントビルド

## 貢献プロセス

### 変更を行う

1. **Fork またはブランチを作成**: 適切な issue からブランチを作成
2. **変更を行う**: コード品質基準に従う
3. **ローカルでテスト**: プッシュ前にすべてのチェックを実行:
   ```bash
   uv run pre-commit run --all-files -c dev/pre-commit-config.yaml
   ```
4. **コミット**: 従来のコミットメッセージを使用
5. **プッシュ**: ブランチにプッシュ
6. **PR を作成**: `dev` ブランチにプルリクエストを送信

## ライセンス

このプロジェクトは **GPL**（GNU 一般公衆利用許諾）の下でライセンスされています。貢献することで、あなたの貢献が同じライセンスの下でライセンスされることに同意したことになります。

