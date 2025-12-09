# BEP 52: BitTorrent Protocol v2

## 概述

BitTorrent Protocol v2 (BEP 52) 是BitTorrent协议的重大升级，引入了SHA-256哈希、改进的元数据结构以及对大文件的更好支持。ccBitTorrent为仅v2种子、仅v1种子以及可在两种协议下工作的混合种子提供完整支持。

### 主要特性

- **SHA-256哈希**: 比v1中使用的SHA-1更安全
- **Merkle Tree结构**: 高效的片段验证和部分下载
- **File Tree格式**: 分层文件组织
- **Piece Layers**: 每个文件的片段验证
- **混合种子**: 与v1客户端的向后兼容性

## 架构

### 核心组件

#### 1. 种子元数据 (`ccbt/core/torrent_v2.py`)

v2种子解析器处理所有元数据操作：

```python
from ccbt.core.torrent_v2 import TorrentV2Parser, TorrentV2Info

# 解析v2种子
parser = TorrentV2Parser()
with open("torrent_file.torrent", "rb") as f:
    torrent_data = decode(f.read())
    
v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

# 访问v2特定数据
print(f"Info Hash v2: {v2_info.info_hash_v2.hex()}")
print(f"File Tree: {v2_info.file_tree}")
print(f"Piece Layers: {len(v2_info.piece_layers)}")
```

#### 2. 协议通信 (`ccbt/protocols/bittorrent_v2.py`)

处理v2握手和消息：

```python
from ccbt.protocols.bittorrent_v2 import (
    create_v2_handshake,
    send_v2_handshake,
    handle_v2_handshake,
    PieceLayerRequest,
    PieceLayerResponse,
)

# 创建v2握手
info_hash_v2 = v2_info.info_hash_v2
peer_id = b"-CC0101-" + b"x" * 12
handshake = create_v2_handshake(info_hash_v2, peer_id)

# 发送握手
await send_v2_handshake(writer, info_hash_v2, peer_id)

# 接收握手
version, peer_id, parsed = await handle_v2_handshake(reader, writer)
```

#### 3. SHA-256哈希 (`ccbt/piece/hash_v2.py`)

实现v2哈希函数：

```python
from ccbt.piece.hash_v2 import (
    hash_piece_v2,
    hash_piece_layer,
    hash_file_tree,
    verify_piece_v2,
)

# 对片段进行哈希
piece_data = b"..." * 16384
piece_hash = hash_piece_v2(piece_data)

# 验证片段
is_valid = verify_piece_v2(piece_data, expected_hash)

# 构建Merkle tree
piece_hashes = [hash_piece_v2(p) for p in pieces]
merkle_root = hash_piece_layer(piece_hashes)
```

## 配置

### 启用协议v2

在`ccbt.toml`中配置v2协议支持：

```toml
[network.protocol_v2]
enable_protocol_v2 = true      # 启用v2支持
prefer_protocol_v2 = false     # 两者都可用时优先v2而非v1
support_hybrid = true          # 支持混合种子
v2_handshake_timeout = 30.0    # 握手超时（秒）
```

### 环境变量

```bash
export CCBT_PROTOCOL_V2_ENABLE=true
export CCBT_PROTOCOL_V2_PREFER=true
export CCBT_PROTOCOL_V2_SUPPORT_HYBRID=true
export CCBT_PROTOCOL_V2_HANDSHAKE_TIMEOUT=30.0
```

### CLI标志

```bash
# 启用v2协议
ccbt download file.torrent --protocol-v2

# 可用时优先v2
ccbt download file.torrent --protocol-v2-prefer

# 禁用v2协议
ccbt download file.torrent --no-protocol-v2
```

## 创建种子

### 仅V2种子

创建仅在v2客户端下工作的种子：

```python
from pathlib import Path
from ccbt.core.torrent_v2 import TorrentV2Parser

parser = TorrentV2Parser()

# 从单个文件创建
torrent_bytes = parser.generate_v2_torrent(
    source=Path("video.mp4"),
    output=Path("video.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=262144,  # 256 KiB
    comment="My video file",
    private=False,
)

# 从目录创建
torrent_bytes = parser.generate_v2_torrent(
    source=Path("my_files/"),
    output=Path("my_files.torrent"),
    trackers=[
        "http://tracker1.example.com/announce",
        "http://tracker2.example.com/announce",
    ],
    piece_length=None,  # 自动计算
)
```

### 混合种子

创建与v1和v2客户端兼容的种子：

```python
# 创建混合种子
torrent_bytes = parser.generate_hybrid_torrent(
    source=Path("archive.zip"),
    output=Path("archive.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=1048576,  # 1 MiB
    comment="Backwards compatible torrent",
    private=False,
)
```

### CLI种子创建

```bash
# 创建v2种子
ccbt create-torrent file.mp4 --v2 \
    --output file.torrent \
    --tracker http://tracker.example.com/announce \
    --piece-length 262144 \
    --comment "My file"

# 创建混合种子
ccbt create-torrent directory/ --hybrid \
    --output directory.torrent \
    --tracker http://tracker.example.com/announce \
    --private
```

## 协议详情

### 握手格式

#### V2握手（80字节）
```
- 1字节:  协议字符串长度（19）
- 19字节: "BitTorrent protocol"
- 8字节:  保留字节（位0 = 1表示v2支持）
- 32字节: SHA-256 info_hash_v2
- 20字节: Peer ID
```

#### 混合握手（100字节）
```
- 1字节:  协议字符串长度（19）
- 19字节: "BitTorrent protocol"
- 8字节:  保留字节（位0 = 1）
- 20字节: SHA-1 info_hash_v1
- 32字节: SHA-256 info_hash_v2
- 20字节: Peer ID
```

### 协议版本协商

ccBitTorrent自动协商最佳协议版本：

```python
from ccbt.protocols.bittorrent_v2 import (
    ProtocolVersion,
    negotiate_protocol_version,
)

# 对等节点的握手
peer_handshake = b"..."

# 我们支持的版本（按优先级顺序）
supported = [
    ProtocolVersion.HYBRID,
    ProtocolVersion.V2,
    ProtocolVersion.V1,
]

# 协商
negotiated = negotiate_protocol_version(peer_handshake, supported)

if negotiated == ProtocolVersion.V2:
    # 使用v2协议
    pass
elif negotiated == ProtocolVersion.HYBRID:
    # 使用混合模式
    pass
elif negotiated == ProtocolVersion.V1:
    # 回退到v1
    pass
else:
    # 不兼容
    pass
```

### V2特定消息

#### Piece Layer请求（消息ID 20）

请求文件的片段哈希：

```python
from ccbt.protocols.bittorrent_v2 import PieceLayerRequest

pieces_root = b"..." # 32字节SHA-256根哈希
request = PieceLayerRequest(pieces_root)
message_bytes = request.serialize()
```

#### Piece Layer响应（消息ID 21）

发送片段哈希：

```python
from ccbt.protocols.bittorrent_v2 import PieceLayerResponse

piece_hashes = [b"..." * 32 for _ in range(10)]  # SHA-256哈希列表
response = PieceLayerResponse(pieces_root, piece_hashes)
message_bytes = response.serialize()
```

#### File Tree请求（消息ID 22）

请求完整文件树：

```python
from ccbt.protocols.bittorrent_v2 import FileTreeRequest

request = FileTreeRequest()
message_bytes = request.serialize()
```

#### File Tree响应（消息ID 23）

发送文件树结构：

```python
from ccbt.protocols.bittorrent_v2 import FileTreeResponse

file_tree_bencoded = encode(file_tree_dict)
response = FileTreeResponse(file_tree_bencoded)
message_bytes = response.serialize()
```

## File Tree结构

V2种子使用分层文件树：

```python
from ccbt.core.torrent_v2 import FileTreeNode

# 单个文件
file_node = FileTreeNode(
    name="video.mp4",
    length=1000000,
    pieces_root=b"..." * 32,
    children=None,
)

# 目录结构
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

# 检查节点类型
if file_node.is_file():
    print(f"文件: {file_node.length} 字节")
if dir_node.is_directory():
    print(f"包含 {len(dir_node.children)} 个项目的目录")
```

## Piece Layers

每个文件都有自己的带有SHA-256哈希的片段层：

```python
from ccbt.core.torrent_v2 import PieceLayer

# 创建片段层
layer = PieceLayer(
    piece_length=262144,  # 256 KiB
    pieces=[
        b"..." * 32,  # 片段0的哈希
        b"..." * 32,  # 片段1的哈希
        b"..." * 32,  # 片段2的哈希
    ],
)

# 获取片段哈希
piece_0_hash = layer.get_piece_hash(0)

# 片段数量
num_pieces = layer.num_pieces()
```

## 最佳实践

### 何时使用V2

- **新种子**: 新内容始终优先使用v2
- **大文件**: V2对于> 1 GB的文件更高效
- **安全性**: SHA-256提供更好的抗碰撞性
- **面向未来**: V2是BitTorrent的未来

### 何时使用混合

- **最大兼容性**: 同时覆盖v1和v2客户端
- **过渡期**: 生态系统迁移期间
- **公共种子**: 更广泛的分布

### 何时使用仅V1

- **遗留系统**: 仅在v2支持不可用时
- **小文件**: V1的开销对于< 100 MB是可接受的

### 片段长度选择

建议自动计算，但手动值：

- **小文件（< 16 MiB）**: 16 KiB
- **中等文件（16 MiB - 512 MiB）**: 256 KiB
- **大文件（> 512 MiB）**: 1 MiB
- **非常大的文件（> 10 GiB）**: 2-4 MiB

片段长度必须是2的幂。

## API参考

### TorrentV2Parser

v2种子操作的主类：

```python
class TorrentV2Parser:
    def parse_v2(self, info_dict: dict, torrent_data: dict) -> TorrentV2Info:
        """解析v2种子信息字典。"""
        
    def parse_hybrid(self, info_dict: dict, torrent_data: dict) -> tuple[TorrentInfo, TorrentV2Info]:
        """解析混合种子（返回v1和v2信息）。"""
        
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
        """生成仅v2种子文件。"""
        
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
        """生成混合种子文件。"""
```

### TorrentV2Info

v2种子信息的数据模型：

```python
@dataclass
class TorrentV2Info:
    name: str
    info_hash_v2: bytes  # 32字节SHA-256
    info_hash_v1: bytes | None  # 20字节SHA-1（仅混合）
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
        """获取所有文件路径的列表。"""
        
    def get_piece_layer(self, pieces_root: bytes) -> PieceLayer | None:
        """获取文件的片段层。"""
```

### 协议函数

```python
# 握手
def create_v2_handshake(info_hash_v2: bytes, peer_id: bytes) -> bytes
def create_hybrid_handshake(info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> bytes
def detect_protocol_version(handshake: bytes) -> ProtocolVersion
def parse_v2_handshake(data: bytes) -> dict
def negotiate_protocol_version(handshake: bytes, supported: list[ProtocolVersion]) -> ProtocolVersion | None

# 异步I/O
async def send_v2_handshake(writer: StreamWriter, info_hash_v2: bytes, peer_id: bytes) -> None
async def send_hybrid_handshake(writer: StreamWriter, info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> None
async def handle_v2_handshake(reader: StreamReader, writer: StreamWriter, our_info_hash_v2: bytes | None = None, our_info_hash_v1: bytes | None = None, timeout: float = 30.0) -> tuple[ProtocolVersion, bytes, dict]
async def upgrade_to_v2(connection: Any, info_hash_v2: bytes) -> bool
```

### 哈希函数

```python
# 片段哈希
def hash_piece_v2(data: bytes) -> bytes
def hash_piece_v2_streaming(data_source: bytes | IO) -> bytes
def verify_piece_v2(data: bytes, expected_hash: bytes) -> bool

# Merkle trees
def hash_piece_layer(piece_hashes: list[bytes]) -> bytes
def verify_piece_layer(piece_hashes: list[bytes], expected_root: bytes) -> bool

# File trees
def hash_file_tree(file_tree: dict[str, FileTreeNode]) -> bytes
```

## 示例

有关完整的工作示例，请参阅[docs/examples/bep52/](examples/bep52/)：

- `create_v2_torrent.py`: 从文件创建v2种子
- `create_hybrid_torrent.py`: 创建混合种子
- `parse_v2_torrent.py`: 解析并显示v2种子信息
- `protocol_v2_session.py`: 使用v2支持启动会话

## 故障排除

### 常见问题

**问题**: v2握手失败，显示"Info hash v2 mismatch"
- **解决方案**: 验证info_hash_v2是否正确计算（bencoded info字典的SHA-256）

**问题**: 片段层验证失败
- **解决方案**: 确保piece_length在种子和验证之间匹配

**问题**: 文件树解析错误
- **解决方案**: 检查文件树结构是否遵循BEP 52格式（适当的嵌套、pieces_root长度）

**问题**: 协议版本协商返回None
- **解决方案**: 对等节点可能不支持v2。检查握手中的保留字节。

### 调试日志

启用v2协议的调试日志：

```python
import logging
logging.getLogger("ccbt.core.torrent_v2").setLevel(logging.DEBUG)
logging.getLogger("ccbt.protocols.bittorrent_v2").setLevel(logging.DEBUG)
logging.getLogger("ccbt.piece.hash_v2").setLevel(logging.DEBUG)
```

## 性能考虑

### 内存使用

- V2种子为片段层使用更多内存（每个片段32字节 vs 20字节）
- 文件树结构为多文件种子增加开销
- 混合种子存储v1和v2元数据

### CPU使用

- SHA-256在哈希方面比SHA-1慢约2倍
- Merkle tree构建增加计算开销
- 对于大文件使用片段长度 >= 256 KiB以减少CPU使用

### 网络

- V2握手大12字节（80 vs 68字节）
- 混合握手大32字节（100 vs 68字节）
- 片段层交换增加初始开销，但可实现高效恢复

## 标准合规性

ccBitTorrent的BEP 52实现遵循官方规范：

- **BEP 52**: [BitTorrent Protocol v2](https://www.bittorrent.org/beps/bep_0052.html)
- **测试套件**: 2500多行全面测试
- **兼容性**: 与libtorrent、qBittorrent、Transmission互操作

## 另请参阅

- [API文档](API.md)
- [配置指南](configuration.md)
- [架构概述](architecture.md)
- [BEP索引](https://www.bittorrent.org/beps/bep_0000.html)

