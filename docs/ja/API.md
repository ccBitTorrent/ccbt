# ccBT API リファレンス

ccBitTorrent の包括的な API ドキュメント。実際の実装ファイルへの参照を含みます。

!!! note "翻訳状況"
    このドキュメントは英語版から完全に翻訳する必要があります。最新の内容については [docs/en/API.md](../en/API.md) を参照してください。

## エントリーポイント

### メインエントリーポイント (ccbt)

基本的な torrent 操作用のメインコマンドラインエントリーポイント。

実装: [ccbt/__main__.py:main](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L18)

機能:
- 単一 torrent ダウンロードモード
- マルチ torrent セッション用のデーモンモード: [ccbt/__main__.py:52](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L52)
- Magnet URI サポート: [ccbt/__main__.py:73](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L73)
- Tracker アナウンス: [ccbt/__main__.py:89](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L89)

エントリーポイント設定: [pyproject.toml:79](https://github.com/ccBitTorrent/ccbt/blob/main/pyproject.toml#L79)

### 非同期ダウンロードヘルパー

高度な操作のための高性能非同期ヘルパーとダウンロードマネージャー。

実装: [ccbt/session/download_manager.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/download_manager.py)

主要エクスポート:
- `AsyncDownloadManager`
- `download_torrent()`
- `download_magnet()`

### AsyncDownloadManager

個別の torrent 用の高性能非同期ダウンロードマネージャー。

実装: [ccbt/session/download_manager.py:AsyncDownloadManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/download_manager.py)

メソッド:
- `__init__()`: [ccbt/session/async_main.py:41](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L41) - torrent データで初期化
- `start()`: [ccbt/session/async_main.py:110](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L110) - ダウンロードマネージャーを開始
- `stop()`: [ccbt/session/async_main.py:115](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L115) - ダウンロードマネージャーを停止
- `start_download()`: [ccbt/session/async_main.py:122](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L122) - ピアとダウンロードを開始

機能:
- AsyncPeerConnectionManager によるピア接続管理: [ccbt/session/async_main.py:127](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L127)
- AsyncPieceManager によるピース管理: [ccbt/session/async_main.py:94](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L94)
- イベント用コールバックシステム: [ccbt/session/async_main.py:103](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/async_main.py#L103)

## コアモジュール

### Torrent 解析とメタデータ

#### TorrentParser

BitTorrent torrent ファイルを解析し、メタデータを抽出します。

::: ccbt.core.torrent.TorrentParser
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**主要メソッド:**

- `parse()`: [ccbt/core/torrent.py:34](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/torrent.py#L34) - パスまたは URL から torrent ファイルを解析
- `_validate_torrent()`: [ccbt/core/torrent.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/torrent.py) - torrent 構造を検証
- `_extract_torrent_data()`: [ccbt/core/torrent.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/torrent.py) - torrent データを抽出して処理

#### Bencode エンコード/デコード

BitTorrent プロトコル (BEP 3) 用の Bencode コーデック。

**クラス:**

- `BencodeDecoder`: [ccbt/core/bencode.py:BencodeDecoder](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L24) - bencode データのデコーダー
- `BencodeEncoder`: [ccbt/core/bencode.py:BencodeEncoder](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L156) - Python オブジェクトを bencode にエンコードするエンコーダー

**関数:**
- `decode()`: [ccbt/core/bencode.py:decode](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L221) - bencode バイトを Python オブジェクトにデコード
- `encode()`: [ccbt/core/bencode.py:encode](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L227) - Python オブジェクトを bencode 形式にエンコード

**サポートされる型:**
- 整数: `i<数値>e`
- 文字列: `<長さ>:<データ>`
- リスト: `l<項目>e`
- 辞書: `d<キー値ペア>e`

**例外:**
- `BencodeDecodeError`: [ccbt/core/bencode.py:BencodeDecodeError](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L16) - デコードエラー
- `BencodeEncodeError`: [ccbt/core/bencode.py:BencodeEncodeError](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/core/bencode.py#L20) - エンコードエラー

## セッション管理

### AsyncSessionManager

複数の torrent 用の高性能非同期セッションマネージャー。

::: ccbt.session.session.AsyncSessionManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

### AsyncTorrentSession

非同期操作を持つ単一のアクティブな torrent のライフサイクルを表す個別の torrent セッション。

::: ccbt.session.session.AsyncTorrentSession
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**主要メソッド:**

- `start()`: [ccbt/session/session.py:start](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L400) - torrent セッションを開始し、ダウンロードマネージャー、トラッカー、PEX を初期化
- `stop()`: [ccbt/session/session.py:stop](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L678) - torrent セッションを停止し、チェックポイントを保存し、リソースをクリーンアップ
- `pause()`: [ccbt/session/session.py:pause](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - ダウンロードを一時停止
- `resume()`: [ccbt/session/session.py:resume](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - ダウンロードを再開
- `get_status()`: [ccbt/session/session.py:get_status](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - torrent ステータスを取得

## 設定

### ConfigManager

ホットリロード、階層的読み込み、検証を備えた設定管理。

::: ccbt.config.config.ConfigManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**機能:**
- 設定読み込み: [ccbt/config/config.py:_load_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L76)
- ファイル検出: [ccbt/config/config.py:_find_config_file](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L55)
- 環境変数解析: [ccbt/config/config.py:_get_env_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py)
- ホットリロードサポート: [ccbt/config/config.py:ConfigManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L40)
- CLI オーバーライド: [ccbt/cli/overrides.py:apply_cli_overrides](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/overrides.py)

**設定の優先順位:**
1. `ccbt/models.py:Config` からのデフォルト値
2. 設定ファイル（現在のディレクトリの `ccbt.toml` または `~/.config/ccbt/ccbt.toml`）
3. 環境変数（`CCBT_*` プレフィックス）
4. CLI 引数（`apply_cli_overrides()` 経由）
5. 各 torrent のデフォルト値
6. 各 torrent のオーバーライド

## 追加リソース

- [入門ガイド](getting-started.md) - クイックスタートガイド
- [設定ガイド](configuration.md) - 詳細な設定
- [パフォーマンスチューニング](performance.md) - パフォーマンス最適化
- [Bitonic ガイド](bitonic.md) - ターミナルダッシュボード
- [btbt CLI リファレンス](btbt-cli.md) - CLI ドキュメント

