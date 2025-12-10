# btbt CLI - コマンドリファレンス

**btbt** は ccBitTorrent の拡張コマンドラインインターフェースで、トレント操作、監視、設定、高度な機能に対する包括的な制御を提供します。

- エントリーポイント: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- 定義場所: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- メインCLIグループ: [ccbt/cli/main.py:cli](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L243)

## 基本コマンド

### download

トレントファイルをダウンロードします。

実装: [ccbt/cli/main.py:download](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L369)

使用方法:
```bash
uv run btbt download <torrent_file> [options]
```

オプション:
- `--output <dir>`: 出力ディレクトリ
- `--interactive`: 対話モード
- `--monitor`: 監視モード
- `--resume`: チェックポイントから再開
- `--no-checkpoint`: チェックポイントを無効化
- `--checkpoint-dir <dir>`: チェックポイントディレクトリ
- `--files <indices...>`: ダウンロードする特定のファイルを選択（複数回指定可能、例: `--files 0 --files 1`）
- `--file-priority <spec>`: ファイルの優先度を `file_index=priority` として設定（例: `0=high,1=low`）。複数回指定可能。

ネットワークオプション（[ccbt/cli/main.py:_apply_network_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L67) を参照）:
- `--listen-port <int>`: リスンポート
- `--max-peers <int>`: グローバルピアの最大数
- `--max-peers-per-torrent <int>`: トレントあたりの最大ピア数
- `--pipeline-depth <int>`: リクエストパイプラインの深さ
- `--block-size-kib <int>`: ブロックサイズ（KiB）
- `--connection-timeout <float>`: 接続タイムアウト
- `--global-down-kib <int>`: グローバルダウンロード制限（KiB/s）
- `--global-up-kib <int>`: グローバルアップロード制限（KiB/s）

ディスクオプション（[ccbt/cli/main.py:_apply_disk_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L179) を参照）:
- `--hash-workers <int>`: ハッシュ検証ワーカーの数
- `--disk-workers <int>`: ディスクI/Oワーカーの数
- `--use-mmap`: メモリマッピングを有効化
- `--no-mmap`: メモリマッピングを無効化
- `--write-batch-kib <int>`: 書き込みバッチサイズ（KiB）
- `--write-buffer-kib <int>`: 書き込みバッファサイズ（KiB）
- `--preallocate <str>`: 事前割り当て戦略（none|sparse|full）

戦略オプション（[ccbt/cli/main.py:_apply_strategy_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L151) を参照）:
- `--piece-selection <str>`: ピース選択戦略（round_robin|rarest_first|sequential）
- `--endgame-duplicates <int>`: エンドゲーム重複リクエスト
- `--endgame-threshold <float>`: エンドゲーム閾値
- `--streaming`: ストリーミングモードを有効化

発見オプション（[ccbt/cli/main.py:_apply_discovery_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L123) を参照）:
- `--enable-dht`: DHTを有効化
- `--disable-dht`: DHTを無効化
- `--enable-pex`: PEXを有効化
- `--disable-pex`: PEXを無効化
- `--enable-http-trackers`: HTTPトラッカーを有効化
- `--disable-http-trackers`: HTTPトラッカーを無効化
- `--enable-udp-trackers`: UDPトラッカーを有効化
- `--disable-udp-trackers`: UDPトラッカーを無効化

可観測性オプション（[ccbt/cli/main.py:_apply_observability_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L217) を参照）:
- `--log-level <str>`: ログレベル（DEBUG|INFO|WARNING|ERROR|CRITICAL）
- `--log-file <path>`: ログファイルパス
- `--enable-metrics`: メトリクス収集を有効化
- `--disable-metrics`: メトリクス収集を無効化
- `--metrics-port <int>`: メトリクスポート

### magnet

マグネットリンクからダウンロードします。

実装: [ccbt/cli/main.py:magnet](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L608)

使用方法:
```bash
uv run btbt magnet <magnet_link> [options]
```

オプション: `download` コマンドと同じ。

### interactive

対話型CLIモードを開始します。

実装: [ccbt/cli/main.py:interactive](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L767)

使用方法:
```bash
uv run btbt interactive
```

対話型CLI: [ccbt/cli/interactive.py:InteractiveCLI](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/interactive.py#L41)

### status

現在のセッションの状態を表示します。

実装: [ccbt/cli/main.py:status](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L789)

使用方法:
```bash
uv run btbt status
```

## チェックポイントコマンド

チェックポイント管理グループ: [ccbt/cli/main.py:checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L849)

### checkpoints list

利用可能なすべてのチェックポイントを一覧表示します。

実装: [ccbt/cli/main.py:list_checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L863)

使用方法:
```bash
uv run btbt checkpoints list [--format json|table]
```

### checkpoints clean

古いチェックポイントをクリーンアップします。

実装: [ccbt/cli/main.py:clean_checkpoints](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L930)

使用方法:
```bash
uv run btbt checkpoints clean [--days <n>] [--dry-run]
```

### checkpoints delete

特定のチェックポイントを削除します。

実装: [ccbt/cli/main.py:delete_checkpoint](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L978)

使用方法:
```bash
uv run btbt checkpoints delete <info_hash>
```

### checkpoints verify

チェックポイントを検証します。

実装: [ccbt/cli/main.py:verify_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1016)

使用方法:
```bash
uv run btbt checkpoints verify <info_hash>
```

### checkpoints export

チェックポイントをファイルにエクスポートします。

実装: [ccbt/cli/main.py:export_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1058)

使用方法:
```bash
uv run btbt checkpoints export <info_hash> [--format json|binary] [--output <path>]
```

### checkpoints backup

チェックポイントを場所にバックアップします。

実装: [ccbt/cli/main.py:backup_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1099)

使用方法:
```bash
uv run btbt checkpoints backup <info_hash> <destination> [--compress] [--encrypt]
```

### checkpoints restore

バックアップからチェックポイントを復元します。

実装: [ccbt/cli/main.py:restore_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1138)

使用方法:
```bash
uv run btbt checkpoints restore <backup_file> [--info-hash <hash>]
```

### checkpoints migrate

チェックポイントをフォーマット間で移行します。

実装: [ccbt/cli/main.py:migrate_checkpoint_cmd](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1173)

使用方法:
```bash
uv run btbt checkpoints migrate <info_hash> --from <format> --to <format>
```

### resume

チェックポイントからダウンロードを再開します。

実装: [ccbt/cli/main.py:resume](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1204)

使用方法:
```bash
uv run btbt resume <info_hash> [--output <dir>] [--interactive]
```

## 監視コマンド

監視コマンドグループ: [ccbt/cli/monitoring_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py)

### dashboard

ターミナル監視ダッシュボード（Bitonic）を開始します。

実装: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L20)

使用方法:
```bash
uv run btbt dashboard [--refresh <seconds>] [--rules <path>]
```

詳細な使用方法については [Bitonicガイド](bitonic.md) を参照してください。

### alerts

アラートルールとアクティブなアラートを管理します。

実装: [ccbt/cli/monitoring_commands.py:alerts](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L48)

使用方法:
```bash
# アラートルールを一覧表示
uv run btbt alerts --list

# アクティブなアラートを一覧表示
uv run btbt alerts --list-active

# アラートルールを追加
uv run btbt alerts --add --name <name> --metric <metric> --condition "<condition>" --severity <severity>

# アラートルールを削除
uv run btbt alerts --remove --name <name>

# すべてのアクティブなアラートをクリア
uv run btbt alerts --clear-active

# アラートルールをテスト
uv run btbt alerts --test --name <name> --value <value>

# ファイルからルールを読み込む
uv run btbt alerts --load <path>

# ルールをファイルに保存
uv run btbt alerts --save <path>
```

詳細情報については [APIリファレンス](API.md#monitoring) を参照してください。

### metrics

メトリクスを収集してエクスポートします。

実装: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L229)

使用方法:
```bash
uv run btbt metrics [--format json|prometheus] [--output <path>] [--duration <seconds>] [--interval <seconds>] [--include-system] [--include-performance]
```

例:
```bash
# JSONメトリクスをエクスポート
uv run btbt metrics --format json --include-system --include-performance

# Prometheus形式でエクスポート
uv run btbt metrics --format prometheus > metrics.txt
```

詳細情報については [APIリファレンス](API.md#monitoring) を参照してください。

## ファイル選択コマンド

ファイル選択コマンドグループ: [ccbt/cli/file_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py)

マルチファイルトレントのファイル選択と優先度を管理します。

### files list

トレント内のすべてのファイルを、選択状態、優先度、ダウンロード進捗とともに一覧表示します。

実装: [ccbt/cli/file_commands.py:files_list](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L28)

使用方法:
```bash
uv run btbt files list <info_hash>
```

出力には以下が含まれます:
- ファイルインデックスと名前
- ファイルサイズ
- 選択状態（選択済み/未選択）
- 優先度レベル
- ダウンロード進捗

### files select

ダウンロードする1つ以上のファイルを選択します。

実装: [ccbt/cli/file_commands.py:files_select](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L72)

使用方法:
```bash
uv run btbt files select <info_hash> <file_index> [<file_index> ...]
```

例:
```bash
# ファイル0、2、5を選択
uv run btbt files select abc123... 0 2 5

# 単一ファイルを選択
uv run btbt files select abc123... 0
```

### files deselect

ダウンロードから1つ以上のファイルを選択解除します。

実装: [ccbt/cli/file_commands.py:files_deselect](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L108)

使用方法:
```bash
uv run btbt files deselect <info_hash> <file_index> [<file_index> ...]
```

### files select-all

トレント内のすべてのファイルを選択します。

実装: [ccbt/cli/file_commands.py:files_select_all](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L144)

使用方法:
```bash
uv run btbt files select-all <info_hash>
```

### files deselect-all

トレント内のすべてのファイルを選択解除します。

実装: [ccbt/cli/file_commands.py:files_deselect_all](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L161)

使用方法:
```bash
uv run btbt files deselect-all <info_hash>
```

### files priority

特定のファイルの優先度を設定します。

実装: [ccbt/cli/file_commands.py:files_priority](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/file_commands.py#L178)

使用方法:
```bash
uv run btbt files priority <info_hash> <file_index> <priority>
```

優先度レベル:
- `do_not_download`: ダウンロードしない（未選択と同等）
- `low`: 低優先度
- `normal`: 通常優先度（デフォルト）
- `high`: 高優先度
- `maximum`: 最大優先度

例:
```bash
# ファイル0を高優先度に設定
uv run btbt files priority abc123... 0 high

# ファイル2を最大優先度に設定
uv run btbt files priority abc123... 2 maximum
```

## 設定コマンド

設定コマンドグループ: [ccbt/cli/config_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/config_commands.py)

### config

設定を管理します。

実装: [ccbt/cli/main.py:config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L810)

使用方法:
```bash
uv run btbt config [subcommand]
```

拡張設定コマンド: [ccbt/cli/config_commands_extended.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/config_commands_extended.py)

詳細な設定オプションについては [設定ガイド](configuration.md) を参照してください。

## 高度なコマンド

高度なコマンドグループ: [ccbt/cli/advanced_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py)

### performance

パフォーマンス分析とベンチマーク。

実装: [ccbt/cli/advanced_commands.py:performance](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L73)

使用方法:
```bash
uv run btbt performance [--analyze] [--benchmark]
```

### security

セキュリティ分析と検証。

実装: [ccbt/cli/advanced_commands.py:security](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L170)

使用方法:
```bash
uv run btbt security [options]
```

### recover

回復操作。

実装: [ccbt/cli/advanced_commands.py:recover](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L209)

使用方法:
```bash
uv run btbt recover [options]
```

### test

テストと診断を実行します。

実装: [ccbt/cli/advanced_commands.py:test](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/advanced_commands.py#L248)

使用方法:
```bash
uv run btbt test [options]
```

## コマンドラインオプション

### グローバルオプション

グローバルオプションの定義: [ccbt/cli/main.py:cli](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L243)

- `--config <path>`: 設定ファイルパス
- `--verbose`: 詳細出力
- `--debug`: デバッグモード

### CLIオーバーライド

すべてのCLIオプションは次の順序で設定をオーバーライドします:
1. [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py) のデフォルト
2. 設定ファイル（[ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)）
3. 環境変数（[env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)）
4. CLI引数

オーバーライド実装: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)

## 例

### 基本的なダウンロード
```bash
uv run btbt download movie.torrent
```

### オプション付きダウンロード
```bash
uv run btbt download movie.torrent \
  --listen-port 7001 \
  --enable-dht \
  --use-mmap \
  --download-limit 1024 \
  --upload-limit 512
```

### 選択的ファイルダウンロード
```bash
# 特定のファイルのみをダウンロード
uv run btbt download torrent.torrent --files 0 --files 2 --files 5

# ファイル優先度を設定してダウンロード
uv run btbt download torrent.torrent \
  --file-priority 0=high \
  --file-priority 1=maximum \
  --file-priority 2=low

# 組み合わせ: ファイルを選択して優先度を設定
uv run btbt download torrent.torrent \
  --files 0 1 2 \
  --file-priority 0=maximum \
  --file-priority 1=high
```

### マグネットリンクからダウンロード
```bash
uv run btbt magnet "magnet:?xt=urn:btih:..." \
  --download-limit 1024 \
  --upload-limit 256
```

### ファイル選択管理
```bash
# トレント内のファイルを一覧表示
uv run btbt files list abc123def456789...

# ダウンロード開始後に特定のファイルを選択
uv run btbt files select abc123... 3 4

# ファイル優先度を設定
uv run btbt files priority abc123... 0 high
uv run btbt files priority abc123... 2 maximum

# すべてのファイルを選択/選択解除
uv run btbt files select-all abc123...
uv run btbt files deselect-all abc123...
```

### チェックポイント管理
```bash
# チェックポイントを一覧表示
uv run btbt checkpoints list --format json

# チェックポイントをエクスポート
uv run btbt checkpoints export <infohash> --format json --output checkpoint.json

# 古いチェックポイントをクリーンアップ
uv run btbt checkpoints clean --days 7
```

### トレントごとの設定

トレントごとの設定オプションとレート制限を管理します。これらの設定はチェックポイントとデーモン状態に永続化されます。

実装: [ccbt/cli/torrent_config_commands.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/torrent_config_commands.py)

#### トレントごとのオプションを設定

特定のトレントの設定オプションを設定します:

```bash
uv run btbt torrent config set <info_hash> <key> <value> [--save-checkpoint]
```

例:
```bash
# ピース選択戦略を設定
uv run btbt torrent config set abc123... piece_selection sequential

# ストリーミングモードを有効化
uv run btbt torrent config set abc123... streaming_mode true

# トレントあたりの最大ピア数を設定
uv run btbt torrent config set abc123... max_peers_per_torrent 50

# オプションを設定してチェックポイントを即座に保存
uv run btbt torrent config set abc123... piece_selection rarest_first --save-checkpoint
```

#### トレントごとのオプションを取得

特定のトレントの設定オプション値を取得します:

```bash
uv run btbt torrent config get <info_hash> <key>
```

例:
```bash
uv run btbt torrent config get abc123... piece_selection
```

#### すべてのトレントごとの設定を一覧表示

トレントのすべての設定オプションとレート制限を一覧表示します:

```bash
uv run btbt torrent config list <info_hash>
```

例:
```bash
uv run btbt torrent config list abc123...
```

出力には以下が表示されます:
- すべてのトレントごとのオプション（piece_selection、streaming_modeなど）
- レート制限（ダウンロード/アップロード、KiB/s）

#### トレントごとの設定をリセット

トレントの設定オプションをリセットします:

```bash
uv run btbt torrent config reset <info_hash> [--key <key>]
```

例:
```bash
# すべてのトレントごとのオプションをリセット
uv run btbt torrent config reset abc123...

# 特定のオプションをリセット
uv run btbt torrent config reset abc123... --key piece_selection
```

**注意**: トレントごとの設定オプションは、チェックポイントが作成されると自動的にチェックポイントに保存されます。`set` で `--save-checkpoint` を使用すると、変更を即座に永続化できます。これらの設定は、デーモンモードで実行している場合、デーモン状態にも永続化されます。

### 監視
```bash
# ダッシュボードを開始
uv run btbt dashboard --refresh 2.0

# アラートルールを追加
uv run btbt alerts --add --name cpu_high --metric system.cpu --condition "value > 80" --severity warning

# メトリクスをエクスポート
uv run btbt metrics --format json --include-system --include-performance
```

## ヘルプの取得

任意のコマンドのヘルプを取得:
```bash
uv run btbt --help
uv run btbt <command> --help
```

詳細情報:
- [Bitonicガイド](bitonic.md) - ターミナルダッシュボード
- [設定ガイド](configuration.md) - 設定オプション
- [APIリファレンス](API.md#monitoring) - 監視とメトリクス
- [パフォーマンスチューニング](performance.md) - 最適化ガイド
