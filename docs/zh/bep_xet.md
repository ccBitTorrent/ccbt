# BEP XET: 用于内容定义分块和去重的Xet协议扩展

## 概述

Xet协议扩展（BEP XET）是一个BitTorrent协议扩展，通过点对点内容可寻址存储（CAS）系统实现内容定义分块（CDC）和跨种子去重。此扩展将BitTorrent转换为超快速、可更新的点对点文件系统，优化协作和高效数据共享。

## 理由

Xet协议扩展解决了传统BitTorrent的关键限制：

1. **固定片段大小**：传统BitTorrent使用固定片段大小，导致文件修改时重新分发效率低下。CDC适应内容边界。

2. **无跨种子去重**：每个种子都是独立的，即使共享相同内容。Xet实现跨种子的块级去重。

3. **集中式存储**：传统CAS系统需要外部服务。Xet使用DHT和跟踪器直接在BitTorrent网络中构建CAS。

4. **低效更新**：更新共享文件需要重新分发整个文件。Xet仅重新分发更改的块。

通过结合CDC、去重和P2P CAS，Xet将BitTorrent转换为超快速、可更新的点对点文件系统，优化协作。

### 主要特性

- **内容定义分块（CDC）**：基于Gearhash的智能文件分割（8KB-128KB块）
- **跨种子去重**：跨多个种子的块级去重
- **点对点CAS**：使用DHT和跟踪器的分散式内容可寻址存储
- **Merkle Tree验证**：用于完整性的BLAKE3-256哈希，带SHA-256回退
- **Xorb格式**：用于分组多个块的高效存储格式
- **Shard格式**：用于文件信息和CAS数据的元数据存储
- **LZ4压缩**：Xorb数据的可选压缩

## 用例

### 1. 协作文件共享

Xet通过以下方式实现高效协作：
- **去重**：跨多个种子共享的文件共享相同的块
- **快速更新**：只需重新分发更改的块
- **版本控制**：通过Merkle tree根跟踪文件版本

### 2. 大文件分发

对于大文件或数据集：
- **内容定义分块**：智能边界减少编辑时的块重新分发
- **并行下载**：同时从多个对等节点下载块
- **恢复能力**：跟踪单个块以实现可靠的恢复

### 3. 点对点文件系统

将BitTorrent转换为P2P文件系统：
- **CAS集成**：块存储在DHT中，实现全局可用性
- **元数据存储**：Shard提供文件系统元数据
- **快速查找**：通过哈希直接访问块，无需完整种子下载

## 实现状态

Xet协议扩展已在ccBitTorrent中完全实现：

- ✅ 内容定义分块（Gearhash CDC）
- ✅ BLAKE3-256哈希，带SHA-256回退
- ✅ SQLite去重缓存
- ✅ DHT集成（BEP 44）
- ✅ 跟踪器集成
- ✅ Xorb和Shard格式
- ✅ Merkle tree计算
- ✅ BitTorrent协议扩展（BEP 10）
- ✅ CLI集成
- ✅ 配置管理

## 配置

### CLI命令

```bash
# 启用Xet协议
ccbt xet enable

# 显示Xet状态
ccbt xet status

# 显示去重统计
ccbt xet stats

# 清理未使用的块
ccbt xet cleanup --max-age-days 30
```

### 启用Xet协议

在`ccbt.toml`中配置Xet支持：

```toml
[disk]
# Xet协议配置
xet_enabled = false                        # 启用Xet协议
xet_chunk_min_size = 8192                  # 最小块大小（字节）
xet_chunk_max_size = 131072                # 最大块大小（字节）
xet_chunk_target_size = 16384              # 目标块大小（字节）
xet_deduplication_enabled = true           # 启用块级去重
xet_cache_db_path = "data/xet_cache.db"    # SQLite缓存数据库路径
xet_chunk_store_path = "data/xet_chunks"   # 块存储目录
xet_use_p2p_cas = true                     # 使用P2P内容可寻址存储
xet_compression_enabled = true             # 启用Xorb数据的LZ4压缩
```


## 协议规范

### 扩展协商

XET扩展遵循BEP 10（Extension Protocol）进行协商。在扩展握手期间，对等节点交换扩展功能：

- **扩展名称**：`ut_xet`
- **扩展ID**：在握手期间动态分配（1-255）
- **必需功能**：无（扩展是可选的）

支持XET的对等节点在其扩展握手中包含`ut_xet`。扩展ID按对等节点会话存储，用于消息路由。

### 消息类型

XET扩展定义以下消息类型：

#### 块消息

1. **CHUNK_REQUEST (0x01)**：通过哈希请求特定块
2. **CHUNK_RESPONSE (0x02)**：包含块数据的响应
3. **CHUNK_NOT_FOUND (0x03)**：对等节点没有请求的块
4. **CHUNK_ERROR (0x04)**：检索块时发生错误

#### 文件夹同步消息

5. **FOLDER_VERSION_REQUEST (0x10)**：请求文件夹版本（git提交引用）
6. **FOLDER_VERSION_RESPONSE (0x11)**：包含文件夹版本的响应
7. **FOLDER_UPDATE_NOTIFY (0x12)**：通知对等节点文件夹更新
8. **FOLDER_SYNC_MODE_REQUEST (0x13)**：请求同步模式
9. **FOLDER_SYNC_MODE_RESPONSE (0x14)**：包含同步模式的响应

#### 元数据交换消息

10. **FOLDER_METADATA_REQUEST (0x20)**：请求文件夹元数据（.tonic文件）
11. **FOLDER_METADATA_RESPONSE (0x21)**：包含文件夹元数据片段的响应
12. **FOLDER_METADATA_NOT_FOUND (0x22)**：元数据不可用

#### 布隆过滤器消息

13. **BLOOM_FILTER_REQUEST (0x30)**：请求对等节点的布隆过滤器以获取块可用性
14. **BLOOM_FILTER_RESPONSE (0x31)**：包含布隆过滤器数据的响应

### 消息格式

#### CHUNK_REQUEST

```
偏移量  大小  说明
0       32    块哈希（BLAKE3-256或SHA-256）
```

#### CHUNK_RESPONSE

```
偏移量  大小  说明
0       32    块哈希
32      4     块数据长度（大端序）
36      N     块数据
```

#### CHUNK_NOT_FOUND

```
偏移量  大小  说明
0       32    块哈希
```

#### CHUNK_ERROR

```
偏移量  大小  说明
0       32    块哈希
32      4     错误代码（大端序）
36      N     错误消息（UTF-8）
```

#### FOLDER_VERSION_REQUEST

```
偏移量  大小  说明
0       N     文件夹标识符（UTF-8，以null结尾）
```

#### FOLDER_VERSION_RESPONSE

```
偏移量  大小  说明
0       N     文件夹标识符（UTF-8，以null结尾）
N       40    Git提交引用（SHA-1，20字节）或（SHA-256，32字节）
```

#### FOLDER_UPDATE_NOTIFY

```
偏移量  大小  说明
0       N     文件夹标识符（UTF-8，以null结尾）
N       40    新的git提交引用
N+40    8     时间戳（大端序，Unix纪元）
```

#### FOLDER_SYNC_MODE_REQUEST

```
偏移量  大小  说明
0       N     文件夹标识符（UTF-8，以null结尾）
```

#### FOLDER_SYNC_MODE_RESPONSE

```
偏移量  大小  说明
0       N     文件夹标识符（UTF-8，以null结尾）
N       1     同步模式（0=DESIGNATED，1=BEST_EFFORT，2=BROADCAST，3=CONSENSUS）
```

#### FOLDER_METADATA_REQUEST

```
偏移量  大小  说明
0       N     文件夹标识符（UTF-8，以null结尾）
N       4     片段索引（大端序，基于0）
```

#### FOLDER_METADATA_RESPONSE

```
偏移量  大小  说明
0       N     文件夹标识符（UTF-8，以null结尾）
N       4     片段索引（大端序）
N+4     4     总片段数（大端序）
N+8     4     片段大小（大端序）
N+12    M     片段数据（bencoded .tonic文件片段）
```

#### BLOOM_FILTER_REQUEST

```
偏移量  大小  说明
0       4     过滤器大小（字节，大端序）
```

#### BLOOM_FILTER_RESPONSE

```
偏移量  大小  说明
0       4     过滤器大小（字节，大端序）
4       4     哈希计数（大端序）
8       N     布隆过滤器数据（位数组）
```

### 块发现

块通过多种机制发现：

1. **DHT（BEP 44）**：使用DHT存储和检索块元数据。块哈希（32字节）用作DHT键。元数据格式：`{"type": "xet_chunk", "available": True, "ed25519_public_key": "...", "ed25519_signature": "..."}`

2. **跟踪器**：向跟踪器宣布块可用性。块哈希的前20字节用作跟踪器公告的info_hash。

3. **对等节点交换（PEX）**：扩展PEX（BEP 11），带块可用性消息。`CHUNKS_ADDED`和`CHUNKS_DROPPED`消息类型交换块哈希列表。

4. **布隆过滤器**：预过滤块可用性查询。对等节点交换包含其可用块的布隆过滤器，以减少网络开销。

5. **块目录**：将块哈希映射到对等节点信息的内存或持久索引。支持多个块的快速批量查询。

6. **本地对等节点发现（BEP 14）**：用于本地网络对等节点发现的UDP多播。XET特定的多播地址和端口可配置。

7. **多播广播**：用于本地网络上块公告的UDP多播。

8. **Gossip协议**：用于分散式更新传播的流行病式协议，具有可配置的扇出和间隔。

9. **受控泛洪**：用于紧急更新的基于TTL的泛洪机制，带优先级阈值。

10. **种子元数据**：从种子XET元数据或BitTorrent v2片段层提取块哈希。

### 文件夹同步

XET支持多种同步模式的文件夹同步：

#### 同步模式

- **DESIGNATED (0)**：单一真相来源。一个对等节点被指定为源，其他对等节点从中同步。基于运行时间和块可用性的自动源对等节点选举。

- **BEST_EFFORT (1)**：所有节点贡献更新，尽力而为。通过last-write-wins、version-vector、3-way-merge或时间戳策略解决冲突。

- **BROADCAST (2)**：特定节点使用队列广播更新。使用gossip协议或受控泛洪进行传播。

- **CONSENSUS (3)**：更新需要大多数节点的同意。支持简单多数、Raft共识或拜占庭容错（BFT）。

#### 冲突解决

在BEST_EFFORT模式下检测到冲突时，以下策略可用：

- **last-write-wins**：最近的修改时间戳获胜
- **version-vector**：基于向量时钟的冲突检测和解决
- **3-way-merge**：用于自动冲突解决的三路合并算法
- **timestamp**：基于时间戳的解决，带可配置的时间窗口

#### Git集成

通过git提交引用（SHA-1或SHA-256）跟踪文件夹版本。通过`git diff`检测更改。如果`git_auto_commit=True`，则启用自动提交。Git存储库必须在文件夹根目录中初始化。

#### 允许列表

使用Ed25519进行签名和AES-256-GCM进行存储的加密允许列表。在对等节点握手期间验证。支持人类可读的对等节点名称别名。允许列表哈希在扩展握手期间交换。

### .tonic文件格式

`.tonic`文件格式（类似于`.torrent`）包含XET特定的元数据：

```
dictionary {
    "xet": dictionary {
        "version": integer,           # 格式版本（1）
        "sync_mode": integer,        # 0=DESIGNATED，1=BEST_EFFORT，2=BROADCAST，3=CONSENSUS
        "git_ref": string,           # Git提交引用（SHA-1或SHA-256）
        "allowlist_hash": string,    # 允许列表的SHA-256哈希
        "file_tree": dictionary {    # 嵌套目录结构
            "path": dictionary {
                "": dictionary {     # 空键 = 文件元数据
                    "hash": string,   # 文件哈希
                    "size": integer   # 文件大小
                }
            }
        },
        "files": list [              # 平面文件列表
            dictionary {
                "path": string,
                "hash": string,
                "size": integer
            }
        ],
        "chunk_hashes": list [       # 块哈希列表（每个32字节）
            string
        ]
    }
}
```

### NAT端口映射

XET需要UDP端口映射以实现适当的NAT遍历：

- **XET协议端口**：通过`xet_port`可配置（默认为`listen_port_udp`）。如果`map_xet_port=True`，则通过UPnP/NAT-PMP映射。

- **XET多播端口**：通过`xet_multicast_port`可配置。如果`map_xet_multicast_port=True`则映射（多播通常不需要）。

外部端口信息传播到跟踪器以实现适当的对等节点发现。`NATManager.get_external_port()`支持UDP协议用于XET端口查询。


## 架构

### 核心组件

#### 1. 协议扩展（`ccbt/extensions/xet.py`）

Xet扩展实现BEP 10（Extension Protocol）消息，用于块请求和响应。

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

**消息类型：**

```23:29:ccbt/extensions/xet.py
class XetMessageType(IntEnum):
    """Xet Extension message types."""

    CHUNK_REQUEST = 0x01  # Request chunk by hash
    CHUNK_RESPONSE = 0x02  # Response with chunk data
    CHUNK_NOT_FOUND = 0x03  # Chunk not available
    CHUNK_ERROR = 0x04  # Error retrieving chunk
```

**关键方法：**
- `encode_chunk_request()`: [ccbt/extensions/xet.py:89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L89) - 使用请求ID编码块请求消息
- `decode_chunk_request()`: [ccbt/extensions/xet.py:108](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L108) - 解码块请求消息
- `encode_chunk_response()`: [ccbt/extensions/xet.py:136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L136) - 使用数据编码块响应
- `handle_chunk_request()`: [ccbt/extensions/xet.py:210](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L210) - 处理来自对等节点的传入块请求
- `handle_chunk_response()`: [ccbt/extensions/xet.py:284](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L284) - 处理来自对等节点的块响应

**扩展握手：**
- `encode_handshake()`: [ccbt/extensions/xet.py:61](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L61) - 编码Xet扩展功能
- `decode_handshake()`: [ccbt/extensions/xet.py:75](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/extensions/xet.py#L75) - 解码对等节点的Xet扩展功能

#### 2. 内容定义分块（`ccbt/storage/xet_chunking.py`）

基于内容模式的Gearhash CDC算法，用于智能文件分割，具有可变大小的块。

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

**常量：**
- `MIN_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:21](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L21) - 最小块大小8 KB
- `MAX_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L22) - 最大块大小128 KB
- `TARGET_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:23](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L23) - 默认目标块大小16 KB
- `WINDOW_SIZE`: [ccbt/storage/xet_chunking.py:24](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L24) - 滚动哈希窗口48字节

**关键方法：**
- `chunk_buffer()`: [ccbt/storage/xet_chunking.py:210](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L210) - 使用Gearhash CDC算法对数据进行分块
- `_find_chunk_boundary()`: [ccbt/storage/xet_chunking.py:242](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L242) - 使用滚动哈希查找内容定义的块边界
- `_init_gear_table()`: [ccbt/storage/xet_chunking.py:54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_chunking.py#L54) - 初始化用于滚动哈希的预计算gear表

**算法：**
Gearhash算法使用带有预计算的256元素gear表的滚动哈希来查找内容定义的边界。这确保不同文件中的相似内容产生相同的块边界，实现跨文件去重。

#### 3. 去重缓存（`ccbt/storage/xet_deduplication.py`）

基于SQLite的本地去重缓存，带DHT集成，用于块级去重。

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

**数据库模式：**
- `chunks`表: [ccbt/storage/xet_deduplication.py:65](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L65) - 存储块哈希、大小、存储路径、引用计数、时间戳
- 索引: [ccbt/storage/xet_deduplication.py:75](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L75) - 在size和last_accessed上，用于高效查询

**关键方法：**
- `check_chunk_exists()`: [ccbt/storage/xet_deduplication.py:85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L85) - 检查块是否在本地存在并更新访问时间
- `store_chunk()`: [ccbt/storage/xet_deduplication.py:112](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L112) - 使用去重存储块（如果存在则增加ref_count）
- `get_chunk_path()`: [ccbt/storage/xet_deduplication.py:165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L165) - 获取块的本地存储路径
- `cleanup_unused_chunks()`: [ccbt/storage/xet_deduplication.py:201](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_deduplication.py#L201) - 删除在max_age_days内未访问的块

**功能：**
- 引用计数：跟踪有多少种子/文件引用每个块
- 自动清理：基于访问时间删除未使用的块
- 物理存储：块存储在`xet_chunks/`目录中，哈希作为文件名

#### 4. 点对点CAS（`ccbt/discovery/xet_cas.py`）

基于DHT和跟踪器的块发现和交换，用于分散式内容可寻址存储。

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

**关键方法：**
- `announce_chunk()`: [ccbt/discovery/xet_cas.py:50](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L50) - 向DHT（BEP 44）和跟踪器宣布块可用性
- `find_chunk_peers()`: [ccbt/discovery/xet_cas.py:112](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L112) - 通过DHT和跟踪器查询查找具有特定块的对等节点
- `request_chunk_from_peer()`: [ccbt/discovery/xet_cas.py:200](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L200) - 使用Xet扩展协议从特定对等节点请求块

**DHT集成：**
- 使用BEP 44（Distributed Hash Table for Mutable Items）存储块元数据
- 块元数据格式: [ccbt/discovery/xet_cas.py:68](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/discovery/xet_cas.py#L68) - `{"type": "xet_chunk", "available": True}`
- 支持多种DHT方法：`store()`、`store_chunk_hash()`、`get_chunk_peers()`、`get_peers()`、`find_value()`

**跟踪器集成：**
- 使用块哈希的前20字节作为info_hash向跟踪器宣布块
- 实现基于跟踪器的块对等节点发现

## 存储格式

### Xorb格式

Xorb将多个块分组，以实现高效的存储和检索。

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

**格式规范：**
- 标头: [ccbt/storage/xet_xorb.py:123](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L123) - 16字节（magic `0x24687531`，版本，标志，保留）
- 块计数: [ccbt/storage/xet_xorb.py:149](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L149) - 4字节（uint32，小端序）
- 块条目: [ccbt/storage/xet_xorb.py:140](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L140) - 可变（每个块的哈希、大小、数据）
- 元数据: [ccbt/storage/xet_xorb.py:119](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L119) - 8字节（总未压缩大小作为uint64）

**常量：**
- `MAX_XORB_SIZE`: [ccbt/storage/xet_xorb.py:35](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L35) - 最大xorb大小64 MiB
- `XORB_MAGIC_INT`: [ccbt/storage/xet_xorb.py:36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L36) - 魔数`0x24687531`
- `FLAG_COMPRESSED`: [ccbt/storage/xet_xorb.py:42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L42) - LZ4压缩标志

**关键方法：**
- `add_chunk()`: [ccbt/storage/xet_xorb.py:62](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L62) - 将块添加到xorb（如果超过MAX_XORB_SIZE则失败）
- `serialize()`: [ccbt/storage/xet_xorb.py:84](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L84) - 使用可选的LZ4压缩将xorb序列化为二进制格式
- `deserialize()`: [ccbt/storage/xet_xorb.py:200](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L200) - 从二进制格式反序列化xorb，带自动解压缩

**压缩：**
- 可选LZ4压缩: [ccbt/storage/xet_xorb.py:132](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L132) - 如果`compress=True`且LZ4可用，则压缩块数据
- 自动检测: [ccbt/storage/xet_xorb.py:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_xorb.py#L22) - 如果未安装LZ4，则优雅回退

### Shard格式

Shard存储文件元数据和CAS信息，以实现高效的文件系统操作。

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

**格式规范：**
- 标头: [ccbt/storage/xet_shard.py:142](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L142) - 24字节（magic `"SHAR"`，版本，标志，文件/xorb/块计数）
- 文件信息部分: [ccbt/storage/xet_shard.py:145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L145) - 可变（每个文件的路径、哈希、大小、xorb引用）
- CAS信息部分: [ccbt/storage/xet_shard.py:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L148) - 可变（xorb哈希、块哈希）
- HMAC页脚: [ccbt/storage/xet_shard.py:150](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L150) - 32字节（如果提供密钥则为HMAC-SHA256）

**常量：**
- `SHARD_MAGIC`: [ccbt/storage/xet_shard.py:19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L19) - 魔数字节`b"SHAR"`
- `SHARD_VERSION`: [ccbt/storage/xet_shard.py:20](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L20) - 格式版本1
- `HMAC_SIZE`: [ccbt/storage/xet_shard.py:22](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L22) - HMAC-SHA256的32字节

**关键方法：**
- `add_file_info()`: [ccbt/storage/xet_shard.py:47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L47) - 添加带xorb引用的文件元数据
- `add_chunk_hash()`: [ccbt/storage/xet_shard.py:80](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L80) - 将块哈希添加到shard
- `add_xorb_hash()`: [ccbt/storage/xet_shard.py:93](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L93) - 将xorb哈希添加到shard
- `serialize()`: [ccbt/storage/xet_shard.py:106](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L106) - 使用可选的HMAC将shard序列化为二进制格式
- `deserialize()`: [ccbt/storage/xet_shard.py:201](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L201) - 从二进制格式反序列化shard，带HMAC验证

**完整性：**
- HMAC验证: [ccbt/storage/xet_shard.py:170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_shard.py#L170) - 用于shard完整性的可选HMAC-SHA256

## Merkle Tree计算

文件使用从块哈希构建的Merkle tree进行验证，以实现高效的完整性验证。

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

**哈希函数：**
- `compute_chunk_hash()`: [ccbt/storage/xet_hashing.py:43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L43) - 计算块的BLAKE3-256哈希（回退到SHA-256）
- `compute_xorb_hash()`: [ccbt/storage/xet_hashing.py:63](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L63) - 计算xorb数据的哈希
- `verify_chunk_hash()`: [ccbt/storage/xet_hashing.py:158](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L158) - 根据预期哈希验证块数据

**Merkle Tree构建：**
- `build_merkle_tree()`: [ccbt/storage/xet_hashing.py:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L78) - 从块数据构建Merkle tree（首先对块进行哈希）
- `build_merkle_tree_from_hashes()`: [ccbt/storage/xet_hashing.py:115](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L115) - 从预计算的块哈希构建Merkle tree

**算法：**
Merkle tree通过在每个级别配对哈希自下而上构建：
1. 从块哈希（叶节点）开始
2. 配对相邻哈希并对组合进行哈希
3. 重复直到只剩下单个根哈希
4. 奇数：复制最后一个哈希用于配对

**增量哈希：**
- `hash_file_incremental()`: [ccbt/storage/xet_hashing.py:175](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L175) - 增量计算文件哈希以提高内存效率

**哈希大小：**
- `HASH_SIZE`: [ccbt/storage/xet_hashing.py:40](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L40) - BLAKE3-256或SHA-256的32字节

**BLAKE3支持：**
- 自动检测: [ccbt/storage/xet_hashing.py:21](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/storage/xet_hashing.py#L21) - 如果可用则使用BLAKE3，否则回退到SHA-256
- 性能：BLAKE3为大文件提供更好的性能

## 参考文献

- [BEP 10: Extension Protocol](https://www.bittorrent.org/beps/bep_0010.html)
- [BEP 44: Distributed Hash Table for Mutable Items](https://www.bittorrent.org/beps/bep_0044.html)
- [BEP 52: BitTorrent Protocol v2](https://www.bittorrent.org/beps/bep_0052.html)
- [Gearhash Algorithm](https://github.com/xetdata/xet-core)

