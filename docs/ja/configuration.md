# 設定ガイド

ccBitTorrentは、TOMLサポート、検証、ホットリロード、複数ソースからの階層的読み込みを備えた包括的な設定システムを使用します。

設定システム: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## 設定ソースと優先順位

設定は次の順序で読み込まれます（後のソースが前のソースを上書きします）：

1. **デフォルト**: [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)からの組み込みの適切なデフォルト値
2. **設定ファイル**: 現在のディレクトリまたは`~/.config/ccbt/ccbt.toml`の`ccbt.toml`。参照: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **環境変数**: `CCBT_*`プレフィックス付き変数。参照: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI引数**: コマンドラインオーバーライド。参照: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **トレントごと**: 個別のトレント設定（将来の機能）

設定の読み込み: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## 設定ファイル

### デフォルト設定

デフォルト設定ファイルを参照: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

設定はセクションごとに整理されています：

### ネットワーク設定

ネットワーク設定: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- 接続制限: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- リクエストパイプライン: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- ソケットチューニング: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- タイムアウト: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- リスン設定: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- トランスポートプロトコル: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- レート制限: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- チョーキング戦略: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- トラッカー設定: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

ネットワーク設定モデル: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ディスク設定

ディスク設定: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- 事前割り当て: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- 書き込み最適化: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- ハッシュ検証: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/Oスレッディング: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- 高度な設定: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- ストレージサービス設定: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: ストレージサービスの最大ファイルサイズ制限（MB単位）（0またはNone = 無制限、最大1048576 = 1TB）。テスト中の無制限ディスク書き込みを防ぎ、本番使用のために設定できます。
- チェックポイント設定: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

ディスク設定モデル: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 戦略設定

戦略設定: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- ピース選択: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- 高度な戦略: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- ピース優先度: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

戦略設定モデル: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 発見設定

発見設定: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT設定: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX設定: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- トラッカー設定: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: トラッカーアナウンス間隔（秒単位）（デフォルト: 1800.0、範囲: 60.0-86400.0）
  - `tracker_scrape_interval`: 定期的なスクレイピングのためのトラッカースクレイプ間隔（秒単位）（デフォルト: 3600.0、範囲: 60.0-86400.0）
  - `tracker_auto_scrape`: トレントが追加されたときにトラッカーを自動的にスクレイプ（BEP 48）（デフォルト: false）
  - 環境変数: `CCBT_TRACKER_ANNOUNCE_INTERVAL`、`CCBT_TRACKER_SCRAPE_INTERVAL`、`CCBT_TRACKER_AUTO_SCRAPE`

発見設定モデル: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 制限設定

レート制限: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- グローバル制限: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- トレントごとの制限: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- ピアごとの制限: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- スケジューラー設定: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

制限設定モデル: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 可観測性設定

可観測性設定: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- ロギング: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- メトリクス: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- トレーシングとアラート: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

可観測性設定モデル: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### セキュリティ設定

セキュリティ設定: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

セキュリティ設定モデル: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### 暗号化設定

ccBitTorrentは、安全なピア接続のためにBEP 3 Message Stream Encryption（MSE）とProtocol Encryption（PE）をサポートしています。

**暗号化設定：**

- `enable_encryption`（bool、デフォルト: `false`）: プロトコル暗号化サポートを有効化
- `encryption_mode`（str、デフォルト: `"preferred"`）: 暗号化モード
  - `"disabled"`: 暗号化なし（プレーンのみ）
  - `"preferred"`: 暗号化を試み、利用できない場合はプレーンにフォールバック
  - `"required"`: 暗号化必須、暗号化が利用できない場合は接続失敗
- `encryption_dh_key_size`（int、デフォルト: `768`）: Diffie-Hellmanキーサイズ（ビット単位）（768または1024）
- `encryption_prefer_rc4`（bool、デフォルト: `true`）: 古いクライアントとの互換性のためにRC4暗号を優先
- `encryption_allowed_ciphers`（list[str]、デフォルト: `["rc4", "aes"]`）: 許可される暗号タイプ
  - `"rc4"`: RC4ストリーム暗号（最も互換性が高い）
  - `"aes"`: CFBモードのAES暗号（より安全）
  - `"chacha20"`: ChaCha20暗号（まだ実装されていません）
- `encryption_allow_plain_fallback`（bool、デフォルト: `true`）: 暗号化が失敗した場合にプレーン接続へのフォールバックを許可（`encryption_mode`が`"preferred"`の場合のみ適用）

**環境変数：**

- `CCBT_ENABLE_ENCRYPTION`: 暗号化を有効/無効（`true`/`false`）
- `CCBT_ENCRYPTION_MODE`: 暗号化モード（`disabled`/`preferred`/`required`）
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DHキーサイズ（`768`または`1024`）
- `CCBT_ENCRYPTION_PREFER_RC4`: RC4を優先（`true`/`false`）
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: カンマ区切りリスト（例: `"rc4,aes"`）
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: プレーンフォールバックを許可（`true`/`false`）

**設定例：**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**セキュリティに関する考慮事項：**

1. **RC4互換性**: RC4は互換性のためにサポートされていますが、暗号学的に弱いです。可能な場合はAESを使用してセキュリティを向上させてください。
2. **DHキーサイズ**: 768ビットのDHキーは、ほとんどのユースケースに適切なセキュリティを提供します。1024ビットはより強力なセキュリティを提供しますが、ハンドシェイクのレイテンシを増加させます。
3. **暗号化モード**:
   - `preferred`: 互換性に最適 - 暗号化を試みますが、エレガントにフォールバックします
   - `required`: 最も安全ですが、暗号化をサポートしないピアとの接続に失敗する可能性があります
4. **パフォーマンスへの影響**: 暗号化は最小限のオーバーヘッドを追加します（RC4で約1-5%、AESで約2-8%）が、プライバシーを向上させ、トラフィックシェイピングを回避するのに役立ちます。

**実装の詳細：**

暗号化の実装: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSEハンドシェイク: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- 暗号スイート: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py)（RC4、AES）
- Diffie-Hellman交換: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML設定

機械学習設定: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML設定モデル: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ダッシュボード設定

ダッシュボード設定: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

ダッシュボード設定モデル: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## 環境変数

環境変数は`CCBT_`プレフィックスを使用し、階層的な命名スキームに従います。

参照: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

形式: `CCBT_<SECTION>_<OPTION>=<value>`

例:
- ネットワーク: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- ディスク: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- 戦略: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- 発見: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- 可観測性: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- 制限: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- セキュリティ: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

環境変数の解析: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## 設定スキーマ

設定スキーマと検証: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

スキーマは以下を定義します：
- フィールドタイプと制約
- デフォルト値
- 検証ルール
- ドキュメント

## 設定機能

設定機能と機能検出: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## 設定テンプレート

事前定義された設定テンプレート: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

テンプレート:
- 高性能セットアップ
- 低リソースセットアップ
- セキュリティ重視セットアップ
- 開発セットアップ

## 設定例

設定例は[examples/](examples/)ディレクトリで利用できます：

- 基本設定: [example-config-basic.toml](examples/example-config-basic.toml)
- 高度な設定: [example-config-advanced.toml](examples/example-config-advanced.toml)
- パフォーマンス設定: [example-config-performance.toml](examples/example-config-performance.toml)
- セキュリティ設定: [example-config-security.toml](examples/example-config-security.toml)

## ホットリロード

設定のホットリロードサポート: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

設定システムは、クライアントを再起動せずに変更をリロードすることをサポートします。

## 設定移行

設定移行ユーティリティ: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

設定バージョン間の移行ツール。

## 設定のバックアップと差分

設定管理ユーティリティ:
- バックアップ: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- 差分: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## 条件付き設定

条件付き設定サポート: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## ヒントとベストプラクティス

### パフォーマンスチューニング

- 大きなシーケンシャル書き込みには`disk.write_buffer_kib`を増やす: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Linux/NVMeで`direct_io`を有効にして書き込みスループットを向上: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- ネットワークに合わせて`network.pipeline_depth`と`network.block_size_kib`を調整: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### リソース最適化

- CPUコア数に基づいて`disk.hash_workers`を調整: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- 利用可能なRAMに基づいて`disk.cache_size_mb`を設定: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- 帯域幅に基づいて`network.max_global_peers`を設定: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### ネットワーク設定

- ネットワーク条件に基づいてタイムアウトを設定: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- 必要に応じてプロトコルを有効/無効化: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- 適切にレート制限を設定: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

詳細なパフォーマンスチューニングについては、[パフォーマンスチューニングガイド](performance.md)を参照してください。






ccBitTorrentは、TOMLサポート、検証、ホットリロード、複数ソースからの階層的読み込みを備えた包括的な設定システムを使用します。

設定システム: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## 設定ソースと優先順位

設定は次の順序で読み込まれます（後のソースが前のソースを上書きします）：

1. **デフォルト**: [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)からの組み込みの適切なデフォルト値
2. **設定ファイル**: 現在のディレクトリまたは`~/.config/ccbt/ccbt.toml`の`ccbt.toml`。参照: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **環境変数**: `CCBT_*`プレフィックス付き変数。参照: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI引数**: コマンドラインオーバーライド。参照: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **トレントごと**: 個別のトレント設定（将来の機能）

設定の読み込み: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## 設定ファイル

### デフォルト設定

デフォルト設定ファイルを参照: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

設定はセクションごとに整理されています：

### ネットワーク設定

ネットワーク設定: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- 接続制限: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- リクエストパイプライン: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- ソケットチューニング: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- タイムアウト: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- リスン設定: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- トランスポートプロトコル: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- レート制限: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- チョーキング戦略: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- トラッカー設定: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

ネットワーク設定モデル: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ディスク設定

ディスク設定: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- 事前割り当て: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- 書き込み最適化: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- ハッシュ検証: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/Oスレッディング: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- 高度な設定: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- ストレージサービス設定: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: ストレージサービスの最大ファイルサイズ制限（MB単位）（0またはNone = 無制限、最大1048576 = 1TB）。テスト中の無制限ディスク書き込みを防ぎ、本番使用のために設定できます。
- チェックポイント設定: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

ディスク設定モデル: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 戦略設定

戦略設定: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- ピース選択: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- 高度な戦略: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- ピース優先度: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

戦略設定モデル: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 発見設定

発見設定: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT設定: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX設定: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- トラッカー設定: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: トラッカーアナウンス間隔（秒単位）（デフォルト: 1800.0、範囲: 60.0-86400.0）
  - `tracker_scrape_interval`: 定期的なスクレイピングのためのトラッカースクレイプ間隔（秒単位）（デフォルト: 3600.0、範囲: 60.0-86400.0）
  - `tracker_auto_scrape`: トレントが追加されたときにトラッカーを自動的にスクレイプ（BEP 48）（デフォルト: false）
  - 環境変数: `CCBT_TRACKER_ANNOUNCE_INTERVAL`、`CCBT_TRACKER_SCRAPE_INTERVAL`、`CCBT_TRACKER_AUTO_SCRAPE`

発見設定モデル: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 制限設定

レート制限: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- グローバル制限: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- トレントごとの制限: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- ピアごとの制限: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- スケジューラー設定: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

制限設定モデル: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 可観測性設定

可観測性設定: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- ロギング: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- メトリクス: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- トレーシングとアラート: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

可観測性設定モデル: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### セキュリティ設定

セキュリティ設定: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

セキュリティ設定モデル: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### 暗号化設定

ccBitTorrentは、安全なピア接続のためにBEP 3 Message Stream Encryption（MSE）とProtocol Encryption（PE）をサポートしています。

**暗号化設定：**

- `enable_encryption`（bool、デフォルト: `false`）: プロトコル暗号化サポートを有効化
- `encryption_mode`（str、デフォルト: `"preferred"`）: 暗号化モード
  - `"disabled"`: 暗号化なし（プレーンのみ）
  - `"preferred"`: 暗号化を試み、利用できない場合はプレーンにフォールバック
  - `"required"`: 暗号化必須、暗号化が利用できない場合は接続失敗
- `encryption_dh_key_size`（int、デフォルト: `768`）: Diffie-Hellmanキーサイズ（ビット単位）（768または1024）
- `encryption_prefer_rc4`（bool、デフォルト: `true`）: 古いクライアントとの互換性のためにRC4暗号を優先
- `encryption_allowed_ciphers`（list[str]、デフォルト: `["rc4", "aes"]`）: 許可される暗号タイプ
  - `"rc4"`: RC4ストリーム暗号（最も互換性が高い）
  - `"aes"`: CFBモードのAES暗号（より安全）
  - `"chacha20"`: ChaCha20暗号（まだ実装されていません）
- `encryption_allow_plain_fallback`（bool、デフォルト: `true`）: 暗号化が失敗した場合にプレーン接続へのフォールバックを許可（`encryption_mode`が`"preferred"`の場合のみ適用）

**環境変数：**

- `CCBT_ENABLE_ENCRYPTION`: 暗号化を有効/無効（`true`/`false`）
- `CCBT_ENCRYPTION_MODE`: 暗号化モード（`disabled`/`preferred`/`required`）
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DHキーサイズ（`768`または`1024`）
- `CCBT_ENCRYPTION_PREFER_RC4`: RC4を優先（`true`/`false`）
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: カンマ区切りリスト（例: `"rc4,aes"`）
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: プレーンフォールバックを許可（`true`/`false`）

**設定例：**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**セキュリティに関する考慮事項：**

1. **RC4互換性**: RC4は互換性のためにサポートされていますが、暗号学的に弱いです。可能な場合はAESを使用してセキュリティを向上させてください。
2. **DHキーサイズ**: 768ビットのDHキーは、ほとんどのユースケースに適切なセキュリティを提供します。1024ビットはより強力なセキュリティを提供しますが、ハンドシェイクのレイテンシを増加させます。
3. **暗号化モード**:
   - `preferred`: 互換性に最適 - 暗号化を試みますが、エレガントにフォールバックします
   - `required`: 最も安全ですが、暗号化をサポートしないピアとの接続に失敗する可能性があります
4. **パフォーマンスへの影響**: 暗号化は最小限のオーバーヘッドを追加します（RC4で約1-5%、AESで約2-8%）が、プライバシーを向上させ、トラフィックシェイピングを回避するのに役立ちます。

**実装の詳細：**

暗号化の実装: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSEハンドシェイク: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- 暗号スイート: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py)（RC4、AES）
- Diffie-Hellman交換: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML設定

機械学習設定: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML設定モデル: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ダッシュボード設定

ダッシュボード設定: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

ダッシュボード設定モデル: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## 環境変数

環境変数は`CCBT_`プレフィックスを使用し、階層的な命名スキームに従います。

参照: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

形式: `CCBT_<SECTION>_<OPTION>=<value>`

例:
- ネットワーク: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- ディスク: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- 戦略: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- 発見: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- 可観測性: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- 制限: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- セキュリティ: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

環境変数の解析: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## 設定スキーマ

設定スキーマと検証: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

スキーマは以下を定義します：
- フィールドタイプと制約
- デフォルト値
- 検証ルール
- ドキュメント

## 設定機能

設定機能と機能検出: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## 設定テンプレート

事前定義された設定テンプレート: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

テンプレート:
- 高性能セットアップ
- 低リソースセットアップ
- セキュリティ重視セットアップ
- 開発セットアップ

## 設定例

設定例は[examples/](examples/)ディレクトリで利用できます：

- 基本設定: [example-config-basic.toml](examples/example-config-basic.toml)
- 高度な設定: [example-config-advanced.toml](examples/example-config-advanced.toml)
- パフォーマンス設定: [example-config-performance.toml](examples/example-config-performance.toml)
- セキュリティ設定: [example-config-security.toml](examples/example-config-security.toml)

## ホットリロード

設定のホットリロードサポート: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

設定システムは、クライアントを再起動せずに変更をリロードすることをサポートします。

## 設定移行

設定移行ユーティリティ: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

設定バージョン間の移行ツール。

## 設定のバックアップと差分

設定管理ユーティリティ:
- バックアップ: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- 差分: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## 条件付き設定

条件付き設定サポート: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## ヒントとベストプラクティス

### パフォーマンスチューニング

- 大きなシーケンシャル書き込みには`disk.write_buffer_kib`を増やす: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Linux/NVMeで`direct_io`を有効にして書き込みスループットを向上: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- ネットワークに合わせて`network.pipeline_depth`と`network.block_size_kib`を調整: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### リソース最適化

- CPUコア数に基づいて`disk.hash_workers`を調整: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- 利用可能なRAMに基づいて`disk.cache_size_mb`を設定: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- 帯域幅に基づいて`network.max_global_peers`を設定: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### ネットワーク設定

- ネットワーク条件に基づいてタイムアウトを設定: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- 必要に応じてプロトコルを有効/無効化: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- 適切にレート制限を設定: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

詳細なパフォーマンスチューニングについては、[パフォーマンスチューニングガイド](performance.md)を参照してください。
































































































































































































