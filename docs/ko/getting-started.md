# 시작하기

ccBitTorrent에 오신 것을 환영합니다! 이 가이드는 고성능 BitTorrent 클라이언트를 빠르게 시작하고 실행하는 데 도움이 됩니다.

!!! tip "주요 기능: BEP XET 프로토콜 확장"
    ccBitTorrent는 **Xet 프로토콜 확장 (BEP XET)**을 포함하며, 콘텐츠 정의 청킹과 토렌트 간 중복 제거를 가능하게 합니다. 이를 통해 BitTorrent는 협업에 최적화된 초고속 업데이트 가능한 피어투피어 파일 시스템으로 변환됩니다. [BEP XET에 대해 자세히 알아보기 →](bep_xet.md)

## 설치

### 사전 요구사항

- Python 3.8 이상
- [UV](https://astral.sh/uv) 패키지 관리자 (권장)

### UV 설치

공식 설치 스크립트에서 UV 설치:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ccBitTorrent 설치

PyPI에서 설치:
```bash
uv pip install ccbittorrent
```

또는 소스에서 설치:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

진입점은 [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81)에 정의되어 있습니다.

## 주요 진입점

ccBitTorrent는 세 가지 주요 진입점을 제공합니다:

### 1. Bitonic (권장)

**Bitonic**은 메인 터미널 대시보드 인터페이스입니다. 모든 토렌트, 피어 및 시스템 메트릭의 라이브 인터랙티브 뷰를 제공합니다.

- 진입점: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- 정의 위치: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- 시작: `uv run bitonic` 또는 `uv run ccbt dashboard`

자세한 사용법은 [Bitonic 가이드](bitonic.md)를 참조하세요.

### 2. btbt CLI

**btbt**는 풍부한 기능을 갖춘 향상된 명령줄 인터페이스입니다.

- 진입점: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- 정의 위치: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- 시작: `uv run btbt`

사용 가능한 모든 명령은 [btbt CLI 참조](btbt-cli.md)를 참조하세요.

### 3. ccbt (기본 CLI)

**ccbt**는 기본 명령줄 인터페이스입니다.

- 진입점: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- 정의 위치: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- 시작: `uv run ccbt`

## 빠른 시작

### Bitonic 시작 (권장)

터미널 대시보드 시작:
```bash
uv run bitonic
```

또는 CLI를 통해:
```bash
uv run ccbt dashboard
```

사용자 정의 새로고침 속도로:
```bash
uv run ccbt dashboard --refresh 2.0
```

### 토렌트 다운로드

CLI 사용:
```bash
# 토렌트 파일에서 다운로드
uv run btbt download movie.torrent

# 마그넷 링크에서 다운로드
uv run btbt magnet "magnet:?xt=urn:btih:..."

# 속도 제한과 함께
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

모든 다운로드 옵션은 [btbt CLI 참조](btbt-cli.md)를 참조하세요.

### ccBitTorrent 구성

작업 디렉토리에 `ccbt.toml` 파일을 만듭니다. 예제 구성을 참조하세요:
- 기본 구성: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- 환경 변수: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- 구성 시스템: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

자세한 구성 옵션은 [구성 가이드](configuration.md)를 참조하세요.

## 프로젝트 보고서

프로젝트 품질 메트릭 및 보고서 보기:

- **코드 커버리지**: [reports/coverage.md](reports/coverage.md) - 포괄적인 코드 커버리지 분석
- **보안 보고서**: [reports/bandit/index.md](reports/bandit/index.md) - Bandit의 보안 스캔 결과
- **벤치마크**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - 성능 벤치마크 결과

이러한 보고서는 지속적인 통합 프로세스의 일부로 자동 생성 및 업데이트됩니다.

## 다음 단계

- [Bitonic](bitonic.md) - 터미널 대시보드 인터페이스에 대해 알아보기
- [btbt CLI](btbt-cli.md) - 전체 명령줄 인터페이스 참조
- [구성](configuration.md) - 자세한 구성 옵션
- [성능 조정](performance.md) - 최적화 가이드
- [API 참조](API.md) - 모니터링 기능을 포함한 Python API 문서

## 도움말 얻기

- 명령 도움말에는 `uv run bitonic --help` 또는 `uv run btbt --help` 사용
- 자세한 옵션은 [btbt CLI 참조](btbt-cli.md) 확인
- 문제 및 토론은 [GitHub 저장소](https://github.com/yourusername/ccbittorrent) 방문






ccBitTorrent에 오신 것을 환영합니다! 이 가이드는 고성능 BitTorrent 클라이언트를 빠르게 시작하고 실행하는 데 도움이 됩니다.

!!! tip "주요 기능: BEP XET 프로토콜 확장"
    ccBitTorrent는 **Xet 프로토콜 확장 (BEP XET)**을 포함하며, 콘텐츠 정의 청킹과 토렌트 간 중복 제거를 가능하게 합니다. 이를 통해 BitTorrent는 협업에 최적화된 초고속 업데이트 가능한 피어투피어 파일 시스템으로 변환됩니다. [BEP XET에 대해 자세히 알아보기 →](bep_xet.md)

## 설치

### 사전 요구사항

- Python 3.8 이상
- [UV](https://astral.sh/uv) 패키지 관리자 (권장)

### UV 설치

공식 설치 스크립트에서 UV 설치:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ccBitTorrent 설치

PyPI에서 설치:
```bash
uv pip install ccbittorrent
```

또는 소스에서 설치:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

진입점은 [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81)에 정의되어 있습니다.

## 주요 진입점

ccBitTorrent는 세 가지 주요 진입점을 제공합니다:

### 1. Bitonic (권장)

**Bitonic**은 메인 터미널 대시보드 인터페이스입니다. 모든 토렌트, 피어 및 시스템 메트릭의 라이브 인터랙티브 뷰를 제공합니다.

- 진입점: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- 정의 위치: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- 시작: `uv run bitonic` 또는 `uv run ccbt dashboard`

자세한 사용법은 [Bitonic 가이드](bitonic.md)를 참조하세요.

### 2. btbt CLI

**btbt**는 풍부한 기능을 갖춘 향상된 명령줄 인터페이스입니다.

- 진입점: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- 정의 위치: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- 시작: `uv run btbt`

사용 가능한 모든 명령은 [btbt CLI 참조](btbt-cli.md)를 참조하세요.

### 3. ccbt (기본 CLI)

**ccbt**는 기본 명령줄 인터페이스입니다.

- 진입점: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- 정의 위치: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- 시작: `uv run ccbt`

## 빠른 시작

### Bitonic 시작 (권장)

터미널 대시보드 시작:
```bash
uv run bitonic
```

또는 CLI를 통해:
```bash
uv run ccbt dashboard
```

사용자 정의 새로고침 속도로:
```bash
uv run ccbt dashboard --refresh 2.0
```

### 토렌트 다운로드

CLI 사용:
```bash
# 토렌트 파일에서 다운로드
uv run btbt download movie.torrent

# 마그넷 링크에서 다운로드
uv run btbt magnet "magnet:?xt=urn:btih:..."

# 속도 제한과 함께
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

모든 다운로드 옵션은 [btbt CLI 참조](btbt-cli.md)를 참조하세요.

### ccBitTorrent 구성

작업 디렉토리에 `ccbt.toml` 파일을 만듭니다. 예제 구성을 참조하세요:
- 기본 구성: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- 환경 변수: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- 구성 시스템: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

자세한 구성 옵션은 [구성 가이드](configuration.md)를 참조하세요.

## 프로젝트 보고서

프로젝트 품질 메트릭 및 보고서 보기:

- **코드 커버리지**: [reports/coverage.md](reports/coverage.md) - 포괄적인 코드 커버리지 분석
- **보안 보고서**: [reports/bandit/index.md](reports/bandit/index.md) - Bandit의 보안 스캔 결과
- **벤치마크**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - 성능 벤치마크 결과

이러한 보고서는 지속적인 통합 프로세스의 일부로 자동 생성 및 업데이트됩니다.

## 다음 단계

- [Bitonic](bitonic.md) - 터미널 대시보드 인터페이스에 대해 알아보기
- [btbt CLI](btbt-cli.md) - 전체 명령줄 인터페이스 참조
- [구성](configuration.md) - 자세한 구성 옵션
- [성능 조정](performance.md) - 최적화 가이드
- [API 참조](API.md) - 모니터링 기능을 포함한 Python API 문서

## 도움말 얻기

- 명령 도움말에는 `uv run bitonic --help` 또는 `uv run btbt --help` 사용
- 자세한 옵션은 [btbt CLI 참조](btbt-cli.md) 확인
- 문제 및 토론은 [GitHub 저장소](https://github.com/yourusername/ccbittorrent) 방문
































































































































































































