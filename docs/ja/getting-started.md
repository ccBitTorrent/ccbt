# はじめに

ccBitTorrentへようこそ！このガイドは、高性能BitTorrentクライアントを迅速に起動して実行するのに役立ちます。

!!! tip "主要機能：BEP XETプロトコル拡張"
    ccBitTorrentには**Xetプロトコル拡張（BEP XET）**が含まれており、コンテンツ定義チャンキングとクロストレント重複排除を可能にします。これにより、BitTorrentは協力に最適化された超高速で更新可能なピアツーピアファイルシステムに変換されます。[BEP XETについて詳しく →](bep_xet.md)

## インストール

### 前提条件

- Python 3.8以上
- [UV](https://astral.sh/uv)パッケージマネージャー（推奨）

### UVのインストール

公式インストールスクリプトからUVをインストール：
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ccBitTorrentのインストール

PyPIからインストール：
```bash
uv pip install ccbittorrent
```

またはソースからインストール：
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

エントリーポイントは[pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81)で定義されています。

## 主要エントリーポイント

ccBitTorrentは3つの主要なエントリーポイントを提供します：

### 1. Bitonic（推奨）

**Bitonic**はメインターミナルダッシュボードインターフェースです。すべてのトレント、ピア、システムメトリクスのライブでインタラクティブなビューを提供します。

- エントリーポイント: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- 定義場所: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- 起動: `uv run bitonic` または `uv run ccbt dashboard`

詳細な使用方法については[Bitonicガイド](bitonic.md)を参照してください。

### 2. btbt CLI

**btbt**は豊富な機能を備えた拡張コマンドラインインターフェースです。

- エントリーポイント: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- 定義場所: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- 起動: `uv run btbt`

利用可能なすべてのコマンドについては[btbt CLIリファレンス](btbt-cli.md)を参照してください。

### 3. ccbt（基本CLI）

**ccbt**は基本的なコマンドラインインターフェースです。

- エントリーポイント: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- 定義場所: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- 起動: `uv run ccbt`

## クイックスタート

### Bitonicを起動（推奨）

ターミナルダッシュボードを開始：
```bash
uv run bitonic
```

またはCLI経由：
```bash
uv run ccbt dashboard
```

カスタムリフレッシュレートで：
```bash
uv run ccbt dashboard --refresh 2.0
```

### トレントをダウンロード

CLIを使用：
```bash
# トレントファイルからダウンロード
uv run btbt download movie.torrent

# マグネットリンクからダウンロード
uv run btbt magnet "magnet:?xt=urn:btih:..."

# レート制限付き
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

すべてのダウンロードオプションについては[btbt CLIリファレンス](btbt-cli.md)を参照してください。

### ccBitTorrentを設定

作業ディレクトリに`ccbt.toml`ファイルを作成します。サンプル設定を参照：
- デフォルト設定: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- 環境変数: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- 設定システム: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

詳細な設定オプションについては[設定ガイド](configuration.md)を参照してください。

## プロジェクトレポート

プロジェクトの品質メトリクスとレポートを表示：

- **コードカバレッジ**: [reports/coverage.md](reports/coverage.md) - 包括的なコードカバレッジ分析
- **セキュリティレポート**: [reports/bandit/index.md](reports/bandit/index.md) - Banditによるセキュリティスキャン結果
- **ベンチマーク**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - パフォーマンスベンチマーク結果

これらのレポートは、継続的インテグレーションプロセスの一部として自動的に生成および更新されます。

## 次のステップ

- [Bitonic](bitonic.md) - ターミナルダッシュボードインターフェースについて学ぶ
- [btbt CLI](btbt-cli.md) - 完全なコマンドラインインターフェースリファレンス
- [設定](configuration.md) - 詳細な設定オプション
- [パフォーマンスチューニング](performance.md) - 最適化ガイド
- [APIリファレンス](API.md) - 監視機能を含むPython APIドキュメント

## ヘルプの取得

- コマンドヘルプには`uv run bitonic --help`または`uv run btbt --help`を使用
- 詳細なオプションについては[btbt CLIリファレンス](btbt-cli.md)を確認
- 問題やディスカッションについては[GitHubリポジトリ](https://github.com/yourusername/ccbittorrent)にアクセス






ccBitTorrentへようこそ！このガイドは、高性能BitTorrentクライアントを迅速に起動して実行するのに役立ちます。

!!! tip "主要機能：BEP XETプロトコル拡張"
    ccBitTorrentには**Xetプロトコル拡張（BEP XET）**が含まれており、コンテンツ定義チャンキングとクロストレント重複排除を可能にします。これにより、BitTorrentは協力に最適化された超高速で更新可能なピアツーピアファイルシステムに変換されます。[BEP XETについて詳しく →](bep_xet.md)

## インストール

### 前提条件

- Python 3.8以上
- [UV](https://astral.sh/uv)パッケージマネージャー（推奨）

### UVのインストール

公式インストールスクリプトからUVをインストール：
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ccBitTorrentのインストール

PyPIからインストール：
```bash
uv pip install ccbittorrent
```

またはソースからインストール：
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

エントリーポイントは[pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81)で定義されています。

## 主要エントリーポイント

ccBitTorrentは3つの主要なエントリーポイントを提供します：

### 1. Bitonic（推奨）

**Bitonic**はメインターミナルダッシュボードインターフェースです。すべてのトレント、ピア、システムメトリクスのライブでインタラクティブなビューを提供します。

- エントリーポイント: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- 定義場所: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- 起動: `uv run bitonic` または `uv run ccbt dashboard`

詳細な使用方法については[Bitonicガイド](bitonic.md)を参照してください。

### 2. btbt CLI

**btbt**は豊富な機能を備えた拡張コマンドラインインターフェースです。

- エントリーポイント: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- 定義場所: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- 起動: `uv run btbt`

利用可能なすべてのコマンドについては[btbt CLIリファレンス](btbt-cli.md)を参照してください。

### 3. ccbt（基本CLI）

**ccbt**は基本的なコマンドラインインターフェースです。

- エントリーポイント: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- 定義場所: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- 起動: `uv run ccbt`

## クイックスタート

### Bitonicを起動（推奨）

ターミナルダッシュボードを開始：
```bash
uv run bitonic
```

またはCLI経由：
```bash
uv run ccbt dashboard
```

カスタムリフレッシュレートで：
```bash
uv run ccbt dashboard --refresh 2.0
```

### トレントをダウンロード

CLIを使用：
```bash
# トレントファイルからダウンロード
uv run btbt download movie.torrent

# マグネットリンクからダウンロード
uv run btbt magnet "magnet:?xt=urn:btih:..."

# レート制限付き
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

すべてのダウンロードオプションについては[btbt CLIリファレンス](btbt-cli.md)を参照してください。

### ccBitTorrentを設定

作業ディレクトリに`ccbt.toml`ファイルを作成します。サンプル設定を参照：
- デフォルト設定: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- 環境変数: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- 設定システム: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

詳細な設定オプションについては[設定ガイド](configuration.md)を参照してください。

## プロジェクトレポート

プロジェクトの品質メトリクスとレポートを表示：

- **コードカバレッジ**: [reports/coverage.md](reports/coverage.md) - 包括的なコードカバレッジ分析
- **セキュリティレポート**: [reports/bandit/index.md](reports/bandit/index.md) - Banditによるセキュリティスキャン結果
- **ベンチマーク**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - パフォーマンスベンチマーク結果

これらのレポートは、継続的インテグレーションプロセスの一部として自動的に生成および更新されます。

## 次のステップ

- [Bitonic](bitonic.md) - ターミナルダッシュボードインターフェースについて学ぶ
- [btbt CLI](btbt-cli.md) - 完全なコマンドラインインターフェースリファレンス
- [設定](configuration.md) - 詳細な設定オプション
- [パフォーマンスチューニング](performance.md) - 最適化ガイド
- [APIリファレンス](API.md) - 監視機能を含むPython APIドキュメント

## ヘルプの取得

- コマンドヘルプには`uv run bitonic --help`または`uv run btbt --help`を使用
- 詳細なオプションについては[btbt CLIリファレンス](btbt-cli.md)を確認
- 問題やディスカッションについては[GitHubリポジトリ](https://github.com/yourusername/ccbittorrent)にアクセス
































































































































































































