# ܡܕܒܪܢܘܬܐ ܕܬܟܢܝܬܐ

ccBitTorrent ܡܫܬܡܫ ܒܡܕܝܢܬܐ ܕܬܟܢܝܬܐ ܡܫܠܡܬܐ ܥܡ ܬܡܝܕܘܬܐ ܕܛܘܡܠ، ܒܨܘܪܬܐ، ܬܘܒ ܚܕܬܐ ܕܚܡܝܡܐ، ܘܐܚܬܐ ܕܡܬܬܪܝܛܐ ܡܢ ܣܘܪܓܐ ܣܓܝܐܐ.

ܡܕܝܢܬܐ ܕܬܟܢܝܬܐ: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## ܣܘܪܓܐ ܕܬܟܢܝܬܐ ܘܩܕܡܘܬܐ

ܬܟܢܝܬܐ ܡܬܐܚܬܐ ܒܗܢܐ ܛܘܪܣܐ (ܣܘܪܓܐ ܕܒܬܪ ܡܚܦܝܢ ܠܩܕܡܝܐ):

1. **ܒܣܝܣܝܬܐ**: ܒܣܝܣܝܬܐ ܡܚܟܡܬܐ ܕܡܬܒܢܝܢ ܡܢ [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **ܦܝܠܐ ܕܬܟܢܝܬܐ**: `ccbt.toml` ܒܕܝܪܟܬܘܪܝ ܕܗܫܐ ܐܘ `~/.config/ccbt/ccbt.toml`. ܚܙܝ: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **ܡܫܚܠܦܢܐ ܕܐܬܪܐ**: ܡܫܚܠܦܢܐ ܕܡܬܚܪܪܝܢ ܒ `CCBT_*`. ܚܙܝ: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **ܐܪܓܘܡܢܬܐ ܕܟܠܝܐܝ**: ܡܚܦܝܢܐ ܕܦܘܩܕܢܐ-ܫܪܝܬܐ. ܚܙܝ: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **ܠܟܠ ܛܘܪܢܛ**: ܬܟܢܝܬܐ ܕܛܘܪܢܛ ܕܓܢܝܐ (ܡܢܝܘܬܐ ܕܥܬܝܕܐ)

ܐܚܬܐ ܕܬܟܢܝܬܐ: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## ܦܝܠܐ ܕܬܟܢܝܬܐ

### ܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ

ܚܙܝ ܠܦܝܠܐ ܕܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

ܬܟܢܝܬܐ ܡܬܬܕܡܪܐ ܒܦܠܓܐ:

### ܬܟܢܝܬܐ ܕܫܒܝܠܐ

ܬܟܢܝܬܐ ܕܫܒܝܠܐ: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- ܚܕܝܢܐ ܕܐܚܝܕܘܬܐ: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- ܦܝܦܠܐܝܢ ܕܒܥܝܬܐ: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- ܬܟܢܝܬܐ ܕܣܘܟܝܛ: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- ܙܒܢܐ ܕܡܦܝܐ: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- ܬܟܢܝܬܐ ܕܫܡܥܐ: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- ܦܪܘܛܘܟܘܠܐ ܕܢܘܩܠܐ: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- ܚܕܝܢܐ ܕܪܝܬܐ: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- ܐܣܛܪܛܝܓܝܐ ܕܚܢܝܩܐ: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- ܬܟܢܝܬܐ ܕܛܪܐܟܪ: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܫܒܝܠܐ: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܕܝܣܩ

ܬܟܢܝܬܐ ܕܕܝܣܩ: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- ܩܕܡ-ܡܢܝܢܐ: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- ܬܟܢܝܬܐ ܕܟܬܒܐ: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- ܒܨܘܪܬܐ ܕܗܐܫ: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- ܬܪܝܕܝܢܓ ܕܐܝ ܐܘ: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- ܬܟܢܝܬܐ ܕܪܡܐ: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- ܬܟܢܝܬܐ ܕܚܕܡܬܐ ܕܐܣܛܘܪܝܓ: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: ܚܕܝܢܐ ܕܪܒܘܬܐ ܕܦܝܠܐ ܕܪܒܐ ܒ MB ܠܚܕܡܬܐ ܕܐܣܛܘܪܝܓ (0 ܐܘ None = ܠܐ ܡܚܕܝܢ، ܪܒܐ 1048576 = 1TB). ܡܢܥ ܟܬܒܐ ܕܕܝܣܩ ܕܠܐ ܡܚܕܝܢ ܒܝܘܡܬܐ ܕܒܨܘܪܬܐ ܘܡܫܟܚ ܠܡܬܬܟܢܝܘ ܠܡܫܬܡܫܢܘܬܐ ܕܦܪܘܕܘܩܣܝܘܢ.
- ܬܟܢܝܬܐ ܕܨܝܦ ܦܘܢܬ: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܕܝܣܩ: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܐܣܛܪܛܝܓܝܐ

ܬܟܢܝܬܐ ܕܐܣܛܪܛܝܓܝܐ: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- ܓܒܝܬܐ ܕܦܝܣܐ: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- ܐܣܛܪܛܝܓܝܐ ܕܪܡܐ: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- ܩܕܡܘܬܐ ܕܦܝܣܐ: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܐܣܛܪܛܝܓܝܐ: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܐܫܟܚܬܐ

ܬܟܢܝܬܐ ܕܐܫܟܚܬܐ: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- ܬܟܢܝܬܐ ܕܕܝܚܛܝ: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- ܬܟܢܝܬܐ ܕܦܝܐܟܣ: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- ܬܟܢܝܬܐ ܕܛܪܐܟܪ: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: ܡܨܥܬܐ ܕܡܠܟܫܐ ܕܛܪܐܟܪ ܒܫܢܝܢ (ܒܣܝܣܝܬܐ: 1800.0، ܦܘܪܢܣܐ: 60.0-86400.0)
  - `tracker_scrape_interval`: ܡܨܥܬܐ ܕܣܟܪܝܦ ܕܛܪܐܟܪ ܒܫܢܝܢ ܠܣܟܪܝܦ ܕܙܒܢܢܝܐ (ܒܣܝܣܝܬܐ: 3600.0، ܦܘܪܢܣܐ: 60.0-86400.0)
  - `tracker_auto_scrape`: ܐܘܛܘܡܛܝܩܐܝܬ ܣܟܪܝܦ ܠܛܪܐܟܪܣ ܟܕ ܛܘܪܢܛܣ ܡܬܬܘܣܦܢ (BEP 48) (ܒܣܝܣܝܬܐ: false)
  - ܡܫܚܠܦܢܐ ܕܐܬܪܐ: `CCBT_TRACKER_ANNOUNCE_INTERVAL`، `CCBT_TRACKER_SCRAPE_INTERVAL`، `CCBT_TRACKER_AUTO_SCRAPE`

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܐܫܟܚܬܐ: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܚܕܝܢܐ

ܚܕܝܢܐ ܕܪܝܬܐ: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- ܚܕܝܢܐ ܕܥܠܡܝܐ: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- ܚܕܝܢܐ ܕܠܟܠ ܛܘܪܢܛ: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- ܚܕܝܢܐ ܕܠܟܠ ܦܝܪ: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- ܬܟܢܝܬܐ ܕܙܒܢܢܝܐ: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܚܕܝܢܐ: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܚܙܝܬܐ

ܬܟܢܝܬܐ ܕܚܙܝܬܐ: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- ܟܬܒܐ: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- ܡܝܬܪܝܟܣ: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- ܐܬܪܐ ܘܙܘܥܐ: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܚܙܝܬܐ: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܐܡܢܘܬܐ

ܬܟܢܝܬܐ ܕܐܡܢܘܬܐ: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܐܡܢܘܬܐ: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### ܬܟܢܝܬܐ ܕܐܢܩܪܝܦܬܐ

ccBitTorrent ܡܬܡܝܕ ܒ BEP 3 Message Stream Encryption (MSE) ܘ Protocol Encryption (PE) ܠܐܚܝܕܘܬܐ ܕܦܝܪ ܕܐܡܝܢܐ.

**ܬܟܢܝܬܐ ܕܐܢܩܪܝܦܬܐ:**

- `enable_encryption` (bool، ܒܣܝܣܝܬܐ: `false`): ܦܠܚ ܠܬܡܝܕܘܬܐ ܕܐܢܩܪܝܦܬܐ ܕܦܪܘܛܘܟܘܠ
- `encryption_mode` (str، ܒܣܝܣܝܬܐ: `"preferred"`): ܐܘܪܚܐ ܕܐܢܩܪܝܦܬܐ
  - `"disabled"`: ܠܐ ܐܢܩܪܝܦܬܐ (ܐܚܝܕܘܬܐ ܕܦܫܝܛܐ ܒܠܚܘܕ)
  - `"preferred"`: ܢܣܝ ܐܢܩܪܝܦܬܐ، ܗܦܟ ܠܦܫܝܛܐ ܐܢ ܠܐ ܡܬܝܕܥ
  - `"required"`: ܐܢܩܪܝܦܬܐ ܚܝܒܝܬܐ، ܐܚܝܕܘܬܐ ܡܬܟܫܠ ܐܢ ܐܢܩܪܝܦܬܐ ܠܐ ܡܬܝܕܥ
- `encryption_dh_key_size` (int، ܒܣܝܣܝܬܐ: `768`): ܪܒܘܬܐ ܕܡܦܬܚܐ ܕܕܝܚ-ܗܠܡܢ ܒܒܝܬܐ (768 ܐܘ 1024)
- `encryption_prefer_rc4` (bool، ܒܣܝܣܝܬܐ: `true`): ܩܕܡ ܠܪܣܝ 4 ܣܝܦܪ ܠܡܬܡܝܕܘܬܐ ܥܡ ܟܠܝܢܛܣ ܥܬܝܩܐ
- `encryption_allowed_ciphers` (list[str]، ܒܣܝܣܝܬܐ: `["rc4", "aes"]`): ܐܢܘܢܐ ܕܣܝܦܪ ܕܡܬܪܫܝܢ
  - `"rc4"`: ܢܗܪܐ ܕܣܝܦܪ ܪܣܝ 4 (ܝܬܝܪ ܡܬܡܝܕ)
  - `"aes"`: ܣܝܦܪ ܐܝ ܐܝ ܐܣ ܒܐܘܪܚܐ ܕܣܝ ܐܦ ܒܝ (ܝܬܝܪ ܐܡܝܢ)
  - `"chacha20"`: ܣܝܦܪ ܟܐܟܐ 20 (ܥܕܟܝܠ ܠܐ ܡܬܒܢܐ)
- `encryption_allow_plain_fallback` (bool، ܒܣܝܣܝܬܐ: `true`): ܐܦܣ ܠܗܦܟܬܐ ܠܐܚܝܕܘܬܐ ܦܫܝܛܐ ܐܢ ܐܢܩܪܝܦܬܐ ܡܬܟܫܠ (ܒܠܚܘܕ ܡܬܡܫܚ ܟܕ `encryption_mode` ܗܘ `"preferred"`)

**ܡܫܚܠܦܢܐ ܕܐܬܪܐ:**

- `CCBT_ENABLE_ENCRYPTION`: ܦܠܚ/ܛܥܡ ܐܢܩܪܝܦܬܐ (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: ܐܘܪܚܐ ܕܐܢܩܪܝܦܬܐ (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: ܪܒܘܬܐ ܕܡܦܬܚܐ ܕܕܝܚ (`768` ܐܘ `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: ܩܕܡ ܪܣܝ 4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: ܪܝܫܡܐ ܕܡܦܪܫ ܒܦܘܫܩܐ (ܡܬܠ: `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: ܐܦܣ ܠܗܦܟܬܐ ܦܫܝܛܐ (`true`/`false`)

**ܡܬܠ ܕܬܟܢܝܬܐ:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**ܚܘܫܒܢܐ ܕܐܡܢܘܬܐ:**

1. **ܡܬܡܝܕܘܬܐ ܕܪܣܝ 4**: ܪܣܝ 4 ܡܬܡܝܕ ܠܡܬܡܝܕܘܬܐ ܐܠܐ ܟܪܝܦܬܐܝܬ ܟܪܝܫ. ܡܫܬܡܫ ܒܐܝ ܐܝ ܐܣ ܠܐܡܢܘܬܐ ܝܬܝܪܐ ܐܢ ܡܫܟܚ.
2. **ܪܒܘܬܐ ܕܡܦܬܚܐ ܕܕܝܚ**: ܡܦܬܚܐ ܕܕܝܚ 768-ܒܝܬ ܡܦܠܚ ܠܐܡܢܘܬܐ ܕܣܦܩ ܠܝܬܝܪ ܡܫܬܡܫܢܘܬܐ. 1024-ܒܝܬ ܡܦܠܚ ܠܐܡܢܘܬܐ ܚܝܠܬܢܝܬܐ ܝܬܝܪ ܐܠܐ ܡܘܣܦ ܠܡܐܚܪܘܬܐ ܕܐܚܕ ܐܝܕܐ.
3. **ܐܘܪܚܐ ܕܐܢܩܪܝܦܬܐ**:
   - `preferred`: ܛܒ ܝܬܝܪ ܠܡܬܡܝܕܘܬܐ - ܢܣܝ ܐܢܩܪܝܦܬܐ ܐܠܐ ܡܗܦܟ ܒܫܘܦܪܐ
   - `required`: ܐܡܝܢ ܝܬܝܪ ܐܠܐ ܡܫܟܚ ܠܡܬܟܫܠ ܒܐܚܝܕܘܬܐ ܥܡ ܦܝܪܣ ܕܠܐ ܡܬܡܝܕܝܢ ܒܐܢܩܪܝܦܬܐ
4. **ܐܬܪܐ ܕܬܘܩܦܐ**: ܐܢܩܪܝܦܬܐ ܡܘܣܦ ܠܐܘܒܪܗܝܕ ܙܥܘܪܐ (~1-5% ܠܪܣܝ 4، ~2-8% ܠܐܝ ܐܝ ܐܣ) ܐܠܐ ܡܬܟܝܢ ܠܚܒܝܫܘܬܐ ܘܥܕܪ ܠܡܥܪܩ ܡܢ ܫܘܦܪܐ ܕܬܪܦܝܩ.

**ܦܪܫܬܐ ܕܒܢܝܬܐ:**

ܒܢܝܬܐ ܕܐܢܩܪܝܦܬܐ: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- ܐܚܕ ܐܝܕܐ ܕܐܡ ܐܣ ܐܝ: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- ܣܘܝܬܐ ܕܣܝܦܪ: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- ܫܘܠܡܐ ܕܕܝܚ-ܗܠܡܢ: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ܬܟܢܝܬܐ ܕܐܡ ܐܠ

ܬܟܢܝܬܐ ܕܝܘܠܦܢܐ ܕܡܟܝܢܐ: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܐܡ ܐܠ: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܕܐܫܒܘܪܕ

ܬܟܢܝܬܐ ܕܕܐܫܒܘܪܕ: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܕܐܫܒܘܪܕ: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## ܡܫܚܠܦܢܐ ܕܐܬܪܐ

ܡܫܚܠܦܢܐ ܕܐܬܪܐ ܡܫܬܡܫܝܢ ܒ `CCBT_` ܘܡܗܠܟܝܢ ܒܬܕܒܝܪܐ ܕܫܡܐ ܕܡܬܬܪܝܛܐ.

ܡܥܠܝܬܐ: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

ܦܘܪܡܐ: `CCBT_<SECTION>_<OPTION>=<value>`

ܡܬܠܐ:
- ܫܒܝܠܐ: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- ܕܝܣܩ: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- ܐܣܛܪܛܝܓܝܐ: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- ܐܫܟܚܬܐ: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- ܚܙܝܬܐ: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- ܚܕܝܢܐ: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- ܐܡܢܘܬܐ: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ܐܡ ܐܠ: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

ܦܘܪܫܐ ܕܡܫܚܠܦܢܐ ܕܐܬܪܐ: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## ܣܟܝܡܐ ܕܬܟܢܝܬܐ

ܣܟܝܡܐ ܕܬܟܢܝܬܐ ܘܒܨܘܪܬܐ: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

ܣܟܝܡܐ ܡܚܪܪ:
- ܐܢܘܢܐ ܕܕܘܟܬܐ ܘܚܕܝܢܐ
- ܒܣܝܣܝܬܐ ܕܪܝܫܡܐ
- ܩܢܘܢܐ ܕܒܨܘܪܬܐ
- ܟܬܒܐ

## ܡܢܝܘܬܐ ܕܬܟܢܝܬܐ

ܡܢܝܘܬܐ ܕܬܟܢܝܬܐ ܘܐܫܟܚܬܐ ܕܡܢܝܘܬܐ: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## ܛܡܦܠܝܬܐ ܕܬܟܢܝܬܐ

ܛܡܦܠܝܬܐ ܕܬܟܢܝܬܐ ܕܡܬܚܪܪܢ ܩܕܡܐܝܬ: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

ܛܡܦܠܝܬܐ ܠ:
- ܬܟܢܝܬܐ ܕܬܘܩܦܐ ܪܡܐ
- ܬܟܢܝܬܐ ܕܡܒܘܥܐ ܙܥܘܪܐ
- ܬܟܢܝܬܐ ܕܡܬܟܝܢܐ ܠܐܡܢܘܬܐ
- ܬܟܢܝܬܐ ܕܒܢܝܬܐ

## ܡܬܠܐ ܕܬܟܢܝܬܐ

ܡܬܠܐ ܕܬܟܢܝܬܐ ܐܝܬܝܗܘܢ ܒܕܝܪܟܬܘܪܝ [examples/](examples/):

- ܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ: [example-config-basic.toml](examples/example-config-basic.toml)
- ܬܟܢܝܬܐ ܕܪܡܐ: [example-config-advanced.toml](examples/example-config-advanced.toml)
- ܬܟܢܝܬܐ ܕܬܘܩܦܐ: [example-config-performance.toml](examples/example-config-performance.toml)
- ܬܟܢܝܬܐ ܕܐܡܢܘܬܐ: [example-config-security.toml](examples/example-config-security.toml)

## ܬܘܒ ܚܕܬܐ ܕܚܡܝܡܐ

ܬܡܝܕܘܬܐ ܕܬܘܒ ܚܕܬܐ ܕܚܡܝܡܐ ܕܬܟܢܝܬܐ: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

ܡܕܝܢܬܐ ܕܬܟܢܝܬܐ ܡܬܡܝܕܐ ܒܬܘܒ ܚܕܬܐ ܕܫܘܚܠܦܐ ܕܠܐ ܬܘܒ ܚܕܬܐ ܕܟܠܝܢܛ.

## ܫܢܝܬܐ ܕܬܟܢܝܬܐ

ܡܐܢܐ ܕܫܢܝܬܐ ܕܬܟܢܝܬܐ: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

ܡܐܢܐ ܠܫܢܝܬܐ ܒܝܢ ܓܪܣܐ ܕܬܟܢܝܬܐ.

## ܒܟܘܬܐ ܘܦܪܫܐ ܕܬܟܢܝܬܐ

ܡܐܢܐ ܕܡܕܒܪܢܘܬܐ ܕܬܟܢܝܬܐ:
- ܒܟܘܬܐ: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- ܦܪܫܐ: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## ܬܟܢܝܬܐ ܕܡܬܬܪܝܛܐ

ܬܡܝܕܘܬܐ ܕܬܟܢܝܬܐ ܕܡܬܬܪܝܛܐ: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## ܢܝܗܐ ܘܡܫܟܚܢܐ ܕܛܒ ܝܬܝܪ

### ܬܟܢܝܬܐ ܕܬܘܩܦܐ

- ܐܘܣܦ ܠ `disk.write_buffer_kib` ܠܟܬܒܐ ܕܡܬܬܪܝܛܐ ܪܒܐ: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- ܦܠܚ ܠ `direct_io` ܒ Linux/NVMe ܠܬܘܩܦܐ ܕܟܬܒܐ ܝܬܝܪ: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- ܬܟܢ ܠ `network.pipeline_depth` ܘ `network.block_size_kib` ܠܫܒܝܠܟ: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### ܬܟܢܝܬܐ ܕܡܒܘܥܐ

- ܬܟܢ ܠ `disk.hash_workers` ܐܝܟ ܩܪܢܝܢ ܕܣܝ ܦܝ ܐܝ: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- ܬܟܢ ܠ `disk.cache_size_mb` ܐܝܟ ܪܐܡ ܕܐܝܬ: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- ܣܝܡ ܠ `network.max_global_peers` ܐܝܟ ܦܘܬܐ ܕܦܘܫܩܐ: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### ܬܟܢܝܬܐ ܕܫܒܝܠܐ

- ܬܟܢ ܠܙܒܢܐ ܕܡܦܝܐ ܐܝܟ ܫܘܝܢܐ ܕܫܒܝܠܐ: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- ܦܠܚ/ܛܥܡ ܦܪܘܛܘܟܘܠܐ ܐܝܟ ܕܡܬܒܥܐ: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- ܣܝܡ ܚܕܝܢܐ ܕܪܝܬܐ ܐܝܟ ܕܡܬܒܥܐ: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

ܠܬܟܢܝܬܐ ܡܦܪܫܬܐ ܕܬܘܩܦܐ، ܚܙܝ ܠ [ܡܕܒܪܢܘܬܐ ܕܬܟܢܝܬܐ ܕܬܘܩܦܐ](performance.md).






ccBitTorrent ܡܫܬܡܫ ܒܡܕܝܢܬܐ ܕܬܟܢܝܬܐ ܡܫܠܡܬܐ ܥܡ ܬܡܝܕܘܬܐ ܕܛܘܡܠ، ܒܨܘܪܬܐ، ܬܘܒ ܚܕܬܐ ܕܚܡܝܡܐ، ܘܐܚܬܐ ܕܡܬܬܪܝܛܐ ܡܢ ܣܘܪܓܐ ܣܓܝܐܐ.

ܡܕܝܢܬܐ ܕܬܟܢܝܬܐ: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## ܣܘܪܓܐ ܕܬܟܢܝܬܐ ܘܩܕܡܘܬܐ

ܬܟܢܝܬܐ ܡܬܐܚܬܐ ܒܗܢܐ ܛܘܪܣܐ (ܣܘܪܓܐ ܕܒܬܪ ܡܚܦܝܢ ܠܩܕܡܝܐ):

1. **ܒܣܝܣܝܬܐ**: ܒܣܝܣܝܬܐ ܡܚܟܡܬܐ ܕܡܬܒܢܝܢ ܡܢ [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **ܦܝܠܐ ܕܬܟܢܝܬܐ**: `ccbt.toml` ܒܕܝܪܟܬܘܪܝ ܕܗܫܐ ܐܘ `~/.config/ccbt/ccbt.toml`. ܚܙܝ: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **ܡܫܚܠܦܢܐ ܕܐܬܪܐ**: ܡܫܚܠܦܢܐ ܕܡܬܚܪܪܝܢ ܒ `CCBT_*`. ܚܙܝ: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **ܐܪܓܘܡܢܬܐ ܕܟܠܝܐܝ**: ܡܚܦܝܢܐ ܕܦܘܩܕܢܐ-ܫܪܝܬܐ. ܚܙܝ: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **ܠܟܠ ܛܘܪܢܛ**: ܬܟܢܝܬܐ ܕܛܘܪܢܛ ܕܓܢܝܐ (ܡܢܝܘܬܐ ܕܥܬܝܕܐ)

ܐܚܬܐ ܕܬܟܢܝܬܐ: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## ܦܝܠܐ ܕܬܟܢܝܬܐ

### ܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ

ܚܙܝ ܠܦܝܠܐ ܕܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

ܬܟܢܝܬܐ ܡܬܬܕܡܪܐ ܒܦܠܓܐ:

### ܬܟܢܝܬܐ ܕܫܒܝܠܐ

ܬܟܢܝܬܐ ܕܫܒܝܠܐ: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- ܚܕܝܢܐ ܕܐܚܝܕܘܬܐ: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- ܦܝܦܠܐܝܢ ܕܒܥܝܬܐ: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- ܬܟܢܝܬܐ ܕܣܘܟܝܛ: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- ܙܒܢܐ ܕܡܦܝܐ: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- ܬܟܢܝܬܐ ܕܫܡܥܐ: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- ܦܪܘܛܘܟܘܠܐ ܕܢܘܩܠܐ: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- ܚܕܝܢܐ ܕܪܝܬܐ: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- ܐܣܛܪܛܝܓܝܐ ܕܚܢܝܩܐ: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- ܬܟܢܝܬܐ ܕܛܪܐܟܪ: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܫܒܝܠܐ: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܕܝܣܩ

ܬܟܢܝܬܐ ܕܕܝܣܩ: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- ܩܕܡ-ܡܢܝܢܐ: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- ܬܟܢܝܬܐ ܕܟܬܒܐ: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- ܒܨܘܪܬܐ ܕܗܐܫ: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- ܬܪܝܕܝܢܓ ܕܐܝ ܐܘ: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- ܬܟܢܝܬܐ ܕܪܡܐ: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- ܬܟܢܝܬܐ ܕܚܕܡܬܐ ܕܐܣܛܘܪܝܓ: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: ܚܕܝܢܐ ܕܪܒܘܬܐ ܕܦܝܠܐ ܕܪܒܐ ܒ MB ܠܚܕܡܬܐ ܕܐܣܛܘܪܝܓ (0 ܐܘ None = ܠܐ ܡܚܕܝܢ، ܪܒܐ 1048576 = 1TB). ܡܢܥ ܟܬܒܐ ܕܕܝܣܩ ܕܠܐ ܡܚܕܝܢ ܒܝܘܡܬܐ ܕܒܨܘܪܬܐ ܘܡܫܟܚ ܠܡܬܬܟܢܝܘ ܠܡܫܬܡܫܢܘܬܐ ܕܦܪܘܕܘܩܣܝܘܢ.
- ܬܟܢܝܬܐ ܕܨܝܦ ܦܘܢܬ: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܕܝܣܩ: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܐܣܛܪܛܝܓܝܐ

ܬܟܢܝܬܐ ܕܐܣܛܪܛܝܓܝܐ: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- ܓܒܝܬܐ ܕܦܝܣܐ: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- ܐܣܛܪܛܝܓܝܐ ܕܪܡܐ: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- ܩܕܡܘܬܐ ܕܦܝܣܐ: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܐܣܛܪܛܝܓܝܐ: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܐܫܟܚܬܐ

ܬܟܢܝܬܐ ܕܐܫܟܚܬܐ: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- ܬܟܢܝܬܐ ܕܕܝܚܛܝ: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- ܬܟܢܝܬܐ ܕܦܝܐܟܣ: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- ܬܟܢܝܬܐ ܕܛܪܐܟܪ: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: ܡܨܥܬܐ ܕܡܠܟܫܐ ܕܛܪܐܟܪ ܒܫܢܝܢ (ܒܣܝܣܝܬܐ: 1800.0، ܦܘܪܢܣܐ: 60.0-86400.0)
  - `tracker_scrape_interval`: ܡܨܥܬܐ ܕܣܟܪܝܦ ܕܛܪܐܟܪ ܒܫܢܝܢ ܠܣܟܪܝܦ ܕܙܒܢܢܝܐ (ܒܣܝܣܝܬܐ: 3600.0، ܦܘܪܢܣܐ: 60.0-86400.0)
  - `tracker_auto_scrape`: ܐܘܛܘܡܛܝܩܐܝܬ ܣܟܪܝܦ ܠܛܪܐܟܪܣ ܟܕ ܛܘܪܢܛܣ ܡܬܬܘܣܦܢ (BEP 48) (ܒܣܝܣܝܬܐ: false)
  - ܡܫܚܠܦܢܐ ܕܐܬܪܐ: `CCBT_TRACKER_ANNOUNCE_INTERVAL`، `CCBT_TRACKER_SCRAPE_INTERVAL`، `CCBT_TRACKER_AUTO_SCRAPE`

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܐܫܟܚܬܐ: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܚܕܝܢܐ

ܚܕܝܢܐ ܕܪܝܬܐ: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- ܚܕܝܢܐ ܕܥܠܡܝܐ: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- ܚܕܝܢܐ ܕܠܟܠ ܛܘܪܢܛ: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- ܚܕܝܢܐ ܕܠܟܠ ܦܝܪ: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- ܬܟܢܝܬܐ ܕܙܒܢܢܝܐ: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܚܕܝܢܐ: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܚܙܝܬܐ

ܬܟܢܝܬܐ ܕܚܙܝܬܐ: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- ܟܬܒܐ: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- ܡܝܬܪܝܟܣ: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- ܐܬܪܐ ܘܙܘܥܐ: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܚܙܝܬܐ: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܐܡܢܘܬܐ

ܬܟܢܝܬܐ ܕܐܡܢܘܬܐ: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܐܡܢܘܬܐ: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### ܬܟܢܝܬܐ ܕܐܢܩܪܝܦܬܐ

ccBitTorrent ܡܬܡܝܕ ܒ BEP 3 Message Stream Encryption (MSE) ܘ Protocol Encryption (PE) ܠܐܚܝܕܘܬܐ ܕܦܝܪ ܕܐܡܝܢܐ.

**ܬܟܢܝܬܐ ܕܐܢܩܪܝܦܬܐ:**

- `enable_encryption` (bool، ܒܣܝܣܝܬܐ: `false`): ܦܠܚ ܠܬܡܝܕܘܬܐ ܕܐܢܩܪܝܦܬܐ ܕܦܪܘܛܘܟܘܠ
- `encryption_mode` (str، ܒܣܝܣܝܬܐ: `"preferred"`): ܐܘܪܚܐ ܕܐܢܩܪܝܦܬܐ
  - `"disabled"`: ܠܐ ܐܢܩܪܝܦܬܐ (ܐܚܝܕܘܬܐ ܕܦܫܝܛܐ ܒܠܚܘܕ)
  - `"preferred"`: ܢܣܝ ܐܢܩܪܝܦܬܐ، ܗܦܟ ܠܦܫܝܛܐ ܐܢ ܠܐ ܡܬܝܕܥ
  - `"required"`: ܐܢܩܪܝܦܬܐ ܚܝܒܝܬܐ، ܐܚܝܕܘܬܐ ܡܬܟܫܠ ܐܢ ܐܢܩܪܝܦܬܐ ܠܐ ܡܬܝܕܥ
- `encryption_dh_key_size` (int، ܒܣܝܣܝܬܐ: `768`): ܪܒܘܬܐ ܕܡܦܬܚܐ ܕܕܝܚ-ܗܠܡܢ ܒܒܝܬܐ (768 ܐܘ 1024)
- `encryption_prefer_rc4` (bool، ܒܣܝܣܝܬܐ: `true`): ܩܕܡ ܠܪܣܝ 4 ܣܝܦܪ ܠܡܬܡܝܕܘܬܐ ܥܡ ܟܠܝܢܛܣ ܥܬܝܩܐ
- `encryption_allowed_ciphers` (list[str]، ܒܣܝܣܝܬܐ: `["rc4", "aes"]`): ܐܢܘܢܐ ܕܣܝܦܪ ܕܡܬܪܫܝܢ
  - `"rc4"`: ܢܗܪܐ ܕܣܝܦܪ ܪܣܝ 4 (ܝܬܝܪ ܡܬܡܝܕ)
  - `"aes"`: ܣܝܦܪ ܐܝ ܐܝ ܐܣ ܒܐܘܪܚܐ ܕܣܝ ܐܦ ܒܝ (ܝܬܝܪ ܐܡܝܢ)
  - `"chacha20"`: ܣܝܦܪ ܟܐܟܐ 20 (ܥܕܟܝܠ ܠܐ ܡܬܒܢܐ)
- `encryption_allow_plain_fallback` (bool، ܒܣܝܣܝܬܐ: `true`): ܐܦܣ ܠܗܦܟܬܐ ܠܐܚܝܕܘܬܐ ܦܫܝܛܐ ܐܢ ܐܢܩܪܝܦܬܐ ܡܬܟܫܠ (ܒܠܚܘܕ ܡܬܡܫܚ ܟܕ `encryption_mode` ܗܘ `"preferred"`)

**ܡܫܚܠܦܢܐ ܕܐܬܪܐ:**

- `CCBT_ENABLE_ENCRYPTION`: ܦܠܚ/ܛܥܡ ܐܢܩܪܝܦܬܐ (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: ܐܘܪܚܐ ܕܐܢܩܪܝܦܬܐ (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: ܪܒܘܬܐ ܕܡܦܬܚܐ ܕܕܝܚ (`768` ܐܘ `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: ܩܕܡ ܪܣܝ 4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: ܪܝܫܡܐ ܕܡܦܪܫ ܒܦܘܫܩܐ (ܡܬܠ: `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: ܐܦܣ ܠܗܦܟܬܐ ܦܫܝܛܐ (`true`/`false`)

**ܡܬܠ ܕܬܟܢܝܬܐ:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**ܚܘܫܒܢܐ ܕܐܡܢܘܬܐ:**

1. **ܡܬܡܝܕܘܬܐ ܕܪܣܝ 4**: ܪܣܝ 4 ܡܬܡܝܕ ܠܡܬܡܝܕܘܬܐ ܐܠܐ ܟܪܝܦܬܐܝܬ ܟܪܝܫ. ܡܫܬܡܫ ܒܐܝ ܐܝ ܐܣ ܠܐܡܢܘܬܐ ܝܬܝܪܐ ܐܢ ܡܫܟܚ.
2. **ܪܒܘܬܐ ܕܡܦܬܚܐ ܕܕܝܚ**: ܡܦܬܚܐ ܕܕܝܚ 768-ܒܝܬ ܡܦܠܚ ܠܐܡܢܘܬܐ ܕܣܦܩ ܠܝܬܝܪ ܡܫܬܡܫܢܘܬܐ. 1024-ܒܝܬ ܡܦܠܚ ܠܐܡܢܘܬܐ ܚܝܠܬܢܝܬܐ ܝܬܝܪ ܐܠܐ ܡܘܣܦ ܠܡܐܚܪܘܬܐ ܕܐܚܕ ܐܝܕܐ.
3. **ܐܘܪܚܐ ܕܐܢܩܪܝܦܬܐ**:
   - `preferred`: ܛܒ ܝܬܝܪ ܠܡܬܡܝܕܘܬܐ - ܢܣܝ ܐܢܩܪܝܦܬܐ ܐܠܐ ܡܗܦܟ ܒܫܘܦܪܐ
   - `required`: ܐܡܝܢ ܝܬܝܪ ܐܠܐ ܡܫܟܚ ܠܡܬܟܫܠ ܒܐܚܝܕܘܬܐ ܥܡ ܦܝܪܣ ܕܠܐ ܡܬܡܝܕܝܢ ܒܐܢܩܪܝܦܬܐ
4. **ܐܬܪܐ ܕܬܘܩܦܐ**: ܐܢܩܪܝܦܬܐ ܡܘܣܦ ܠܐܘܒܪܗܝܕ ܙܥܘܪܐ (~1-5% ܠܪܣܝ 4، ~2-8% ܠܐܝ ܐܝ ܐܣ) ܐܠܐ ܡܬܟܝܢ ܠܚܒܝܫܘܬܐ ܘܥܕܪ ܠܡܥܪܩ ܡܢ ܫܘܦܪܐ ܕܬܪܦܝܩ.

**ܦܪܫܬܐ ܕܒܢܝܬܐ:**

ܒܢܝܬܐ ܕܐܢܩܪܝܦܬܐ: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- ܐܚܕ ܐܝܕܐ ܕܐܡ ܐܣ ܐܝ: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- ܣܘܝܬܐ ܕܣܝܦܪ: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- ܫܘܠܡܐ ܕܕܝܚ-ܗܠܡܢ: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ܬܟܢܝܬܐ ܕܐܡ ܐܠ

ܬܟܢܝܬܐ ܕܝܘܠܦܢܐ ܕܡܟܝܢܐ: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܐܡ ܐܠ: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ܬܟܢܝܬܐ ܕܕܐܫܒܘܪܕ

ܬܟܢܝܬܐ ܕܕܐܫܒܘܪܕ: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

ܡܘܕܠ ܕܬܟܢܝܬܐ ܕܕܐܫܒܘܪܕ: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## ܡܫܚܠܦܢܐ ܕܐܬܪܐ

ܡܫܚܠܦܢܐ ܕܐܬܪܐ ܡܫܬܡܫܝܢ ܒ `CCBT_` ܘܡܗܠܟܝܢ ܒܬܕܒܝܪܐ ܕܫܡܐ ܕܡܬܬܪܝܛܐ.

ܡܥܠܝܬܐ: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

ܦܘܪܡܐ: `CCBT_<SECTION>_<OPTION>=<value>`

ܡܬܠܐ:
- ܫܒܝܠܐ: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- ܕܝܣܩ: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- ܐܣܛܪܛܝܓܝܐ: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- ܐܫܟܚܬܐ: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- ܚܙܝܬܐ: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- ܚܕܝܢܐ: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- ܐܡܢܘܬܐ: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ܐܡ ܐܠ: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

ܦܘܪܫܐ ܕܡܫܚܠܦܢܐ ܕܐܬܪܐ: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## ܣܟܝܡܐ ܕܬܟܢܝܬܐ

ܣܟܝܡܐ ܕܬܟܢܝܬܐ ܘܒܨܘܪܬܐ: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

ܣܟܝܡܐ ܡܚܪܪ:
- ܐܢܘܢܐ ܕܕܘܟܬܐ ܘܚܕܝܢܐ
- ܒܣܝܣܝܬܐ ܕܪܝܫܡܐ
- ܩܢܘܢܐ ܕܒܨܘܪܬܐ
- ܟܬܒܐ

## ܡܢܝܘܬܐ ܕܬܟܢܝܬܐ

ܡܢܝܘܬܐ ܕܬܟܢܝܬܐ ܘܐܫܟܚܬܐ ܕܡܢܝܘܬܐ: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## ܛܡܦܠܝܬܐ ܕܬܟܢܝܬܐ

ܛܡܦܠܝܬܐ ܕܬܟܢܝܬܐ ܕܡܬܚܪܪܢ ܩܕܡܐܝܬ: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

ܛܡܦܠܝܬܐ ܠ:
- ܬܟܢܝܬܐ ܕܬܘܩܦܐ ܪܡܐ
- ܬܟܢܝܬܐ ܕܡܒܘܥܐ ܙܥܘܪܐ
- ܬܟܢܝܬܐ ܕܡܬܟܝܢܐ ܠܐܡܢܘܬܐ
- ܬܟܢܝܬܐ ܕܒܢܝܬܐ

## ܡܬܠܐ ܕܬܟܢܝܬܐ

ܡܬܠܐ ܕܬܟܢܝܬܐ ܐܝܬܝܗܘܢ ܒܕܝܪܟܬܘܪܝ [examples/](examples/):

- ܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ: [example-config-basic.toml](examples/example-config-basic.toml)
- ܬܟܢܝܬܐ ܕܪܡܐ: [example-config-advanced.toml](examples/example-config-advanced.toml)
- ܬܟܢܝܬܐ ܕܬܘܩܦܐ: [example-config-performance.toml](examples/example-config-performance.toml)
- ܬܟܢܝܬܐ ܕܐܡܢܘܬܐ: [example-config-security.toml](examples/example-config-security.toml)

## ܬܘܒ ܚܕܬܐ ܕܚܡܝܡܐ

ܬܡܝܕܘܬܐ ܕܬܘܒ ܚܕܬܐ ܕܚܡܝܡܐ ܕܬܟܢܝܬܐ: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

ܡܕܝܢܬܐ ܕܬܟܢܝܬܐ ܡܬܡܝܕܐ ܒܬܘܒ ܚܕܬܐ ܕܫܘܚܠܦܐ ܕܠܐ ܬܘܒ ܚܕܬܐ ܕܟܠܝܢܛ.

## ܫܢܝܬܐ ܕܬܟܢܝܬܐ

ܡܐܢܐ ܕܫܢܝܬܐ ܕܬܟܢܝܬܐ: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

ܡܐܢܐ ܠܫܢܝܬܐ ܒܝܢ ܓܪܣܐ ܕܬܟܢܝܬܐ.

## ܒܟܘܬܐ ܘܦܪܫܐ ܕܬܟܢܝܬܐ

ܡܐܢܐ ܕܡܕܒܪܢܘܬܐ ܕܬܟܢܝܬܐ:
- ܒܟܘܬܐ: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- ܦܪܫܐ: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## ܬܟܢܝܬܐ ܕܡܬܬܪܝܛܐ

ܬܡܝܕܘܬܐ ܕܬܟܢܝܬܐ ܕܡܬܬܪܝܛܐ: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## ܢܝܗܐ ܘܡܫܟܚܢܐ ܕܛܒ ܝܬܝܪ

### ܬܟܢܝܬܐ ܕܬܘܩܦܐ

- ܐܘܣܦ ܠ `disk.write_buffer_kib` ܠܟܬܒܐ ܕܡܬܬܪܝܛܐ ܪܒܐ: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- ܦܠܚ ܠ `direct_io` ܒ Linux/NVMe ܠܬܘܩܦܐ ܕܟܬܒܐ ܝܬܝܪ: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- ܬܟܢ ܠ `network.pipeline_depth` ܘ `network.block_size_kib` ܠܫܒܝܠܟ: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### ܬܟܢܝܬܐ ܕܡܒܘܥܐ

- ܬܟܢ ܠ `disk.hash_workers` ܐܝܟ ܩܪܢܝܢ ܕܣܝ ܦܝ ܐܝ: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- ܬܟܢ ܠ `disk.cache_size_mb` ܐܝܟ ܪܐܡ ܕܐܝܬ: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- ܣܝܡ ܠ `network.max_global_peers` ܐܝܟ ܦܘܬܐ ܕܦܘܫܩܐ: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### ܬܟܢܝܬܐ ܕܫܒܝܠܐ

- ܬܟܢ ܠܙܒܢܐ ܕܡܦܝܐ ܐܝܟ ܫܘܝܢܐ ܕܫܒܝܠܐ: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- ܦܠܚ/ܛܥܡ ܦܪܘܛܘܟܘܠܐ ܐܝܟ ܕܡܬܒܥܐ: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- ܣܝܡ ܚܕܝܢܐ ܕܪܝܬܐ ܐܝܟ ܕܡܬܒܥܐ: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

ܠܬܟܢܝܬܐ ܡܦܪܫܬܐ ܕܬܘܩܦܐ، ܚܙܝ ܠ [ܡܕܒܪܢܘܬܐ ܕܬܟܢܝܬܐ ܕܬܘܩܦܐ](performance.md).
































































































































































































