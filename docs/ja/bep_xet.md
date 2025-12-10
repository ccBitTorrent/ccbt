# BEP XET: コンテンツ定義チャンキングと重複排除のためのXetプロトコル拡張

## 概要

Xetプロトコル拡張（BEP XET）は、ピアツーピアコンテンツアドレッサブルストレージ（CAS）システムを通じてコンテンツ定義チャンキング（CDC）とトレント間重複排除を可能にするBitTorrentプロトコル拡張です。この拡張は、BitTorrentを協力と効率的なデータ共有に最適化された超高速で更新可能なピアツーピアファイルシステムに変換します。

## 根拠

Xetプロトコル拡張は、従来のBitTorrentの主要な制限に対処します：

1. **固定ピースサイズ**：従来のBitTorrentは固定ピースサイズを使用し、ファイルが変更されると非効率な再配布につながります。CDCはコンテンツ境界に適応します。

2. **トレント間重複排除なし**：各トレントは独立しており、同一のコンテンツを共有していてもそうです。Xetはトレント間でチャンクレベルの重複排除を可能にします。

3. **集中ストレージ**：従来のCASシステムは外部サービスを必要とします。XetはDHTとトラッカーを使用してBitTorrentネットワークに直接CASを構築します。

4. **非効率な更新**：共有ファイルの更新にはファイル全体の再配布が必要です。Xetは変更されたチャンクのみを再配布します。

CDC、重複排除、P2P CASを組み合わせることで、XetはBitTorrentを協力に最適化された超高速で更新可能なピアツーピアファイルシステムに変換します。

### 主な機能

- **コンテンツ定義チャンキング（CDC）**：Gearhashベースのインテリジェントファイル分割（8KB-128KBチャンク）
- **トレント間重複排除**：複数のトレント間でのチャンクレベル重複排除
- **ピアツーピアCAS**：DHTとトラッカーを使用した分散コンテンツアドレッサブルストレージ
- **Merkle Tree検証**：整合性のためのBLAKE3-256ハッシュとSHA-256フォールバック
- **Xorb形式**：複数のチャンクをグループ化するための効率的なストレージ形式
- **Shard形式**：ファイル情報とCASデータのメタデータストレージ
- **LZ4圧縮**：Xorbデータのオプション圧縮

## ユースケース

### 1. 協力ファイル共有

Xetは以下により効率的な協力を可能にします：
- **重複排除**：複数のトレント間で共有されるファイルは同じチャンクを共有します
- **高速更新**：変更されたチャンクのみが再配布される必要があります
- **バージョン管理**：Merkle treeルートを通じてファイルバージョンを追跡します

### 2. 大容量ファイル配布

大容量ファイルやデータセットの場合：
- **コンテンツ定義チャンキング**：インテリジェントな境界により、編集時のチャンク再配布が減少します
- **並列ダウンロード**：複数のピアから同時にチャンクをダウンロードします
- **再開機能**：信頼性の高い再開のために個別のチャンクを追跡します

### 3. ピアツーピアファイルシステム

BitTorrentをP2Pファイルシステムに変換：
- **CAS統合**：グローバルな可用性のためにDHTに保存されたチャンク
- **メタデータストレージ**：Shardがファイルシステムメタデータを提供します
- **高速ルックアップ**：ハッシュによる直接チャンクアクセスにより、完全なトレントダウンロードの必要性がなくなります

## 実装状況

Xetプロトコル拡張はccBitTorrentに完全に実装されています：

- ✅ コンテンツ定義チャンキング（Gearhash CDC）
- ✅ BLAKE3-256ハッシュとSHA-256フォールバック
- ✅ SQLite重複排除キャッシュ
- ✅ DHT統合（BEP 44）
- ✅ トラッカー統合
- ✅ XorbおよびShard形式
- ✅ Merkle tree計算
- ✅ BitTorrentプロトコル拡張（BEP 10）
- ✅ CLI統合
- ✅ 設定管理

## 設定

### CLIコマンド

```bash
# Xetプロトコルを有効化
ccbt xet enable

# Xetステータスを表示
ccbt xet status

# 重複排除統計を表示
ccbt xet stats

# 未使用チャンクをクリーンアップ
ccbt xet cleanup --max-age-days 30
```

### Xetプロトコルを有効化

`ccbt.toml`でXetサポートを設定します：

```toml
[disk]
# Xetプロトコル設定
xet_enabled = false                        # Xetプロトコルを有効化
xet_chunk_min_size = 8192                  # 最小チャンクサイズ（バイト）
xet_chunk_max_size = 131072                # 最大チャンクサイズ（バイト）
xet_chunk_target_size = 16384              # ターゲットチャンクサイズ（バイト）
xet_deduplication_enabled = true           # チャンクレベル重複排除を有効化
xet_cache_db_path = "data/xet_cache.db"    # SQLiteキャッシュデータベースパス
xet_chunk_store_path = "data/xet_chunks"   # チャンクストレージディレクトリ
xet_use_p2p_cas = true                     # P2Pコンテンツアドレッサブルストレージを使用
xet_compression_enabled = true             # XorbデータのLZ4圧縮を有効化
```


## プロトコル仕様

### 拡張ネゴシエーション

XET拡張はネゴシエーションのためにBEP 10（Extension Protocol）に従います。拡張ハンドシェイク中、ピアは拡張機能を交換します：

- **拡張名**：`ut_xet`
- **拡張ID**：ハンドシェイク中に動的に割り当て（1-255）
- **必要な機能**：なし（拡張はオプション）

XETをサポートするピアは、拡張ハンドシェイクに`ut_xet`を含めます。拡張IDはメッセージルーティングのためにピアセッションごとに保存されます。

### メッセージタイプ

XET拡張は以下のメッセージタイプを定義します：

#### チャンクメッセージ

1. **CHUNK_REQUEST (0x01)**：ハッシュで特定のチャンクをリクエスト
2. **CHUNK_RESPONSE (0x02)**：チャンクデータを含むレスポンス
3. **CHUNK_NOT_FOUND (0x03)**：ピアがリクエストされたチャンクを持っていない
4. **CHUNK_ERROR (0x04)**：チャンク取得中にエラーが発生

#### フォルダ同期メッセージ

5. **FOLDER_VERSION_REQUEST (0x10)**：フォルダバージョンをリクエスト（gitコミット参照）
6. **FOLDER_VERSION_RESPONSE (0x11)**：フォルダバージョンを含むレスポンス
7. **FOLDER_UPDATE_NOTIFY (0x12)**：ピアにフォルダ更新を通知
8. **FOLDER_SYNC_MODE_REQUEST (0x13)**：同期モードをリクエスト
9. **FOLDER_SYNC_MODE_RESPONSE (0x14)**：同期モードを含むレスポンス

#### メタデータ交換メッセージ

10. **FOLDER_METADATA_REQUEST (0x20)**：フォルダメタデータをリクエスト（.tonicファイル）
11. **FOLDER_METADATA_RESPONSE (0x21)**：フォルダメタデータピースを含むレスポンス
12. **FOLDER_METADATA_NOT_FOUND (0x22)**：メタデータが利用不可

#### ブルームフィルターメッセージ

13. **BLOOM_FILTER_REQUEST (0x30)**：チャンク可用性のためのピアのブルームフィルターをリクエスト
14. **BLOOM_FILTER_RESPONSE (0x31)**：ブルームフィルターデータを含むレスポンス

### メッセージ形式

#### CHUNK_REQUEST

```
Offset  サイズ  説明
0       32      チャンクハッシュ（BLAKE3-256またはSHA-256）
```

#### CHUNK_RESPONSE

```
Offset  サイズ  説明
0       32      チャンクハッシュ
32      4       チャンクデータ長（big-endian）
36      N       チャンクデータ
```

#### CHUNK_NOT_FOUND

```
Offset  サイズ  説明
0       32      チャンクハッシュ
```

#### CHUNK_ERROR

```
Offset  サイズ  説明
0       32      チャンクハッシュ
32      4       エラーコード（big-endian）
36      N       エラーメッセージ（UTF-8）
```

#### FOLDER_VERSION_REQUEST

```
Offset  サイズ  説明
0       N       フォルダ識別子（UTF-8、null終端）
```

#### FOLDER_VERSION_RESPONSE

```
Offset  サイズ  説明
0       N       フォルダ識別子（UTF-8、null終端）
N       40      Gitコミット参照（SHA-1、20バイト）または（SHA-256、32バイト）
```

#### FOLDER_UPDATE_NOTIFY

```
Offset  サイズ  説明
0       N       フォルダ識別子（UTF-8、null終端）
N       40      新しいgitコミット参照
N+40    8       タイムスタンプ（big-endian、Unixエポック）
```

#### FOLDER_SYNC_MODE_REQUEST

```
Offset  サイズ  説明
0       N       フォルダ識別子（UTF-8、null終端）
```

#### FOLDER_SYNC_MODE_RESPONSE

```
Offset  サイズ  説明
0       N       フォルダ識別子（UTF-8、null終端）
N       1       同期モード（0=DESIGNATED、1=BEST_EFFORT、2=BROADCAST、3=CONSENSUS）
```

#### FOLDER_METADATA_REQUEST

```
Offset  サイズ  説明
0       N       フォルダ識別子（UTF-8、null終端）
N       4       ピースインデックス（big-endian、0ベース）
```

#### FOLDER_METADATA_RESPONSE

```
Offset  サイズ  説明
0       N       フォルダ識別子（UTF-8、null終端）
N       4       ピースインデックス（big-endian）
N+4     4       総ピース数（big-endian）
N+8     4       ピースサイズ（big-endian）
N+12    M       ピースデータ（bencoded .tonicファイルフラグメント）
```

#### BLOOM_FILTER_REQUEST

```
Offset  サイズ  説明
0       4       フィルターサイズ（バイト、big-endian）
```

#### BLOOM_FILTER_RESPONSE

```
Offset  サイズ  説明
0       4       フィルターサイズ（バイト、big-endian）
4       4       ハッシュ数（big-endian）
8       N       ブルームフィルターデータ（ビット配列）
```

### チャンク発見

チャンクは複数のメカニズムを通じて発見されます：

1. **DHT（BEP 44）**：DHTを使用してチャンクメタデータを保存および取得します。チャンクハッシュ（32バイト）がDHTキーとして使用されます。メタデータ形式：`{"type": "xet_chunk", "available": True, "ed25519_public_key": "...", "ed25519_signature": "..."}`

2. **トラッカー**：チャンク可用性をトラッカーにアナウンスします。チャンクハッシュの最初の20バイトがトラッカーアナウンスのinfo_hashとして使用されます。

3. **ピア交換（PEX）**：チャンク可用性メッセージ付きの拡張PEX（BEP 11）。`CHUNKS_ADDED`および`CHUNKS_DROPPED`メッセージタイプがチャンクハッシュリストを交換します。

4. **ブルームフィルター**：チャンク可用性クエリを事前フィルタリングします。ピアは利用可能なチャンクを含むブルームフィルターを交換してネットワークオーバーヘッドを削減します。

5. **チャンクカタログ**：チャンクハッシュをピア情報にマッピングするメモリ内または永続的なインデックス。複数のチャンクの高速一括クエリを可能にします。

6. **ローカルピア発見（BEP 14）**：ローカルネットワークピア発見のためのUDPマルチキャスト。XET固有のマルチキャストアドレスとポートが設定可能です。

7. **マルチキャストブロードキャスト**：ローカルネットワーク上のチャンクアナウンスのためのUDPマルチキャスト。

8. **ゴシッププロトコル**：設定可能なファンアウトと間隔を持つ分散更新伝播のためのエピデミックスタイルプロトコル。

9. **制御フラッディング**：優先度しきい値付きの緊急更新のためのTTLベースのフラッディングメカニズム。

10. **トレントメタデータ**：トレントXETメタデータまたはBitTorrent v2ピースレイヤーからチャンクハッシュを抽出します。

### フォルダ同期

XETは複数の同期モードでフォルダ同期をサポートします：

#### 同期モード

- **DESIGNATED (0)**：単一の真実の源。1つのピアがソースとして指定され、他のピアはそれから同期します。稼働時間とチャンク可用性に基づく自動ソースピア選出。

- **BEST_EFFORT (1)**：すべてのノードが更新に貢献し、ベストエフォート。last-write-wins、version-vector、3-way-merge、またはタイムスタンプ戦略による競合解決。

- **BROADCAST (2)**：特定のノードがキューイング付きで更新をブロードキャストします。伝播のためにゴシッププロトコルまたは制御フラッディングを使用します。

- **CONSENSUS (3)**：更新にはノードの過半数の同意が必要です。単純過半数、Raftコンセンサス、またはビザンチンフォールトトレランス（BFT）をサポートします。

#### 競合解決

BEST_EFFORTモードで競合が検出された場合、以下の戦略が利用可能です：

- **last-write-wins**：最新の変更タイムスタンプが勝ちます
- **version-vector**：ベクトルクロックベースの競合検出と解決
- **3-way-merge**：自動競合解決のための3方向マージアルゴリズム
- **timestamp**：設定可能な時間ウィンドウ付きのタイムスタンプベースの解決

#### Git統合

フォルダバージョンはgitコミット参照（SHA-1またはSHA-256）を通じて追跡されます。`git diff`を通じて変更が検出されます。`git_auto_commit=True`の場合、自動コミットが有効になります。Gitリポジトリはフォルダルートで初期化されている必要があります。

#### 許可リスト

署名にEd25519、ストレージにAES-256-GCMを使用した暗号化許可リスト。ピアハンドシェイク中に検証されます。人間が読めるピア名のエイリアスがサポートされます。許可リストハッシュが拡張ハンドシェイク中に交換されます。

### .tonicファイル形式

`.tonic`ファイル形式（`.torrent`と同様）にはXET固有のメタデータが含まれます：

```
dictionary {
    "xet": dictionary {
        "version": integer,           # 形式バージョン（1）
        "sync_mode": integer,        # 0=DESIGNATED、1=BEST_EFFORT、2=BROADCAST、3=CONSENSUS
        "git_ref": string,           # Gitコミット参照（SHA-1またはSHA-256）
        "allowlist_hash": string,    # 許可リストのSHA-256ハッシュ
        "file_tree": dictionary {    # ネストされたディレクトリ構造
            "path": dictionary {
                "": dictionary {     # 空のキー = ファイルメタデータ
                    "hash": string,   # ファイルハッシュ
                    "size": integer   # ファイルサイズ
                }
            }
        },
        "files": list [              # フラットファイルリスト
            dictionary {
                "path": string,
                "hash": string,
                "size": integer
            }
        ],
        "chunk_hashes": list [       # チャンクハッシュのリスト（各32バイト）
            string
        ]
    }
}
```

### NATポートマッピング

XETは適切なNATトラバーサルのためにUDPポートマッピングを必要とします：

- **XETプロトコルポート**：`xet_port`経由で設定可能（デフォルトは`listen_port_udp`）。`map_xet_port=True`の場合、UPnP/NAT-PMP経由でマッピングされます。

- **XETマルチキャストポート**：`xet_multicast_port`経由で設定可能。`map_xet_multicast_port=True`の場合にマッピングされます（マルチキャストには通常不要）。

外部ポート情報が適切なピア発見のためにトラッカーに伝播されます。`NATManager.get_external_port()`はXETポートクエリのためにUDPプロトコルをサポートします。


## アーキテクチャ

### コアコンポーネント

#### 1. プロトコル拡張（`ccbt/extensions/xet.py`）

Xet拡張はチャンクリクエストとレスポンスのためにBEP 10（Extension Protocol）メッセージを実装します。

::: ccbt.extensions.xet.XetExtension
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**メッセージタイプ：**

```23:29:ccbt/extensions/xet.py
class XetMessageType(IntEnum):
    """Xet Extension message types."""

    CHUNK_REQUEST = 0x01  # Request chunk by hash
    CHUNK_RESPONSE = 0x02  # Response with chunk data
    CHUNK_NOT_FOUND = 0x03  # Chunk not available
    CHUNK_ERROR = 0x04  # Error retrieving chunk
```

**主要メソッド：**
- `encode_chunk_request()`: [ccbt/extensions/xet.py:89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L89) - リクエストID付きチャンクリクエストメッセージをエンコード
- `decode_chunk_request()`: [ccbt/extensions/xet.py:108](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L108) - チャンクリクエストメッセージをデコード
- `encode_chunk_response()`: [ccbt/extensions/xet.py:136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L136) - データ付きチャンクレスポンスをエンコード
- `handle_chunk_request()`: [ccbt/extensions/xet.py:210](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L210) - ピアからの着信チャンクリクエストを処理
- `handle_chunk_response()`: [ccbt/extensions/xet.py:284](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L284) - ピアからのチャンクレスポンスを処理

**拡張ハンドシェイク：**
- `encode_handshake()`: [ccbt/extensions/xet.py:61](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L61) - Xet拡張機能をエンコード
- `decode_handshake()`: [ccbt/extensions/xet.py:75](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L75) - ピアのXet拡張機能をデコード

#### 2. コンテンツ定義チャンキング（`ccbt/storage/xet_chunking.py`）

コンテンツパターンに基づく可変サイズチャンクを使用したインテリジェントファイル分割のためのGearhash CDCアルゴリズム。

::: ccbt.storage.xet_chunking.GearhashChunker
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**定数：**
- `MIN_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:21](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L21) - 最小チャンクサイズ8 KB
- `MAX_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L22) - 最大チャンクサイズ128 KB
- `TARGET_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:23](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L23) - デフォルトターゲットチャンクサイズ16 KB
- `WINDOW_SIZE`: [ccbt/storage/xet_chunking.py:24](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L24) - ローリングハッシュウィンドウ48バイト

**主要メソッド：**
- `chunk_buffer()`: [ccbt/storage/xet_chunking.py:210](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L210) - Gearhash CDCアルゴリズムを使用してデータをチャンク化
- `_find_chunk_boundary()`: [ccbt/storage/xet_chunking.py:242](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L242) - ローリングハッシュを使用してコンテンツ定義チャンク境界を見つける
- `_init_gear_table()`: [ccbt/storage/xet_chunking.py:54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L54) - ローリングハッシュのための事前計算gearテーブルを初期化

**アルゴリズム：**
Gearhashアルゴリズムは、コンテンツ定義境界を見つけるために事前計算された256要素gearテーブルを使用するローリングハッシュを使用します。これにより、異なるファイル内の類似コンテンツが同じチャンク境界を生成し、ファイル間重複排除を可能にします。

#### 3. 重複排除キャッシュ（`ccbt/storage/xet_deduplication.py`）

チャンクレベル重複排除のためのDHT統合を備えたSQLiteベースのローカル重複排除キャッシュ。

::: ccbt.storage.xet_deduplication.XetDeduplication
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**データベーススキーマ：**
- `chunks`テーブル: [ccbt/storage/xet_deduplication.py:65](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L65) - チャンクハッシュ、サイズ、ストレージパス、参照カウント、タイムスタンプを保存
- インデックス: [ccbt/storage/xet_deduplication.py:75](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L75) - 効率的なクエリのためにサイズとlast_accessedに

**主要メソッド：**
- `check_chunk_exists()`: [ccbt/storage/xet_deduplication.py:85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L85) - チャンクがローカルに存在するか確認し、アクセス時間を更新
- `store_chunk()`: [ccbt/storage/xet_deduplication.py:112](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L112) - 重複排除付きでチャンクを保存（存在する場合はref_countをインクリメント）
- `get_chunk_path()`: [ccbt/storage/xet_deduplication.py:165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L165) - チャンクのローカルストレージパスを取得
- `cleanup_unused_chunks()`: [ccbt/storage/xet_deduplication.py:201](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L201) - max_age_days以内にアクセスされなかったチャンクを削除

**機能：**
- 参照カウント：各チャンクを参照するトレント/ファイルの数を追跡
- 自動クリーンアップ：アクセス時間に基づいて未使用チャンクを削除
- 物理ストレージ：チャンクはハッシュをファイル名として`xet_chunks/`ディレクトリに保存されます

#### 4. ピアツーピアCAS（`ccbt/discovery/xet_cas.py`）

分散コンテンツアドレッサブルストレージのためのDHTおよびトラッカーベースのチャンク発見と交換。

::: ccbt.discovery.xet_cas.P2PCASClient
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**主要メソッド：**
- `announce_chunk()`: [ccbt/discovery/xet_cas.py:50](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L50) - チャンク可用性をDHT（BEP 44）およびトラッカーにアナウンス
- `find_chunk_peers()`: [ccbt/discovery/xet_cas.py:112](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L112) - DHTおよびトラッカークエリ経由で特定のチャンクを持つピアを見つける
- `request_chunk_from_peer()`: [ccbt/discovery/xet_cas.py:200](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L200) - Xet拡張プロトコルを使用して特定のピアからチャンクをリクエスト

**DHT統合：**
- BEP 44（Distributed Hash Table for Mutable Items）を使用してチャンクメタデータを保存
- チャンクメタデータ形式: [ccbt/discovery/xet_cas.py:68](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L68) - `{"type": "xet_chunk", "available": True}`
- 複数のDHTメソッドをサポート：`store()`、`store_chunk_hash()`、`get_chunk_peers()`、`get_peers()`、`find_value()`

**トラッカー統合：**
- チャンクハッシュの最初の20バイトをinfo_hashとして使用してトラッカーにチャンクをアナウンス
- チャンクのトラッカーベースピア発見を可能にします

## ストレージ形式

### Xorb形式

Xorbは効率的なストレージと取得のために複数のチャンクをグループ化します。

::: ccbt.storage.xet_xorb.Xorb
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**形式仕様：**
- ヘッダー: [ccbt/storage/xet_xorb.py:123](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L123) - 16バイト（magic `0x24687531`、バージョン、フラグ、予約）
- チャンク数: [ccbt/storage/xet_xorb.py:149](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L149) - 4バイト（uint32、little-endian）
- チャンクエントリ: [ccbt/storage/xet_xorb.py:140](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L140) - 可変（各チャンクのハッシュ、サイズ、データ）
- メタデータ: [ccbt/storage/xet_xorb.py:119](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L119) - 8バイト（合計非圧縮サイズをuint64として）

**定数：**
- `MAX_XORB_SIZE`: [ccbt/storage/xet_xorb.py:35](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L35) - 最大xorbサイズ64 MiB
- `XORB_MAGIC_INT`: [ccbt/storage/xet_xorb.py:36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L36) - マジックナンバー`0x24687531`
- `FLAG_COMPRESSED`: [ccbt/storage/xet_xorb.py:42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L42) - LZ4圧縮フラグ

**主要メソッド：**
- `add_chunk()`: [ccbt/storage/xet_xorb.py:62](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L62) - チャンクをxorbに追加（MAX_XORB_SIZEを超えると失敗）
- `serialize()`: [ccbt/storage/xet_xorb.py:84](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L84) - オプションのLZ4圧縮付きでxorbをバイナリ形式にシリアライズ
- `deserialize()`: [ccbt/storage/xet_xorb.py:200](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L200) - 自動解凍付きでバイナリ形式からxorbをデシリアライズ

**圧縮：**
- オプションLZ4圧縮: [ccbt/storage/xet_xorb.py:132](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L132) - `compress=True`でLZ4が利用可能な場合、チャンクデータを圧縮
- 自動検出: [ccbt/storage/xet_xorb.py:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L22) - LZ4がインストールされていない場合、優雅にフォールバック

### Shard形式

Shardは効率的なファイルシステム操作のためにファイルメタデータとCAS情報を保存します。

::: ccbt.storage.xet_shard.XetShard
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**形式仕様：**
- ヘッダー: [ccbt/storage/xet_shard.py:142](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L142) - 24バイト（magic `"SHAR"`、バージョン、フラグ、ファイル/xorb/チャンク数）
- ファイル情報セクション: [ccbt/storage/xet_shard.py:145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L145) - 可変（各ファイルのパス、ハッシュ、サイズ、xorb参照）
- CAS情報セクション: [ccbt/storage/xet_shard.py:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L148) - 可変（xorbハッシュ、チャンクハッシュ）
- HMACフッター: [ccbt/storage/xet_shard.py:150](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L150) - 32バイト（キーが提供された場合のHMAC-SHA256）

**定数：**
- `SHARD_MAGIC`: [ccbt/storage/xet_shard.py:19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L19) - マジックバイト`b"SHAR"`
- `SHARD_VERSION`: [ccbt/storage/xet_shard.py:20](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L20) - 形式バージョン1
- `HMAC_SIZE`: [ccbt/storage/xet_shard.py:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L22) - HMAC-SHA256用32バイト

**主要メソッド：**
- `add_file_info()`: [ccbt/storage/xet_shard.py:47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L47) - xorb参照付きでファイルメタデータを追加
- `add_chunk_hash()`: [ccbt/storage/xet_shard.py:80](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L80) - チャンクハッシュをshardに追加
- `add_xorb_hash()`: [ccbt/storage/xet_shard.py:93](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L93) - xorbハッシュをshardに追加
- `serialize()`: [ccbt/storage/xet_shard.py:106](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L106) - オプションのHMAC付きでshardをバイナリ形式にシリアライズ
- `deserialize()`: [ccbt/storage/xet_shard.py:201](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L201) - HMAC検証付きでバイナリ形式からshardをデシリアライズ

**整合性：**
- HMAC検証: [ccbt/storage/xet_shard.py:170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L170) - shard整合性のためのオプションHMAC-SHA256

## Merkle Tree計算

ファイルは、効率的な整合性検証のためにチャンクハッシュから構築されたMerkle treeを使用して検証されます。

::: ccbt.storage.xet_hashing.XetHasher
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**ハッシュ関数：**
- `compute_chunk_hash()`: [ccbt/storage/xet_hashing.py:43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L43) - チャンクのBLAKE3-256ハッシュを計算（SHA-256にフォールバック）
- `compute_xorb_hash()`: [ccbt/storage/xet_hashing.py:63](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L63) - xorbデータのハッシュを計算
- `verify_chunk_hash()`: [ccbt/storage/xet_hashing.py:158](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L158) - 期待されるハッシュに対してチャンクデータを検証

**Merkle Tree構築：**
- `build_merkle_tree()`: [ccbt/storage/xet_hashing.py:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L78) - チャンクデータからMerkle treeを構築（最初にチャンクをハッシュ）
- `build_merkle_tree_from_hashes()`: [ccbt/storage/xet_hashing.py:115](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L115) - 事前計算されたチャンクハッシュからMerkle treeを構築

**アルゴリズム：**
Merkle treeは、各レベルでハッシュをペアリングすることにより、下から上に構築されます：
1. チャンクハッシュ（リーフノード）から開始
2. 隣接するハッシュをペアリングし、組み合わせをハッシュ
3. 単一のルートハッシュが残るまで繰り返し
4. 奇数：ペアリングのために最後のハッシュを複製

**インクリメンタルハッシュ：**
- `hash_file_incremental()`: [ccbt/storage/xet_hashing.py:175](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L175) - メモリ効率のためにインクリメンタルにファイルハッシュを計算

**ハッシュサイズ：**
- `HASH_SIZE`: [ccbt/storage/xet_hashing.py:40](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L40) - BLAKE3-256またはSHA-256用32バイト

**BLAKE3サポート：**
- 自動検出: [ccbt/storage/xet_hashing.py:21](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L21) - 利用可能な場合はBLAKE3を使用し、SHA-256にフォールバック
- パフォーマンス：BLAKE3は大容量ファイルに対してより優れたパフォーマンスを提供します

## 参照

- [BEP 10: Extension Protocol](https://www.bittorrent.org/beps/bep_0010.html)
- [BEP 44: Distributed Hash Table for Mutable Items](https://www.bittorrent.org/beps/bep_0044.html)
- [BEP 52: BitTorrent Protocol v2](https://www.bittorrent.org/beps/bep_0052.html)
- [Gearhash Algorithm](https://github.com/xetdata/xet-core)

