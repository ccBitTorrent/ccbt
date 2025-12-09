# パフォーマンスチューニングガイド

このガイドでは、ccBitTorrentで最大のダウンロード速度と効率的なリソース使用を実現するためのパフォーマンス最適化技術について説明します。

## ネットワーク最適化

### 接続設定

#### パイプラインの深さ

ピアあたりの未処理リクエスト数を制御します。

設定: [ccbt.toml:12](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L12)

**推奨事項:**
- **高レイテンシ接続**: 32-64（衛星、モバイル）
- **低レイテンシ接続**: 16-32（光ファイバー、ケーブル）
- **ローカルネットワーク**: 8-16（LAN転送）

実装: [ccbt/peer/async_peer_connection.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/peer/async_peer_connection.py) - リクエストパイプライン

#### ブロックサイズ

ピアから要求されるデータブロックのサイズ。

設定: [ccbt.toml:13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L13)

**推奨事項:**
- **高帯域幅**: 32-64 KiB（光ファイバー、ケーブル）
- **中帯域幅**: 16-32 KiB（DSL、モバイル）
- **低帯域幅**: 4-16 KiB（ダイヤルアップ、低速モバイル）

最小/最大ブロックサイズ: [ccbt.toml:14-15](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L14-L15)

#### ソケットバッファ

高スループットシナリオでは増やします。

設定: [ccbt.toml:17-18](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L18)

デフォルト値: [ccbt.toml:17-18](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L18)（それぞれ256 KiB）

TCP_NODELAY設定: [ccbt.toml:19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L19)

### 接続制限

#### グローバルピア制限

設定: [ccbt.toml:6-7](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L7)

**チューニングガイドライン:**
- **高帯域幅**: グローバルピアを増やす（200-500）
- **低帯域幅**: グローバルピアを減らす（50-100）
- **多数のトレント**: トレントあたりの制限を減らす（10-25）
- **少数のトレント**: トレントあたりの制限を増やす（50-100）

実装: [ccbt/peer/connection_pool.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/peer/connection_pool.py) - 接続プール管理

ピアあたりの最大接続数: [ccbt.toml:8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L8)

#### 接続タイムアウト

設定: [ccbt.toml:22-25](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L25)

- 接続タイムアウト: [ccbt.toml:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22)
- ハンドシェイクタイムアウト: [ccbt.toml:23](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L23)
- キープアライブ間隔: [ccbt.toml:24](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L24)
- ピアタイムアウト: [ccbt.toml:25](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L25)

## ディスクI/O最適化

### 事前割り当て戦略

設定: [ccbt.toml:59](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59)

**推奨事項:**
- **SSD**: より良いパフォーマンスのために「full」を使用
- **HDD**: スペースを節約するために「sparse」を使用
- **ネットワークストレージ**: 遅延を避けるために「none」を使用

スパースファイルオプション: [ccbt.toml:60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L60)

実装: [ccbt/storage/disk_io.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - ディスクI/O操作

### 書き込み最適化

設定: [ccbt.toml:63-64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L64)

**チューニングガイドライン:**
- **高速ストレージ**: バッチサイズを増やす（128-256 KiB）
- **低速ストレージ**: バッチサイズを減らす（32-64 KiB）
- **重要なデータ**: sync_writesを有効化
- **パフォーマンス**: sync_writesを無効化

書き込みバッチサイズ: [ccbt.toml:63](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63)

書き込みバッファサイズ: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)

同期書き込み設定: [ccbt.toml:82](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L82)

ファイルアセンブラ: [ccbt/storage/file_assembler.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/file_assembler.py)

### メモリマッピング

設定: [ccbt.toml:65-66](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L65-L66)

**利点:**
- 完了したピースの読み込みが高速化
- メモリ使用量の削減
- OSキャッシングの改善

**考慮事項:**
- 十分なRAMが必要
- メモリ圧迫を引き起こす可能性
- 読み込み中心のワークロードに最適

MMAPを使用: [ccbt.toml:65](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L65)

MMAPキャッシュサイズ: [ccbt.toml:66](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L66)

MMAPキャッシュクリーンアップ間隔: [ccbt.toml:67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L67)

### 高度なI/O機能

#### io_uring（Linux）

設定: [ccbt.toml:84](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L84)

**要件:**
- Linuxカーネル5.1+
- モダンなストレージデバイス
- 十分なシステムリソース

#### ダイレクトI/O

設定: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)

**使用例:**
- 高性能ストレージ
- OSページキャッシュをバイパス
- 一貫したパフォーマンス

読み込み先取りサイズ: [ccbt.toml:83](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L83)

## 戦略選択

### ピース選択アルゴリズム

設定: [ccbt.toml:101](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101)

#### Rarest-First（推奨）

**利点:**
- 最適なスウォームの健全性
- より速い完了時間
- より良いピア協力

実装: [ccbt/piece/async_piece_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/async_piece_manager.py) - ピース選択ロジック

Rarest first閾値: [ccbt.toml:107](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107)

#### シーケンシャル

**使用例:**
- ストリーミングメディアファイル
- シーケンシャルアクセスパターン
- 優先度ベースのダウンロード

シーケンシャルウィンドウ: [ccbt.toml:108](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L108)

ストリーミングモード: [ccbt.toml:104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L104)

#### ラウンドロビン

**使用例:**
- シンプルなシナリオ
- デバッグ
- レガシー互換性

実装: [ccbt/piece/piece_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/piece_manager.py)

### エンドゲーム最適化

設定: [ccbt.toml:102-103](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L102-L103)

**チューニング:**
- **高速接続**: 閾値を下げる（0.85-0.9）
- **低速接続**: 閾値を上げる（0.95-0.98）
- **多数のピア**: 重複を増やす（3-5）
- **少数のピア**: 重複を減らす（1-2）

エンドゲーム閾値: [ccbt.toml:103](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L103)

エンドゲーム重複: [ccbt.toml:102](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L102)

パイプライン容量: [ccbt.toml:109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L109)

### ピース優先度

設定: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

最初のピース優先度: [ccbt.toml:112](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112)

最後のピース優先度: [ccbt.toml:113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L113)

## レート制限

### グローバル制限

設定: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)

グローバルダウンロード制限: [ccbt.toml:140](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140)（0 = 無制限）

グローバルアップロード制限: [ccbt.toml:141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L141)（0 = 無制限）

ネットワークレベル制限: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

実装: [ccbt/security/rate_limiter.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/rate_limiter.py) - レート制限ロジック

### トレントごとの制限

CLIで[ccbt/cli/main.py:download](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L369)を使用し、`--download-limit`と`--upload-limit`オプションで制限を設定します。

トレントごとの設定: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)

ピアごとの制限: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)

### スケジューラー設定

スケジューラータイムスライス: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

## ハッシュ検証

### ワーカースレッド

設定: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)

**チューニングガイドライン:**
- **CPUコア**: コア数に一致または超過
- **SSDストレージ**: より多くのワーカーを処理可能
- **HDDストレージ**: ワーカーを制限（2-4）

ハッシュチャンクサイズ: [ccbt.toml:71](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L71)

ハッシュバッチサイズ: [ccbt.toml:72](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L72)

ハッシュキューサイズ: [ccbt.toml:73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L73)

実装: [ccbt/storage/disk_io.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py) - ハッシュ検証ワーカー

## メモリ管理

### バッファサイズ

書き込みバッファ: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)

読み込み先取り: [ccbt.toml:83](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L83)

### キャッシュ設定

キャッシュサイズ: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)

MMAPキャッシュ: [ccbt.toml:66](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L66)

ディスクキューサイズ: [ccbt.toml:77](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L77)

ディスクワーカー: [ccbt.toml:76](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76)

## システムレベル最適化

### ファイルシステムチューニング

システムレベルの最適化については、オペレーティングシステムのドキュメントを参照してください。これらはccBitTorrentの設定外で適用される一般的な推奨事項です。

### ネットワークスタックチューニング

ネットワークスタックの最適化については、オペレーティングシステムのドキュメントを参照してください。これらは全体的なネットワークパフォーマンスに影響するシステムレベルの設定です。

## パフォーマンス監視

### 主要メトリクス

Prometheus経由でこれらの主要メトリクスを監視します:

- **ダウンロード速度**: `ccbt_download_rate_bytes_per_second` - [ccbt/utils/metrics.py:142](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/metrics.py#L142)を参照
- **アップロード速度**: `ccbt_upload_rate_bytes_per_second` - [ccbt/utils/metrics.py:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/metrics.py#L148)を参照
- **接続ピア**: MetricsCollector経由で利用可能
- **ディスクキュー深度**: MetricsCollector経由で利用可能 - [ccbt/monitoring/metrics_collector.py]を参照
- **ハッシュキュー深度**: MetricsCollector経由で利用可能

Prometheusメトリクスエンドポイント: [ccbt/utils/metrics.py:179](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/utils/metrics.py#L179)

### パフォーマンスプロファイリング

メトリクスを有効化: [ccbt.toml:164](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L164)

メトリクスポート: [ccbt.toml:165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L165)

有効化時は`http://localhost:9090/metrics`でメトリクスにアクセスできます。

CLI経由でメトリクスを表示: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L229)

## パフォーマンス問題のトラブルシューティング

### ダウンロード速度が低い

1. **ピア接続を確認**:
   Bitonicダッシュボードを起動: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L20)

2. **ピース選択を確認**:
   [ccbt.toml:101](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101)で設定
   
   実装: [ccbt/piece/async_piece_manager.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/piece/async_piece_manager.py)

3. **パイプライン深度を増やす**:
   [ccbt.toml:12](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L12)で設定
   
   実装: [ccbt/peer/async_peer_connection.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/peer/async_peer_connection.py)

4. **レート制限を確認**:
   設定: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
   
   CLIステータスコマンド: [ccbt/cli/main.py:status](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L789)

### CPU使用率が高い

1. **ハッシュワーカーを減らす**:
   [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)で設定

2. **メモリマッピングを無効化**:
   [ccbt.toml:65](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L65)で設定

3. **リフレッシュ間隔を増やす**:
   Bitonicリフレッシュ間隔: [ccbt/interface/terminal_dashboard.py:303](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L303)
   
   ダッシュボード設定: [ccbt.toml:189](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L189)

### ディスクI/Oボトルネック

1. **書き込みバッチングを有効化**:
   書き込みバッチサイズを設定: [ccbt.toml:63](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63)
   
   実装: [ccbt/storage/disk_io.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/disk_io.py)

2. **より高速なストレージを使用**:
   - ダウンロードをSSDに移動
   - パフォーマンスのためにRAID 0を使用

3. **ファイルシステムを最適化**:
   - 適切なファイルシステムを使用
   - マウントオプションを調整

## ベンチマーク

### ベンチマークスクリプト

パフォーマンスベンチマークスクリプトは`tests/performance/`にあります:

- ハッシュ検証: `tests/performance/bench_hash_verify.py`
- ディスクI/O: `tests/performance/bench_disk_io.py`
- ピースアセンブリ: `tests/performance/bench_piece_assembly.py`
- ループバックスループット: `tests/performance/bench_loopback_throughput.py`
- 暗号化: `tests/performance/bench_encryption.py`

すべてのベンチマークを実行: [tests/scripts/bench_all.py](https://github.com/yourusername/ccbittorrent/blob/main/tests/scripts/bench_all.py)

ベンチマーク設定例: [example-config-performance.toml](examples/example-config-performance.toml)

### ベンチマーク記録

ベンチマークは、時間の経過に伴うパフォーマンスを追跡するために、異なるモードで記録できます:

#### 記録モード

- **`pre-commit`**: pre-commitフック実行中に記録（クイックスモークテスト）
- **`commit`**: 実際のコミット中に記録（完全なベンチマーク、実行ごとと時系列の両方で記録）
- **`both`**: pre-commitとcommitコンテキストの両方で記録
- **`auto`**: コンテキストを自動検出（環境変数`PRE_COMMIT`を使用）
- **`none`**: 記録なし（ベンチマークは実行されますが、結果は保存されません）

#### 記録付きベンチマークの実行

```bash
# pre-commitモード（クイックスモークテスト）
uv run python tests/performance/bench_hash_verify.py --quick --record-mode=pre-commit

# commitモード（完全なベンチマーク）
uv run python tests/performance/bench_hash_verify.py --record-mode=commit

# 両方のモード
uv run python tests/performance/bench_hash_verify.py --record-mode=both

# 自動検出モード（デフォルト）
uv run python tests/performance/bench_hash_verify.py --record-mode=auto
```

#### ベンチマークデータストレージ

ベンチマーク結果は2つの形式で保存されます:

1. **実行ごとのファイル**（`docs/reports/benchmarks/runs/`）:
   - 各ベンチマーク実行の個別JSONファイル
   - ファイル名形式: `{benchmark_name}-{timestamp}-{commit_hash_short}.json`
   - 完全なメタデータを含む: gitコミットハッシュ、ブランチ、作成者、プラットフォーム情報、結果

2. **時系列ファイル**（`docs/reports/benchmarks/timeseries/`）:
   - JSON形式の集約された履歴データ
   - ファイル名形式: `{benchmark_name}_timeseries.json`
   - 時間の経過に伴うパフォーマンス傾向の簡単なクエリを可能にする

履歴データのクエリとベンチマークレポートの詳細については、[ベンチマークレポート](reports/benchmarks/index.md)を参照してください。

### テストとカバレッジアーティファクト

完全なテストスイートを実行する場合（pre-push/CI）、アーティファクトは以下に出力されます:

- `tests/.reports/junit.xml`（JUnitレポート）
- `tests/.reports/pytest.log`（テストログ）
- `coverage.xml`と`htmlcov/`（カバレッジレポート）

これらはCodecovと統合されます。`dev/.codecov.yml`のフラグは、カバレッジを正確に属性付けるために`ccbt/`サブパッケージ（例: `peer`、`piece`、`protocols`、`extensions`）に合わせて調整されています。カバレッジHTMLレポートは、`mkdocs-coverage`プラグイン経由で自動的にドキュメントに統合され、`site/reports/htmlcov/`から読み取り、[reports/coverage.md](reports/coverage.md)でレンダリングされます。

#### レガシーベンチマークアーティファクト

レガシーベンチマークアーティファクトは、`--output-dir`引数を使用する場合、後方互換性のために`site/reports/benchmarks/artifacts/`に引き続き書き込まれます。ただし、時間の経過に伴うパフォーマンスを追跡するには、新しい記録システムが推奨されます。

## ベストプラクティス

1. **デフォルトから始める**: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)のデフォルト設定から始める
2. **ベースラインを測定**: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/monitoring_commands.py#L229)を使用してパフォーマンスベースラインを確立
3. **1つの設定を変更**: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)で一度に1つの設定を変更
4. **徹底的にテスト**: 改善を確認
5. **リソースを監視**: [Bitonic](bitonic.md)経由でCPU、メモリ、ディスク使用量を監視
6. **変更を文書化**: 効果的な設定を記録

## 設定テンプレート

### 高性能セットアップ

高性能設定テンプレートの参照: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

主要設定:
- ネットワーク: [ccbt.toml:11-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L42)
- ディスク: [ccbt.toml:57-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L85)
- 戦略: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

例: [example-config-performance.toml](examples/example-config-performance.toml)

### 低リソースセットアップ

低リソース設定テンプレートの参照: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

主要設定:
- ネットワーク: [ccbt.toml:6-7](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L7) - ピア制限を減らす
- ディスク: [ccbt.toml:59-65](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L65) - スパース事前割り当てを使用、MMAPを無効化
- 戦略: [ccbt.toml:101](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101) - Rarest-firstが最適のまま

より詳細な設定オプションについては、[設定](configuration.md)ドキュメントを参照してください。
