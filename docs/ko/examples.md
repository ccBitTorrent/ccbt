# 예제

이 섹션에서는 ccBitTorrent 사용을 위한 실용적인 예제와 코드 샘플을 제공합니다.

## 구성 예제

### 기본 구성

시작하기 위한 최소 구성 파일:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

전체 기본 구성은 [example-config-basic.toml](examples/example-config-basic.toml)을 참조하세요.

### 고급 구성

세밀한 제어가 필요한 고급 사용자용:

고급 구성 옵션은 [example-config-advanced.toml](examples/example-config-advanced.toml)을 참조하세요.

### 성능 구성

최대 성능을 위한 최적화된 설정:

성능 조정은 [example-config-performance.toml](examples/example-config-performance.toml)을 참조하세요.

### 보안 구성

암호화 및 검증이 포함된 보안 중심 구성:

보안 설정은 [example-config-security.toml](examples/example-config-security.toml)을 참조하세요.

## BEP 52 예제

### v2 토렌트 생성

BitTorrent v2 토렌트 파일 생성:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# v2 토렌트 생성
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # 16KB 조각
)
```

전체 예제는 [create_v2_torrent.py](examples/bep52/create_v2_torrent.py)를 참조하세요.

### 하이브리드 토렌트 생성

v1 및 v2 클라이언트 모두에서 작동하는 하이브리드 토렌트 생성:

전체 예제는 [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py)를 참조하세요.

### v2 토렌트 구문 분석

BitTorrent v2 토렌트 파일 구문 분석 및 검사:

전체 예제는 [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py)를 참조하세요.

### 프로토콜 v2 세션

세션에서 BitTorrent v2 프로토콜 사용:

전체 예제는 [protocol_v2_session.py](examples/bep52/protocol_v2_session.py)를 참조하세요.

## 시작하기

ccBitTorrent 시작에 대한 자세한 내용은 [시작 가이드](getting-started.md)를 참조하세요.






이 섹션에서는 ccBitTorrent 사용을 위한 실용적인 예제와 코드 샘플을 제공합니다.

## 구성 예제

### 기본 구성

시작하기 위한 최소 구성 파일:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

전체 기본 구성은 [example-config-basic.toml](examples/example-config-basic.toml)을 참조하세요.

### 고급 구성

세밀한 제어가 필요한 고급 사용자용:

고급 구성 옵션은 [example-config-advanced.toml](examples/example-config-advanced.toml)을 참조하세요.

### 성능 구성

최대 성능을 위한 최적화된 설정:

성능 조정은 [example-config-performance.toml](examples/example-config-performance.toml)을 참조하세요.

### 보안 구성

암호화 및 검증이 포함된 보안 중심 구성:

보안 설정은 [example-config-security.toml](examples/example-config-security.toml)을 참조하세요.

## BEP 52 예제

### v2 토렌트 생성

BitTorrent v2 토렌트 파일 생성:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# v2 토렌트 생성
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # 16KB 조각
)
```

전체 예제는 [create_v2_torrent.py](examples/bep52/create_v2_torrent.py)를 참조하세요.

### 하이브리드 토렌트 생성

v1 및 v2 클라이언트 모두에서 작동하는 하이브리드 토렌트 생성:

전체 예제는 [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py)를 참조하세요.

### v2 토렌트 구문 분석

BitTorrent v2 토렌트 파일 구문 분석 및 검사:

전체 예제는 [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py)를 참조하세요.

### 프로토콜 v2 세션

세션에서 BitTorrent v2 프로토콜 사용:

전체 예제는 [protocol_v2_session.py](examples/bep52/protocol_v2_session.py)를 참조하세요.

## 시작하기

ccBitTorrent 시작에 대한 자세한 내용은 [시작 가이드](getting-started.md)를 참조하세요.
































































































































































































