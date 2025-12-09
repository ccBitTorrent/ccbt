# 구성 가이드

ccBitTorrent는 TOML 지원, 검증, 핫 리로드 및 여러 소스에서의 계층적 로딩을 갖춘 포괄적인 구성 시스템을 사용합니다.

구성 시스템: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## 구성 소스 및 우선순위

구성은 다음 순서로 로드됩니다 (나중 소스가 이전 소스를 덮어씁니다):

1. **기본값**: [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)의 내장된 합리적인 기본값
2. **구성 파일**: 현재 디렉토리 또는 `~/.config/ccbt/ccbt.toml`의 `ccbt.toml`. 참조: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **환경 변수**: `CCBT_*` 접두사 변수. 참조: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI 인수**: 명령줄 재정의. 참조: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **토렌트별**: 개별 토렌트 설정 (향후 기능)

구성 로딩: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## 구성 파일

### 기본 구성

기본 구성 파일 참조: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

구성은 섹션별로 구성됩니다:

### 네트워크 구성

네트워크 설정: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- 연결 제한: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- 요청 파이프라인: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- 소켓 조정: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- 타임아웃: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- 수신 설정: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- 전송 프로토콜: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- 속도 제한: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- 조절 전략: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- 트래커 설정: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

네트워크 구성 모델: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 디스크 구성

디스크 설정: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- 사전 할당: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- 쓰기 최적화: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- 해시 검증: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O 스레딩: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- 고급 설정: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- 스토리지 서비스 설정: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: 스토리지 서비스의 최대 파일 크기 제한 (MB) (0 또는 None = 무제한, 최대 1048576 = 1TB). 테스트 중 무제한 디스크 쓰기를 방지하며 프로덕션 사용을 위해 구성할 수 있습니다.
- 체크포인트 설정: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

디스크 구성 모델: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 전략 구성

전략 설정: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- 조각 선택: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- 고급 전략: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- 조각 우선순위: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

전략 구성 모델: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 발견 구성

발견 설정: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT 설정: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX 설정: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- 트래커 설정: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: 트래커 알림 간격 (초) (기본값: 1800.0, 범위: 60.0-86400.0)
  - `tracker_scrape_interval`: 주기적 스크래핑을 위한 트래커 스크래프 간격 (초) (기본값: 3600.0, 범위: 60.0-86400.0)
  - `tracker_auto_scrape`: 토렌트가 추가될 때 트래커를 자동으로 스크래프 (BEP 48) (기본값: false)
  - 환경 변수: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

발견 구성 모델: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 제한 구성

속도 제한: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- 전역 제한: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- 토렌트별 제한: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- 피어별 제한: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- 스케줄러 설정: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

제한 구성 모델: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 관찰 가능성 구성

관찰 가능성 설정: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- 로깅: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- 메트릭: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- 추적 및 경고: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

관찰 가능성 구성 모델: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 보안 구성

보안 설정: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

보안 구성 모델: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### 암호화 구성

ccBitTorrent는 안전한 피어 연결을 위해 BEP 3 Message Stream Encryption (MSE) 및 Protocol Encryption (PE)을 지원합니다.

**암호화 설정:**

- `enable_encryption` (bool, 기본값: `false`): 프로토콜 암호화 지원 활성화
- `encryption_mode` (str, 기본값: `"preferred"`): 암호화 모드
  - `"disabled"`: 암호화 없음 (일반 연결만)
  - `"preferred"`: 암호화 시도, 사용 불가능한 경우 일반으로 폴백
  - `"required"`: 암호화 필수, 암호화를 사용할 수 없으면 연결 실패
- `encryption_dh_key_size` (int, 기본값: `768`): Diffie-Hellman 키 크기 (비트) (768 또는 1024)
- `encryption_prefer_rc4` (bool, 기본값: `true`): 이전 클라이언트와의 호환성을 위해 RC4 암호 우선
- `encryption_allowed_ciphers` (list[str], 기본값: `["rc4", "aes"]`): 허용된 암호 유형
  - `"rc4"`: RC4 스트림 암호 (가장 호환성 높음)
  - `"aes"`: CFB 모드의 AES 암호 (더 안전함)
  - `"chacha20"`: ChaCha20 암호 (아직 구현되지 않음)
- `encryption_allow_plain_fallback` (bool, 기본값: `true`): 암호화가 실패한 경우 일반 연결로 폴백 허용 (`encryption_mode`가 `"preferred"`인 경우에만 적용)

**환경 변수:**

- `CCBT_ENABLE_ENCRYPTION`: 암호화 활성화/비활성화 (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: 암호화 모드 (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DH 키 크기 (`768` 또는 `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: RC4 우선 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: 쉼표로 구분된 목록 (예: `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: 일반 폴백 허용 (`true`/`false`)

**구성 예:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**보안 고려사항:**

1. **RC4 호환성**: RC4는 호환성을 위해 지원되지만 암호학적으로 약합니다. 가능한 경우 더 나은 보안을 위해 AES를 사용하세요.
2. **DH 키 크기**: 768비트 DH 키는 대부분의 사용 사례에 적절한 보안을 제공합니다. 1024비트는 더 강력한 보안을 제공하지만 핸드셰이크 지연 시간을 증가시킵니다.
3. **암호화 모드**:
   - `preferred`: 호환성에 최적 - 암호화를 시도하지만 우아하게 폴백합니다
   - `required`: 가장 안전하지만 암호화를 지원하지 않는 피어와의 연결에 실패할 수 있습니다
4. **성능 영향**: 암호화는 최소한의 오버헤드를 추가합니다 (RC4의 경우 약 1-5%, AES의 경우 약 2-8%) 하지만 개인 정보 보호를 향상시키고 트래픽 셰이핑을 피하는 데 도움이 됩니다.

**구현 세부사항:**

암호화 구현: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE 핸드셰이크: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- 암호 스위트: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman 교환: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML 구성

머신 러닝 설정: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML 구성 모델: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 대시보드 구성

대시보드 설정: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

대시보드 구성 모델: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## 환경 변수

환경 변수는 `CCBT_` 접두사를 사용하며 계층적 명명 체계를 따릅니다.

참조: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

형식: `CCBT_<SECTION>_<OPTION>=<value>`

예:
- 네트워크: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- 디스크: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- 전략: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- 발견: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- 관찰 가능성: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- 제한: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- 보안: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

환경 변수 구문 분석: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## 구성 스키마

구성 스키마 및 검증: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

스키마는 다음을 정의합니다:
- 필드 유형 및 제약 조건
- 기본값
- 검증 규칙
- 문서

## 구성 기능

구성 기능 및 기능 감지: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## 구성 템플릿

사전 정의된 구성 템플릿: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

템플릿:
- 고성능 설정
- 낮은 리소스 설정
- 보안 중심 설정
- 개발 설정

## 구성 예

구성 예제는 [examples/](examples/) 디렉토리에서 사용할 수 있습니다:

- 기본 구성: [example-config-basic.toml](examples/example-config-basic.toml)
- 고급 구성: [example-config-advanced.toml](examples/example-config-advanced.toml)
- 성능 구성: [example-config-performance.toml](examples/example-config-performance.toml)
- 보안 구성: [example-config-security.toml](examples/example-config-security.toml)

## 핫 리로드

구성 핫 리로드 지원: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

구성 시스템은 클라이언트를 다시 시작하지 않고 변경 사항을 리로드하는 것을 지원합니다.

## 구성 마이그레이션

구성 마이그레이션 유틸리티: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

구성 버전 간 마이그레이션 도구.

## 구성 백업 및 차이

구성 관리 유틸리티:
- 백업: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- 차이: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## 조건부 구성

조건부 구성 지원: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## 팁 및 모범 사례

### 성능 조정

- 큰 순차 쓰기의 경우 `disk.write_buffer_kib` 증가: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Linux/NVMe에서 `direct_io` 활성화하여 쓰기 처리량 향상: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- 네트워크에 맞게 `network.pipeline_depth` 및 `network.block_size_kib` 조정: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### 리소스 최적화

- CPU 코어 수에 따라 `disk.hash_workers` 조정: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- 사용 가능한 RAM에 따라 `disk.cache_size_mb` 구성: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- 대역폭에 따라 `network.max_global_peers` 설정: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### 네트워크 구성

- 네트워크 조건에 따라 타임아웃 구성: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- 필요에 따라 프로토콜 활성화/비활성화: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- 적절하게 속도 제한 설정: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

자세한 성능 조정은 [성능 조정 가이드](performance.md)를 참조하세요.






ccBitTorrent는 TOML 지원, 검증, 핫 리로드 및 여러 소스에서의 계층적 로딩을 갖춘 포괄적인 구성 시스템을 사용합니다.

구성 시스템: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## 구성 소스 및 우선순위

구성은 다음 순서로 로드됩니다 (나중 소스가 이전 소스를 덮어씁니다):

1. **기본값**: [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)의 내장된 합리적인 기본값
2. **구성 파일**: 현재 디렉토리 또는 `~/.config/ccbt/ccbt.toml`의 `ccbt.toml`. 참조: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **환경 변수**: `CCBT_*` 접두사 변수. 참조: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI 인수**: 명령줄 재정의. 참조: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **토렌트별**: 개별 토렌트 설정 (향후 기능)

구성 로딩: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## 구성 파일

### 기본 구성

기본 구성 파일 참조: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

구성은 섹션별로 구성됩니다:

### 네트워크 구성

네트워크 설정: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- 연결 제한: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- 요청 파이프라인: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- 소켓 조정: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- 타임아웃: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- 수신 설정: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- 전송 프로토콜: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- 속도 제한: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- 조절 전략: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- 트래커 설정: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

네트워크 구성 모델: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 디스크 구성

디스크 설정: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- 사전 할당: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- 쓰기 최적화: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- 해시 검증: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O 스레딩: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- 고급 설정: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- 스토리지 서비스 설정: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: 스토리지 서비스의 최대 파일 크기 제한 (MB) (0 또는 None = 무제한, 최대 1048576 = 1TB). 테스트 중 무제한 디스크 쓰기를 방지하며 프로덕션 사용을 위해 구성할 수 있습니다.
- 체크포인트 설정: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

디스크 구성 모델: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 전략 구성

전략 설정: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- 조각 선택: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- 고급 전략: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- 조각 우선순위: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

전략 구성 모델: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 발견 구성

발견 설정: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT 설정: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX 설정: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- 트래커 설정: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: 트래커 알림 간격 (초) (기본값: 1800.0, 범위: 60.0-86400.0)
  - `tracker_scrape_interval`: 주기적 스크래핑을 위한 트래커 스크래프 간격 (초) (기본값: 3600.0, 범위: 60.0-86400.0)
  - `tracker_auto_scrape`: 토렌트가 추가될 때 트래커를 자동으로 스크래프 (BEP 48) (기본값: false)
  - 환경 변수: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

발견 구성 모델: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 제한 구성

속도 제한: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- 전역 제한: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- 토렌트별 제한: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- 피어별 제한: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- 스케줄러 설정: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

제한 구성 모델: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 관찰 가능성 구성

관찰 가능성 설정: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- 로깅: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- 메트릭: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- 추적 및 경고: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

관찰 가능성 구성 모델: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 보안 구성

보안 설정: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

보안 구성 모델: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### 암호화 구성

ccBitTorrent는 안전한 피어 연결을 위해 BEP 3 Message Stream Encryption (MSE) 및 Protocol Encryption (PE)을 지원합니다.

**암호화 설정:**

- `enable_encryption` (bool, 기본값: `false`): 프로토콜 암호화 지원 활성화
- `encryption_mode` (str, 기본값: `"preferred"`): 암호화 모드
  - `"disabled"`: 암호화 없음 (일반 연결만)
  - `"preferred"`: 암호화 시도, 사용 불가능한 경우 일반으로 폴백
  - `"required"`: 암호화 필수, 암호화를 사용할 수 없으면 연결 실패
- `encryption_dh_key_size` (int, 기본값: `768`): Diffie-Hellman 키 크기 (비트) (768 또는 1024)
- `encryption_prefer_rc4` (bool, 기본값: `true`): 이전 클라이언트와의 호환성을 위해 RC4 암호 우선
- `encryption_allowed_ciphers` (list[str], 기본값: `["rc4", "aes"]`): 허용된 암호 유형
  - `"rc4"`: RC4 스트림 암호 (가장 호환성 높음)
  - `"aes"`: CFB 모드의 AES 암호 (더 안전함)
  - `"chacha20"`: ChaCha20 암호 (아직 구현되지 않음)
- `encryption_allow_plain_fallback` (bool, 기본값: `true`): 암호화가 실패한 경우 일반 연결로 폴백 허용 (`encryption_mode`가 `"preferred"`인 경우에만 적용)

**환경 변수:**

- `CCBT_ENABLE_ENCRYPTION`: 암호화 활성화/비활성화 (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: 암호화 모드 (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DH 키 크기 (`768` 또는 `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: RC4 우선 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: 쉼표로 구분된 목록 (예: `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: 일반 폴백 허용 (`true`/`false`)

**구성 예:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**보안 고려사항:**

1. **RC4 호환성**: RC4는 호환성을 위해 지원되지만 암호학적으로 약합니다. 가능한 경우 더 나은 보안을 위해 AES를 사용하세요.
2. **DH 키 크기**: 768비트 DH 키는 대부분의 사용 사례에 적절한 보안을 제공합니다. 1024비트는 더 강력한 보안을 제공하지만 핸드셰이크 지연 시간을 증가시킵니다.
3. **암호화 모드**:
   - `preferred`: 호환성에 최적 - 암호화를 시도하지만 우아하게 폴백합니다
   - `required`: 가장 안전하지만 암호화를 지원하지 않는 피어와의 연결에 실패할 수 있습니다
4. **성능 영향**: 암호화는 최소한의 오버헤드를 추가합니다 (RC4의 경우 약 1-5%, AES의 경우 약 2-8%) 하지만 개인 정보 보호를 향상시키고 트래픽 셰이핑을 피하는 데 도움이 됩니다.

**구현 세부사항:**

암호화 구현: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE 핸드셰이크: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- 암호 스위트: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman 교환: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML 구성

머신 러닝 설정: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML 구성 모델: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### 대시보드 구성

대시보드 설정: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

대시보드 구성 모델: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## 환경 변수

환경 변수는 `CCBT_` 접두사를 사용하며 계층적 명명 체계를 따릅니다.

참조: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

형식: `CCBT_<SECTION>_<OPTION>=<value>`

예:
- 네트워크: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- 디스크: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- 전략: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- 발견: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- 관찰 가능성: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- 제한: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- 보안: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

환경 변수 구문 분석: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## 구성 스키마

구성 스키마 및 검증: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

스키마는 다음을 정의합니다:
- 필드 유형 및 제약 조건
- 기본값
- 검증 규칙
- 문서

## 구성 기능

구성 기능 및 기능 감지: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## 구성 템플릿

사전 정의된 구성 템플릿: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

템플릿:
- 고성능 설정
- 낮은 리소스 설정
- 보안 중심 설정
- 개발 설정

## 구성 예

구성 예제는 [examples/](examples/) 디렉토리에서 사용할 수 있습니다:

- 기본 구성: [example-config-basic.toml](examples/example-config-basic.toml)
- 고급 구성: [example-config-advanced.toml](examples/example-config-advanced.toml)
- 성능 구성: [example-config-performance.toml](examples/example-config-performance.toml)
- 보안 구성: [example-config-security.toml](examples/example-config-security.toml)

## 핫 리로드

구성 핫 리로드 지원: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

구성 시스템은 클라이언트를 다시 시작하지 않고 변경 사항을 리로드하는 것을 지원합니다.

## 구성 마이그레이션

구성 마이그레이션 유틸리티: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

구성 버전 간 마이그레이션 도구.

## 구성 백업 및 차이

구성 관리 유틸리티:
- 백업: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- 차이: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## 조건부 구성

조건부 구성 지원: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## 팁 및 모범 사례

### 성능 조정

- 큰 순차 쓰기의 경우 `disk.write_buffer_kib` 증가: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Linux/NVMe에서 `direct_io` 활성화하여 쓰기 처리량 향상: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- 네트워크에 맞게 `network.pipeline_depth` 및 `network.block_size_kib` 조정: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### 리소스 최적화

- CPU 코어 수에 따라 `disk.hash_workers` 조정: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- 사용 가능한 RAM에 따라 `disk.cache_size_mb` 구성: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- 대역폭에 따라 `network.max_global_peers` 설정: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### 네트워크 구성

- 네트워크 조건에 따라 타임아웃 구성: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- 필요에 따라 프로토콜 활성화/비활성화: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- 적절하게 속도 제한 설정: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

자세한 성능 조정은 [성능 조정 가이드](performance.md)를 참조하세요.
































































































































































































