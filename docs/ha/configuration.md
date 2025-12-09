# Jagorar Saitin

ccBitTorrent yana amfani da tsarin saitin mai cikakke tare da goyan bayan TOML, tabbatarwa, sake lodawa mai zafi, da lodawa mai matsayi daga tushe da yawa.

Tsarin saitin: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## Tushen Saitin da Fitarwa

Ana lodawa saitin a wannan tsari (tushe na baya-baya suna maye gurbin na farko):

1. **Tsoho**: Tsoho na hankali na cikin gida daga [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **Fayil ɗin Saitin**: `ccbt.toml` a cikin babban fayil ɗin yanzu ko `~/.config/ccbt/ccbt.toml`. Duba: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **Masu Canza Yanayi**: Masu canza yanayi masu farko `CCBT_*`. Duba: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **Hujjojin CLI**: Maye gurbin layin umarni. Duba: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **Kowane Torrent**: Saitunan torrent na mutum (fasali na gaba)

Lodawa saitin: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## Fayil ɗin Saitin

### Saitin Tsoho

Duba fayil ɗin saitin tsoho: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

An tsara saitin zuwa sasanni:

### Saitin Hanyar Sadarwa

Saitunan hanyar sadarwa: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- Iyakoki na haɗuwa: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- Bututun buƙata: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- Gyara socket: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- Lokutan ƙarewa: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Saitunan saurare: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- Ka'idojin jigilar kaya: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Iyakoki na gudun: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- Dabarar shaƙewa: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- Saitunan tracker: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

Samfurin saitin hanyar sadarwa: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Diski

Saitunan diski: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- Gabatarwa: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- Ingantawa rubutu: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- Tabbatarwa hash: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- Threading I/O: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- Saitunan ci gaba: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- Saitunan sabis na ajiya: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: Iyakar girman fayil ɗin mafi girma a MB don sabis na ajiya (0 ko None = mara iyaka, matsakaici 1048576 = 1TB). Yana hana rubuce-rubucen diski mara iyaka yayin gwaji kuma ana iya saita shi don amfani da samarwa.
- Saitunan maƙallan bincike: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

Samfurin saitin diski: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Dabarar

Saitunan dabarar: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- Zaɓin guntu: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- Dabarar ci gaba: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- Fitarwa guntu: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

Samfurin saitin dabarar: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Bincike

Saitunan bincike: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- Saitunan DHT: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- Saitunan PEX: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- Saitunan tracker: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Tazarar sanarwar tracker a cikin daƙiƙa (tsoho: 1800.0, kewayon: 60.0-86400.0)
  - `tracker_scrape_interval`: Tazarar gogewa tracker a cikin daƙiƙa don gogewa na lokaci-lokaci (tsoho: 3600.0, kewayon: 60.0-86400.0)
  - `tracker_auto_scrape`: Yi gogewa ta atomatik tare da trackers lokacin da aka ƙara torrents (BEP 48) (tsoho: false)
  - Masu canza yanayi: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

Samfurin saitin bincike: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Iyakoki

Iyakoki na gudun: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- Iyakoki na duniya: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- Iyakoki na kowane torrent: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- Iyakoki na kowane peer: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- Saitunan mai tsara lokaci: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

Samfurin saitin iyakoki: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Dubawa

Saitunan dubawa: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- Rubutu: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- Ma'auni: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- Bincike da faɗakarwa: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

Samfurin saitin dubawa: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Tsaro

Saitunan tsaro: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

Samfurin saitin tsaro: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### Saitin Rufe Sirri

ccBitTorrent yana goyan bayan BEP 3 Message Stream Encryption (MSE) da Protocol Encryption (PE) don haɗuwa mai tsaro na peer.

**Saitunan Rufe Sirri:**

- `enable_encryption` (bool, tsoho: `false`): Kuna goyan bayan rufe sirri na ka'idoji
- `encryption_mode` (str, tsoho: `"preferred"`): Yanayin rufe sirri
  - `"disabled"`: Babu rufe sirri (haɗuwa mai tsabta kawai)
  - `"preferred"`: Yi ƙoƙarin rufe sirri, komawa zuwa tsabta idan ba ya samuwa
  - `"required"`: Rufe sirri wajibi ne, haɗuwa ta gaza idan rufe sirri ba ya samuwa
- `encryption_dh_key_size` (int, tsoho: `768`): Girman maɓalli Diffie-Hellman a cikin bits (768 ko 1024)
- `encryption_prefer_rc4` (bool, tsoho: `true`): Zaɓi cipher RC4 don dacewa tare da abokan ciniki na tsoho
- `encryption_allowed_ciphers` (list[str], tsoho: `["rc4", "aes"]`): Nau'ikan cipher da aka yarda
  - `"rc4"`: Cipher na rafi RC4 (mafi dacewa)
  - `"aes"`: Cipher AES a cikin yanayin CFB (mafi tsaro)
  - `"chacha20"`: Cipher ChaCha20 (har yanzu ba a aiwatar da shi ba)
- `encryption_allow_plain_fallback` (bool, tsoho: `true`): Bari komawa zuwa haɗuwa mai tsabta idan rufe sirri ya gaza (kawai yana aiki lokacin da `encryption_mode` ya kasance `"preferred"`)

**Masu Canza Yanayi:**

- `CCBT_ENABLE_ENCRYPTION`: Kuna/ƙashe rufe sirri (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: Yanayin rufe sirri (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: Girman maɓalli DH (`768` ko `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: Zaɓi RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: Jerin da aka raba da waƙafi (misali `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: Bari komawa mai tsabta (`true`/`false`)

**Misalin Saitin:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**Abubuwan da Ake Kula da Tsaro:**

1. **Dacewar RC4**: RC4 ana goyan bayan shi don dacewa amma yana da rauni a cikin ɓoyayyen rubutu. Yi amfani da AES don tsaro mafi kyau idan zai yiwu.
2. **Girman Maɓalli DH**: Maɓallan DH na bit 768 suna ba da tsaro mai isa don yawancin lokuta. Na bit 1024 suna ba da tsaro mai ƙarfi amma suna ƙara jinkirin hannu.
3. **Yanayin Rufe Sirri**:
   - `preferred`: Mafi kyau don dacewa - yana ƙoƙarin rufe sirri amma yana faɗuwa cikin ladabi
   - `required`: Mafi tsaro amma yana iya gaza haɗuwa tare da peers waɗanda ba su goyan bayan rufe sirri ba
4. **Tasirin Aiki**: Rufe sirri yana ƙara ƙaramin ƙari (~1-5% don RC4, ~2-8% don AES) amma yana inganta sirri kuma yana taimakawa guje wa siffa ta hanyar sadarwa.

**Cikakkun Bayanai na Aiwatarwa:**

Aiwatarwa rufe sirri: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Rukunin Cipher: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Musayar Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### Saitin ML

Saitunan koyon inji: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

Samfurin saitin ML: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Dashboard

Saitunan dashboard: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

Samfurin saitin dashboard: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## Masu Canza Yanayi

Masu canza yanayi suna amfani da farkon `CCBT_` kuma suna bin tsarin suna mai matsayi.

Nassoshi: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

Tsari: `CCBT_<SECTION>_<OPTION>=<value>`

Misalai:
- Hanyar sadarwa: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- Diski: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- Dabarar: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- Bincike: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- Dubawa: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- Iyakoki: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- Tsaro: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

Fassarar masu canza yanayi: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## Tsarin Saitin

Tsarin saitin da tabbatarwa: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

Tsarin yana bayyana:
- Nau'ikan filaye da ƙuntatawa
- Ƙimar tsoho
- Dokokin tabbatarwa
- Takardu

## Iyawar Saitin

Iyawar saitin da gano fasali: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## Samfuran Saitin

Samfuran saitin da aka riga aka bayyana: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

Samfuran don:
- Saitin aiki mai inganci
- Saitin albarkatun ƙasa
- Saitin mai da hankali kan tsaro
- Saitin ci gaba

## Misalan Saitin

Misalan saitin suna samuwa a cikin babban fayil ɗin [examples/](examples/):

- Saitin asali: [example-config-basic.toml](examples/example-config-basic.toml)
- Saitin ci gaba: [example-config-advanced.toml](examples/example-config-advanced.toml)
- Saitin aiki: [example-config-performance.toml](examples/example-config-performance.toml)
- Saitin tsaro: [example-config-security.toml](examples/example-config-security.toml)

## Sake Lodawa Mai Zafi

Goyan bayan sake lodawa mai zafi na saitin: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

Tsarin saitin yana goyan bayan sake lodawa canje-canje ba tare da sake kunna abokin ciniki ba.

## Ƙaura Saitin

Kayan aikin ƙaura saitin: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

Kayan aiki don ƙaura tsakanin nau'ikan saitin.

## Ajiya Saitin da Bambanci

Kayan aikin sarrafa saitin:
- Ajiya: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Bambanci: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## Saitin Yanayin

Goyan bayan saitin yanayin: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## Shawarwari da Mafi Kyawun Ayyuka

### Gyara Aiki

- Ƙara `disk.write_buffer_kib` don rubuce-rubucen jeri masu girma: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Kuna `direct_io` akan Linux/NVMe don ingantaccen rubuce-rubucen: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- Gyara `network.pipeline_depth` da `network.block_size_kib` don hanyar sadarwar ku: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### Ingantawa Albarkatu

- Gyara `disk.hash_workers` bisa ga ƙwayoyin CPU: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- Saita `disk.cache_size_mb` bisa ga RAM da ake samu: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- Saita `network.max_global_peers` bisa ga faɗin bandwidth: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### Saitin Hanyar Sadarwa

- Saita lokutan ƙarewa bisa ga yanayin hanyar sadarwa: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Kuna/ƙashe ka'idoji kamar yadda ake buƙata: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Saita iyakoki na gudun yadda ya kamata: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

Don cikakken gyara aiki, duba [Jagorar Gyara Aiki](performance.md).






ccBitTorrent yana amfani da tsarin saitin mai cikakke tare da goyan bayan TOML, tabbatarwa, sake lodawa mai zafi, da lodawa mai matsayi daga tushe da yawa.

Tsarin saitin: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## Tushen Saitin da Fitarwa

Ana lodawa saitin a wannan tsari (tushe na baya-baya suna maye gurbin na farko):

1. **Tsoho**: Tsoho na hankali na cikin gida daga [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **Fayil ɗin Saitin**: `ccbt.toml` a cikin babban fayil ɗin yanzu ko `~/.config/ccbt/ccbt.toml`. Duba: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **Masu Canza Yanayi**: Masu canza yanayi masu farko `CCBT_*`. Duba: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **Hujjojin CLI**: Maye gurbin layin umarni. Duba: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **Kowane Torrent**: Saitunan torrent na mutum (fasali na gaba)

Lodawa saitin: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## Fayil ɗin Saitin

### Saitin Tsoho

Duba fayil ɗin saitin tsoho: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

An tsara saitin zuwa sasanni:

### Saitin Hanyar Sadarwa

Saitunan hanyar sadarwa: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- Iyakoki na haɗuwa: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- Bututun buƙata: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- Gyara socket: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- Lokutan ƙarewa: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Saitunan saurare: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- Ka'idojin jigilar kaya: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Iyakoki na gudun: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- Dabarar shaƙewa: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- Saitunan tracker: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

Samfurin saitin hanyar sadarwa: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Diski

Saitunan diski: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- Gabatarwa: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- Ingantawa rubutu: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- Tabbatarwa hash: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- Threading I/O: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- Saitunan ci gaba: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- Saitunan sabis na ajiya: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: Iyakar girman fayil ɗin mafi girma a MB don sabis na ajiya (0 ko None = mara iyaka, matsakaici 1048576 = 1TB). Yana hana rubuce-rubucen diski mara iyaka yayin gwaji kuma ana iya saita shi don amfani da samarwa.
- Saitunan maƙallan bincike: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

Samfurin saitin diski: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Dabarar

Saitunan dabarar: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- Zaɓin guntu: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- Dabarar ci gaba: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- Fitarwa guntu: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

Samfurin saitin dabarar: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Bincike

Saitunan bincike: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- Saitunan DHT: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- Saitunan PEX: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- Saitunan tracker: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Tazarar sanarwar tracker a cikin daƙiƙa (tsoho: 1800.0, kewayon: 60.0-86400.0)
  - `tracker_scrape_interval`: Tazarar gogewa tracker a cikin daƙiƙa don gogewa na lokaci-lokaci (tsoho: 3600.0, kewayon: 60.0-86400.0)
  - `tracker_auto_scrape`: Yi gogewa ta atomatik tare da trackers lokacin da aka ƙara torrents (BEP 48) (tsoho: false)
  - Masu canza yanayi: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

Samfurin saitin bincike: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Iyakoki

Iyakoki na gudun: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- Iyakoki na duniya: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- Iyakoki na kowane torrent: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- Iyakoki na kowane peer: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- Saitunan mai tsara lokaci: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

Samfurin saitin iyakoki: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Dubawa

Saitunan dubawa: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- Rubutu: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- Ma'auni: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- Bincike da faɗakarwa: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

Samfurin saitin dubawa: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Tsaro

Saitunan tsaro: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

Samfurin saitin tsaro: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### Saitin Rufe Sirri

ccBitTorrent yana goyan bayan BEP 3 Message Stream Encryption (MSE) da Protocol Encryption (PE) don haɗuwa mai tsaro na peer.

**Saitunan Rufe Sirri:**

- `enable_encryption` (bool, tsoho: `false`): Kuna goyan bayan rufe sirri na ka'idoji
- `encryption_mode` (str, tsoho: `"preferred"`): Yanayin rufe sirri
  - `"disabled"`: Babu rufe sirri (haɗuwa mai tsabta kawai)
  - `"preferred"`: Yi ƙoƙarin rufe sirri, komawa zuwa tsabta idan ba ya samuwa
  - `"required"`: Rufe sirri wajibi ne, haɗuwa ta gaza idan rufe sirri ba ya samuwa
- `encryption_dh_key_size` (int, tsoho: `768`): Girman maɓalli Diffie-Hellman a cikin bits (768 ko 1024)
- `encryption_prefer_rc4` (bool, tsoho: `true`): Zaɓi cipher RC4 don dacewa tare da abokan ciniki na tsoho
- `encryption_allowed_ciphers` (list[str], tsoho: `["rc4", "aes"]`): Nau'ikan cipher da aka yarda
  - `"rc4"`: Cipher na rafi RC4 (mafi dacewa)
  - `"aes"`: Cipher AES a cikin yanayin CFB (mafi tsaro)
  - `"chacha20"`: Cipher ChaCha20 (har yanzu ba a aiwatar da shi ba)
- `encryption_allow_plain_fallback` (bool, tsoho: `true`): Bari komawa zuwa haɗuwa mai tsabta idan rufe sirri ya gaza (kawai yana aiki lokacin da `encryption_mode` ya kasance `"preferred"`)

**Masu Canza Yanayi:**

- `CCBT_ENABLE_ENCRYPTION`: Kuna/ƙashe rufe sirri (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: Yanayin rufe sirri (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: Girman maɓalli DH (`768` ko `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: Zaɓi RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: Jerin da aka raba da waƙafi (misali `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: Bari komawa mai tsabta (`true`/`false`)

**Misalin Saitin:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**Abubuwan da Ake Kula da Tsaro:**

1. **Dacewar RC4**: RC4 ana goyan bayan shi don dacewa amma yana da rauni a cikin ɓoyayyen rubutu. Yi amfani da AES don tsaro mafi kyau idan zai yiwu.
2. **Girman Maɓalli DH**: Maɓallan DH na bit 768 suna ba da tsaro mai isa don yawancin lokuta. Na bit 1024 suna ba da tsaro mai ƙarfi amma suna ƙara jinkirin hannu.
3. **Yanayin Rufe Sirri**:
   - `preferred`: Mafi kyau don dacewa - yana ƙoƙarin rufe sirri amma yana faɗuwa cikin ladabi
   - `required`: Mafi tsaro amma yana iya gaza haɗuwa tare da peers waɗanda ba su goyan bayan rufe sirri ba
4. **Tasirin Aiki**: Rufe sirri yana ƙara ƙaramin ƙari (~1-5% don RC4, ~2-8% don AES) amma yana inganta sirri kuma yana taimakawa guje wa siffa ta hanyar sadarwa.

**Cikakkun Bayanai na Aiwatarwa:**

Aiwatarwa rufe sirri: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Rukunin Cipher: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Musayar Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### Saitin ML

Saitunan koyon inji: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

Samfurin saitin ML: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Saitin Dashboard

Saitunan dashboard: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

Samfurin saitin dashboard: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## Masu Canza Yanayi

Masu canza yanayi suna amfani da farkon `CCBT_` kuma suna bin tsarin suna mai matsayi.

Nassoshi: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

Tsari: `CCBT_<SECTION>_<OPTION>=<value>`

Misalai:
- Hanyar sadarwa: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- Diski: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- Dabarar: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- Bincike: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- Dubawa: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- Iyakoki: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- Tsaro: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

Fassarar masu canza yanayi: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## Tsarin Saitin

Tsarin saitin da tabbatarwa: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

Tsarin yana bayyana:
- Nau'ikan filaye da ƙuntatawa
- Ƙimar tsoho
- Dokokin tabbatarwa
- Takardu

## Iyawar Saitin

Iyawar saitin da gano fasali: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## Samfuran Saitin

Samfuran saitin da aka riga aka bayyana: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

Samfuran don:
- Saitin aiki mai inganci
- Saitin albarkatun ƙasa
- Saitin mai da hankali kan tsaro
- Saitin ci gaba

## Misalan Saitin

Misalan saitin suna samuwa a cikin babban fayil ɗin [examples/](examples/):

- Saitin asali: [example-config-basic.toml](examples/example-config-basic.toml)
- Saitin ci gaba: [example-config-advanced.toml](examples/example-config-advanced.toml)
- Saitin aiki: [example-config-performance.toml](examples/example-config-performance.toml)
- Saitin tsaro: [example-config-security.toml](examples/example-config-security.toml)

## Sake Lodawa Mai Zafi

Goyan bayan sake lodawa mai zafi na saitin: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

Tsarin saitin yana goyan bayan sake lodawa canje-canje ba tare da sake kunna abokin ciniki ba.

## Ƙaura Saitin

Kayan aikin ƙaura saitin: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

Kayan aiki don ƙaura tsakanin nau'ikan saitin.

## Ajiya Saitin da Bambanci

Kayan aikin sarrafa saitin:
- Ajiya: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Bambanci: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## Saitin Yanayin

Goyan bayan saitin yanayin: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## Shawarwari da Mafi Kyawun Ayyuka

### Gyara Aiki

- Ƙara `disk.write_buffer_kib` don rubuce-rubucen jeri masu girma: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Kuna `direct_io` akan Linux/NVMe don ingantaccen rubuce-rubucen: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- Gyara `network.pipeline_depth` da `network.block_size_kib` don hanyar sadarwar ku: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### Ingantawa Albarkatu

- Gyara `disk.hash_workers` bisa ga ƙwayoyin CPU: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- Saita `disk.cache_size_mb` bisa ga RAM da ake samu: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- Saita `network.max_global_peers` bisa ga faɗin bandwidth: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### Saitin Hanyar Sadarwa

- Saita lokutan ƙarewa bisa ga yanayin hanyar sadarwa: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Kuna/ƙashe ka'idoji kamar yadda ake buƙata: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Saita iyakoki na gudun yadda ya kamata: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

Don cikakken gyara aiki, duba [Jagorar Gyara Aiki](performance.md).




























































































































































































