# BEP 52: BitTorrent Protocol v2

## 概要

BitTorrent Protocol v2 (BEP 52) は、SHA-256ハッシュ、改善されたメタデータ構造、大容量ファイルへのより良いサポートを導入するBitTorrentプロトコルの主要なアップグレードです。ccBitTorrentは、v2専用トレント、v1専用トレント、および両方のプロトコルで動作するハイブリッドトレントの完全なサポートを提供します。

### 主な機能

- **SHA-256ハッシュ**: v1で使用されるSHA-1よりも安全
- **Merkle Tree構造**: 効率的なピース検証と部分ダウンロード
- **File Tree形式**: 階層的なファイル編成
- **Piece Layers**: ファイルごとのピース検証
- **ハイブリッドトレント**: v1クライアントとの後方互換性

## アーキテクチャ

### コアコンポーネント

#### 1. トレントメタデータ (`ccbt/core/torrent_v2.py`)

v2トレントパーサーはすべてのメタデータ操作を処理します：

```python
from ccbt.core.torrent_v2 import TorrentV2Parser, TorrentV2Info

# v2トレントを解析
parser = TorrentV2Parser()
with open("torrent_file.torrent", "rb") as f:
    torrent_data = decode(f.read())
    
v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

# v2固有のデータにアクセス
print(f"Info Hash v2: {v2_info.info_hash_v2.hex()}")
print(f"File Tree: {v2_info.file_tree}")
print(f"Piece Layers: {len(v2_info.piece_layers)}")
```

#### 2. プロトコル通信 (`ccbt/protocols/bittorrent_v2.py`)

v2ハンドシェイクとメッセージを処理します：

```python
from ccbt.protocols.bittorrent_v2 import (
    create_v2_handshake,
    send_v2_handshake,
    handle_v2_handshake,
    PieceLayerRequest,
    PieceLayerResponse,
)

# v2ハンドシェイクを作成
info_hash_v2 = v2_info.info_hash_v2
peer_id = b"-CC0101-" + b"x" * 12
handshake = create_v2_handshake(info_hash_v2, peer_id)

# ハンドシェイクを送信
await send_v2_handshake(writer, info_hash_v2, peer_id)

# ハンドシェイクを受信
version, peer_id, parsed = await handle_v2_handshake(reader, writer)
```

#### 3. SHA-256ハッシュ (`ccbt/piece/hash_v2.py`)

v2ハッシュ関数を実装します：

```python
from ccbt.piece.hash_v2 import (
    hash_piece_v2,
    hash_piece_layer,
    hash_file_tree,
    verify_piece_v2,
)

# ピースをハッシュ
piece_data = b"..." * 16384
piece_hash = hash_piece_v2(piece_data)

# ピースを検証
is_valid = verify_piece_v2(piece_data, expected_hash)

# Merkle treeを構築
piece_hashes = [hash_piece_v2(p) for p in pieces]
merkle_root = hash_piece_layer(piece_hashes)
```

## 設定

### プロトコルv2を有効化

`ccbt.toml`でv2プロトコルサポートを設定します：

```toml
[network.protocol_v2]
enable_protocol_v2 = true      # v2サポートを有効化
prefer_protocol_v2 = false     # 両方利用可能な場合、v1よりv2を優先
support_hybrid = true          # ハイブリッドトレントをサポート
v2_handshake_timeout = 30.0    # ハンドシェイクタイムアウト（秒）
```

### 環境変数

```bash
export CCBT_PROTOCOL_V2_ENABLE=true
export CCBT_PROTOCOL_V2_PREFER=true
export CCBT_PROTOCOL_V2_SUPPORT_HYBRID=true
export CCBT_PROTOCOL_V2_HANDSHAKE_TIMEOUT=30.0
```

### CLIフラグ

```bash
# プロトコルv2を有効化
ccbt download file.torrent --protocol-v2

# 利用可能な場合、v2を優先
ccbt download file.torrent --protocol-v2-prefer

# プロトコルv2を無効化
ccbt download file.torrent --no-protocol-v2
```

## トレントの作成

### V2専用トレント

v2クライアントでのみ動作するトレントを作成します：

```python
from pathlib import Path
from ccbt.core.torrent_v2 import TorrentV2Parser

parser = TorrentV2Parser()

# 単一ファイルから作成
torrent_bytes = parser.generate_v2_torrent(
    source=Path("video.mp4"),
    output=Path("video.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=262144,  # 256 KiB
    comment="My video file",
    private=False,
)

# ディレクトリから作成
torrent_bytes = parser.generate_v2_torrent(
    source=Path("my_files/"),
    output=Path("my_files.torrent"),
    trackers=[
        "http://tracker1.example.com/announce",
        "http://tracker2.example.com/announce",
    ],
    piece_length=None,  # 自動計算
)
```

### ハイブリッドトレント

v1とv2クライアントの両方と互換性のあるトレントを作成します：

```python
# ハイブリッドトレントを作成
torrent_bytes = parser.generate_hybrid_torrent(
    source=Path("archive.zip"),
    output=Path("archive.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=1048576,  # 1 MiB
    comment="Backwards compatible torrent",
    private=False,
)
```

### CLIトレント作成

```bash
# v2トレントを作成
ccbt create-torrent file.mp4 --v2 \
    --output file.torrent \
    --tracker http://tracker.example.com/announce \
    --piece-length 262144 \
    --comment "My file"

# ハイブリッドトレントを作成
ccbt create-torrent directory/ --hybrid \
    --output directory.torrent \
    --tracker http://tracker.example.com/announce \
    --private
```

## プロトコルの詳細

### ハンドシェイク形式

#### V2ハンドシェイク（80バイト）
```
- 1バイト:  プロトコル文字列の長さ（19）
- 19バイト: "BitTorrent protocol"
- 8バイト:  予約バイト（ビット0 = 1はv2サポート）
- 32バイト: SHA-256 info_hash_v2
- 20バイト: Peer ID
```

#### ハイブリッドハンドシェイク（100バイト）
```
- 1バイト:  プロトコル文字列の長さ（19）
- 19バイト: "BitTorrent protocol"
- 8バイト:  予約バイト（ビット0 = 1）
- 20バイト: SHA-1 info_hash_v1
- 32バイト: SHA-256 info_hash_v2
- 20バイト: Peer ID
```

### プロトコルバージョンのネゴシエーション

ccBitTorrentは自動的に最適なプロトコルバージョンをネゴシエートします：

```python
from ccbt.protocols.bittorrent_v2 import (
    ProtocolVersion,
    negotiate_protocol_version,
)

# ピアのハンドシェイク
peer_handshake = b"..."

# サポートされているバージョン（優先順位順）
supported = [
    ProtocolVersion.HYBRID,
    ProtocolVersion.V2,
    ProtocolVersion.V1,
]

# ネゴシエート
negotiated = negotiate_protocol_version(peer_handshake, supported)

if negotiated == ProtocolVersion.V2:
    # v2プロトコルを使用
    pass
elif negotiated == ProtocolVersion.HYBRID:
    # ハイブリッドモードを使用
    pass
elif negotiated == ProtocolVersion.V1:
    # v1にフォールバック
    pass
else:
    # 非互換
    pass
```

### V2固有のメッセージ

#### Piece Layerリクエスト（メッセージID 20）

ファイルのピースハッシュをリクエストします：

```python
from ccbt.protocols.bittorrent_v2 import PieceLayerRequest

pieces_root = b"..." # 32バイトのSHA-256ルートハッシュ
request = PieceLayerRequest(pieces_root)
message_bytes = request.serialize()
```

#### Piece Layerレスポンス（メッセージID 21）

ピースハッシュを送信します：

```python
from ccbt.protocols.bittorrent_v2 import PieceLayerResponse

piece_hashes = [b"..." * 32 for _ in range(10)]  # SHA-256ハッシュのリスト
response = PieceLayerResponse(pieces_root, piece_hashes)
message_bytes = response.serialize()
```

#### File Treeリクエスト（メッセージID 22）

完全なファイルツリーをリクエストします：

```python
from ccbt.protocols.bittorrent_v2 import FileTreeRequest

request = FileTreeRequest()
message_bytes = request.serialize()
```

#### File Treeレスポンス（メッセージID 23）

ファイルツリー構造を送信します：

```python
from ccbt.protocols.bittorrent_v2 import FileTreeResponse

file_tree_bencoded = encode(file_tree_dict)
response = FileTreeResponse(file_tree_bencoded)
message_bytes = response.serialize()
```

## File Tree構造

V2トレントは階層的なファイルツリーを使用します：

```python
from ccbt.core.torrent_v2 import FileTreeNode

# 単一ファイル
file_node = FileTreeNode(
    name="video.mp4",
    length=1000000,
    pieces_root=b"..." * 32,
    children=None,
)

# ディレクトリ構造
dir_node = FileTreeNode(
    name="my_files",
    length=0,
    pieces_root=None,
    children={
        "file1.txt": FileTreeNode(...),
        "file2.txt": FileTreeNode(...),
        "subdir": FileTreeNode(...),
    },
)

# ノードタイプを確認
if file_node.is_file():
    print(f"ファイル: {file_node.length} バイト")
if dir_node.is_directory():
    print(f"{len(dir_node.children)} アイテムを含むディレクトリ")
```

## Piece Layers

各ファイルにはSHA-256ハッシュを持つ独自のピースレイヤーがあります：

```python
from ccbt.core.torrent_v2 import PieceLayer

# ピースレイヤーを作成
layer = PieceLayer(
    piece_length=262144,  # 256 KiB
    pieces=[
        b"..." * 32,  # ピース0のハッシュ
        b"..." * 32,  # ピース1のハッシュ
        b"..." * 32,  # ピース2のハッシュ
    ],
)

# ピースハッシュを取得
piece_0_hash = layer.get_piece_hash(0)

# ピース数
num_pieces = layer.num_pieces()
```

## ベストプラクティス

### V2を使用する場合

- **新しいトレント**: 新しいコンテンツには常にv2を優先
- **大容量ファイル**: V2は1 GB以上のファイルにより効率的
- **セキュリティ**: SHA-256はより良い衝突耐性を提供
- **将来への準備**: V2はBitTorrentの未来

### ハイブリッドを使用する場合

- **最大の互換性**: v1とv2クライアントの両方に到達
- **移行期間**: エコシステムの移行中
- **公開トレント**: より広い配布

### V1専用を使用する場合

- **レガシーシステム**: v2サポートが利用できない場合のみ
- **小さなファイル**: V1のオーバーヘッドは100 MB未満で許容可能

### ピース長の選択

自動計算が推奨されますが、手動値：

- **小さなファイル（< 16 MiB）**: 16 KiB
- **中程度のファイル（16 MiB - 512 MiB）**: 256 KiB
- **大容量ファイル（> 512 MiB）**: 1 MiB
- **非常に大きなファイル（> 10 GiB）**: 2-4 MiB

ピース長は2の累乗でなければなりません。

## APIリファレンス

### TorrentV2Parser

v2トレント操作のメインクラス：

```python
class TorrentV2Parser:
    def parse_v2(self, info_dict: dict, torrent_data: dict) -> TorrentV2Info:
        """v2トレント情報辞書を解析します。"""
        
    def parse_hybrid(self, info_dict: dict, torrent_data: dict) -> tuple[TorrentInfo, TorrentV2Info]:
        """ハイブリッドトレントを解析します（v1とv2の情報を返します）。"""
        
    def generate_v2_torrent(
        self,
        source: Path,
        output: Path | None = None,
        trackers: list[str] | None = None,
        web_seeds: list[str] | None = None,
        comment: str | None = None,
        created_by: str = "ccBitTorrent",
        piece_length: int | None = None,
        private: bool = False,
    ) -> bytes:
        """v2専用トレントファイルを生成します。"""
        
    def generate_hybrid_torrent(
        self,
        source: Path,
        output: Path | None = None,
        trackers: list[str] | None = None,
        web_seeds: list[str] | None = None,
        comment: str | None = None,
        created_by: str = "ccBitTorrent",
        piece_length: int | None = None,
        private: bool = False,
    ) -> bytes:
        """ハイブリッドトレントファイルを生成します。"""
```

### TorrentV2Info

v2トレント情報のデータモデル：

```python
@dataclass
class TorrentV2Info:
    name: str
    info_hash_v2: bytes  # 32バイトのSHA-256
    info_hash_v1: bytes | None  # 20バイトのSHA-1（ハイブリッドのみ）
    announce: str
    announce_list: list[list[str]] | None
    comment: str | None
    created_by: str | None
    creation_date: int | None
    encoding: str | None
    is_private: bool
    file_tree: dict[str, FileTreeNode]
    piece_layers: dict[bytes, PieceLayer]
    piece_length: int
    files: list[FileInfo]
    total_length: int
    num_pieces: int
    
    def get_file_paths(self) -> list[str]:
        """すべてのファイルパスのリストを取得します。"""
        
    def get_piece_layer(self, pieces_root: bytes) -> PieceLayer | None:
        """ファイルのピースレイヤーを取得します。"""
```

### プロトコル関数

```python
# ハンドシェイク
def create_v2_handshake(info_hash_v2: bytes, peer_id: bytes) -> bytes
def create_hybrid_handshake(info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> bytes
def detect_protocol_version(handshake: bytes) -> ProtocolVersion
def parse_v2_handshake(data: bytes) -> dict
def negotiate_protocol_version(handshake: bytes, supported: list[ProtocolVersion]) -> ProtocolVersion | None

# 非同期I/O
async def send_v2_handshake(writer: StreamWriter, info_hash_v2: bytes, peer_id: bytes) -> None
async def send_hybrid_handshake(writer: StreamWriter, info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> None
async def handle_v2_handshake(reader: StreamReader, writer: StreamWriter, our_info_hash_v2: bytes | None = None, our_info_hash_v1: bytes | None = None, timeout: float = 30.0) -> tuple[ProtocolVersion, bytes, dict]
async def upgrade_to_v2(connection: Any, info_hash_v2: bytes) -> bool
```

### ハッシュ関数

```python
# ピースハッシュ
def hash_piece_v2(data: bytes) -> bytes
def hash_piece_v2_streaming(data_source: bytes | IO) -> bytes
def verify_piece_v2(data: bytes, expected_hash: bytes) -> bool

# Merkle trees
def hash_piece_layer(piece_hashes: list[bytes]) -> bytes
def verify_piece_layer(piece_hashes: list[bytes], expected_root: bytes) -> bool

# File trees
def hash_file_tree(file_tree: dict[str, FileTreeNode]) -> bytes
```

## 例

完全な動作例については、[docs/examples/bep52/](examples/bep52/)を参照してください：

- `create_v2_torrent.py`: ファイルからv2トレントを作成
- `create_hybrid_torrent.py`: ハイブリッドトレントを作成
- `parse_v2_torrent.py`: v2トレント情報を解析して表示
- `protocol_v2_session.py`: v2サポートでセッションを開始

## トラブルシューティング

### 一般的な問題

**問題**: v2ハンドシェイクが「Info hash v2 mismatch」で失敗
- **解決策**: info_hash_v2が正しく計算されていることを確認（bencoded info辞書のSHA-256）

**問題**: ピースレイヤー検証が失敗
- **解決策**: piece_lengthがトレントと検証の間で一致していることを確認

**問題**: ファイルツリー解析エラー
- **解決策**: ファイルツリー構造がBEP 52形式に従っていることを確認（適切なネスト、pieces_rootの長さ）

**問題**: プロトコルバージョンネゴシエーションがNoneを返す
- **解決策**: ピアがv2をサポートしていない可能性があります。ハンドシェイクの予約バイトを確認してください。

### デバッグログ

v2プロトコルのデバッグログを有効化：

```python
import logging
logging.getLogger("ccbt.core.torrent_v2").setLevel(logging.DEBUG)
logging.getLogger("ccbt.protocols.bittorrent_v2").setLevel(logging.DEBUG)
logging.getLogger("ccbt.piece.hash_v2").setLevel(logging.DEBUG)
```

## パフォーマンスの考慮事項

### メモリ使用量

- V2トレントはピースレイヤーにメモリをより多く使用（ピースあたり32バイト vs 20バイト）
- ファイルツリー構造はマルチファイルトレントにオーバーヘッドを追加
- ハイブリッドトレントはv1とv2のメタデータの両方を保存

### CPU使用量

- SHA-256はハッシュ化でSHA-1より約2倍遅い
- Merkle treeの構築は計算オーバーヘッドを追加
- 大容量ファイルにはピース長 >= 256 KiBを使用してCPU使用量を削減

### ネットワーク

- V2ハンドシェイクは12バイト大きい（80 vs 68バイト）
- ハイブリッドハンドシェイクは32バイト大きい（100 vs 68バイト）
- ピースレイヤー交換は初期オーバーヘッドを追加しますが、効率的な再開を可能にします

## 標準準拠

ccBitTorrentのBEP 52実装は公式仕様に従います：

- **BEP 52**: [BitTorrent Protocol v2](https://www.bittorrent.org/beps/bep_0052.html)
- **テストスイート**: 2500行以上の包括的なテスト
- **互換性**: libtorrent、qBittorrent、Transmissionと相互運用可能

## 関連項目

- [APIドキュメント](API.md)
- [設定ガイド](configuration.md)
- [アーキテクチャ概要](architecture.md)
- [BEPインデックス](https://www.bittorrent.org/beps/bep_0000.html)

