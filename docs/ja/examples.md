# 例

このセクションでは、ccBitTorrentを使用するための実用的な例とコードサンプルを提供します。

## 設定例

### 基本設定

開始するための最小限の設定ファイル：

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

完全な基本設定については[example-config-basic.toml](examples/example-config-basic.toml)を参照してください。

### 高度な設定

詳細な制御が必要な上級ユーザー向け：

高度な設定オプションについては[example-config-advanced.toml](examples/example-config-advanced.toml)を参照してください。

### パフォーマンス設定

最大パフォーマンスのための最適化された設定：

パフォーマンスチューニングについては[example-config-performance.toml](examples/example-config-performance.toml)を参照してください。

### セキュリティ設定

暗号化と検証を備えたセキュリティ重視の設定：

セキュリティ設定については[example-config-security.toml](examples/example-config-security.toml)を参照してください。

## BEP 52の例

### v2トレントの作成

BitTorrent v2トレントファイルを作成：

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# v2トレントを作成
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # 16KBピース
)
```

完全な例については[create_v2_torrent.py](examples/bep52/create_v2_torrent.py)を参照してください。

### ハイブリッドトレントの作成

v1とv2の両方のクライアントで動作するハイブリッドトレントを作成：

完全な例については[create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py)を参照してください。

### v2トレントの解析

BitTorrent v2トレントファイルを解析して検査：

完全な例については[parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py)を参照してください。

### プロトコルv2セッション

セッションでBitTorrent v2プロトコルを使用：

完全な例については[protocol_v2_session.py](examples/bep52/protocol_v2_session.py)を参照してください。

## はじめに

ccBitTorrentの開始に関する詳細については、[はじめにガイド](getting-started.md)を参照してください。






このセクションでは、ccBitTorrentを使用するための実用的な例とコードサンプルを提供します。

## 設定例

### 基本設定

開始するための最小限の設定ファイル：

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

完全な基本設定については[example-config-basic.toml](examples/example-config-basic.toml)を参照してください。

### 高度な設定

詳細な制御が必要な上級ユーザー向け：

高度な設定オプションについては[example-config-advanced.toml](examples/example-config-advanced.toml)を参照してください。

### パフォーマンス設定

最大パフォーマンスのための最適化された設定：

パフォーマンスチューニングについては[example-config-performance.toml](examples/example-config-performance.toml)を参照してください。

### セキュリティ設定

暗号化と検証を備えたセキュリティ重視の設定：

セキュリティ設定については[example-config-security.toml](examples/example-config-security.toml)を参照してください。

## BEP 52の例

### v2トレントの作成

BitTorrent v2トレントファイルを作成：

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# v2トレントを作成
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # 16KBピース
)
```

完全な例については[create_v2_torrent.py](examples/bep52/create_v2_torrent.py)を参照してください。

### ハイブリッドトレントの作成

v1とv2の両方のクライアントで動作するハイブリッドトレントを作成：

完全な例については[create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py)を参照してください。

### v2トレントの解析

BitTorrent v2トレントファイルを解析して検査：

完全な例については[parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py)を参照してください。

### プロトコルv2セッション

セッションでBitTorrent v2プロトコルを使用：

完全な例については[protocol_v2_session.py](examples/bep52/protocol_v2_session.py)を参照してください。

## はじめに

ccBitTorrentの開始に関する詳細については、[はじめにガイド](getting-started.md)を参照してください。
































































































































































































