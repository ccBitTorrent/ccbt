# Mwongozo wa Usanidi

ccBitTorrent hutumia mfumo kamili wa usanidi na msaada wa TOML, uthibitishaji, upakiaji wa joto, na upakiaji wa kihierarkia kutoka vyanzo vingi.

Mfumo wa usanidi: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## Vyanzo vya Usanidi na Kipaumbele

Usanidi hupakiwa kwa mpangilio huu (vyanzo vya baadaye vinabadilisha vya awali):

1. **Vigezo vya Kawaida**: Vigezo vya kawaida vya akili vya ndani kutoka [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **Faili ya Usanidi**: `ccbt.toml` katika saraka ya sasa au `~/.config/ccbt/ccbt.toml`. Angalia: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **Vigezo vya Mazingira**: Vigezo vilivyo na kiambishi `CCBT_*`. Angalia: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **Hoja za CLI**: Mabadiliko ya mstari wa amri. Angalia: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **Kwa Torrent**: Mipangilio ya torrent ya kibinafsi (kipengele cha baadaye)

Upakiaji wa usanidi: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## Faili ya Usanidi

### Usanidi wa Kawaida

Rejea faili ya usanidi wa kawaida: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

Usanidi umepangwa katika sehemu:

### Usanidi wa Mtandao

Mipangilio ya mtandao: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- Mipaka ya muunganisho: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- Bomba la maombi: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- Urekebishaji wa socket: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- Muda wa mwisho: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Mipangilio ya kusikiliza: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- Itifaki za usafiri: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Mipaka ya kasi: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- Mkakati wa kukaba: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- Mipangilio ya tracker: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

Mfano wa usanidi wa mtandao: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Diski

Mipangilio ya diski: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- Utayarishaji: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- Uboreshaji wa kuandika: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- Uthibitishaji wa hash: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- Threading ya I/O: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- Mipangilio ya hali ya juu: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- Mipangilio ya huduma ya uhifadhi: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: Kikomo cha juu cha ukubwa wa faili katika MB kwa huduma ya uhifadhi (0 au None = bila kikomo, upeo 1048576 = 1TB). Inazuia kuandika diski bila kikomo wakati wa majaribio na inaweza kusanidiwa kwa matumizi ya uzalishaji.
- Mipangilio ya alama ya kuangalia: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

Mfano wa usanidi wa diski: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Mkakati

Mipangilio ya mkakati: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- Uchaguzi wa kipande: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- Mkakati wa hali ya juu: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- Kipaumbele cha vipande: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

Mfano wa usanidi wa mkakati: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Ugunduzi

Mipangilio ya ugunduzi: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- Mipangilio ya DHT: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- Mipangilio ya PEX: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- Mipangilio ya tracker: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Muda wa kutangaza tracker kwa sekunde (kawaida: 1800.0, anuwai: 60.0-86400.0)
  - `tracker_scrape_interval`: Muda wa kukwaruza tracker kwa sekunde kwa kukwaruza mara kwa mara (kawaida: 3600.0, anuwai: 60.0-86400.0)
  - `tracker_auto_scrape`: Kukwaruza trackers kiotomatiki wakati torrents zinaongezwa (BEP 48) (kawaida: false)
  - Vigezo vya mazingira: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

Mfano wa usanidi wa ugunduzi: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Mipaka

Mipaka ya kasi: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- Mipaka ya kimataifa: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- Mipaka ya torrent: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- Mipaka ya peer: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- Mipangilio ya ratiba: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

Mfano wa usanidi wa mipaka: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Uchunguzi

Mipangilio ya uchunguzi: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- Uwekaji alama: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- Vipimo: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- Ufuatiliaji na tahadhari: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

Mfano wa usanidi wa uchunguzi: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Usalama

Mipangilio ya usalama: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

Mfano wa usanidi wa usalama: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### Usanidi wa Usimbaji

ccBitTorrent inasaidia BEP 3 Message Stream Encryption (MSE) na Protocol Encryption (PE) kwa muunganisho salama wa peer.

**Mipangilio ya Usimbaji:**

- `enable_encryption` (bool, kawaida: `false`): Wezesha msaada wa usimbaji wa itifaki
- `encryption_mode` (str, kawaida: `"preferred"`): Hali ya usimbaji
  - `"disabled"`: Hakuna usimbaji (muunganisho wazi tu)
  - `"preferred"`: Jaribu usimbaji, rudi kwa wazi ikiwa haipatikani
  - `"required"`: Usimbaji ni lazima, muunganisho unashindwa ikiwa usimbaji haupatikani
- `encryption_dh_key_size` (int, kawaida: `768`): Ukubwa wa ufunguo wa Diffie-Hellman kwa bits (768 au 1024)
- `encryption_prefer_rc4` (bool, kawaida: `true`): Pendekeza cipher RC4 kwa ufanisi na wateja wa zamani
- `encryption_allowed_ciphers` (list[str], kawaida: `["rc4", "aes"]`): Aina za cipher zinazoruhusiwa
  - `"rc4"`: Cipher ya mkondo wa RC4 (inayofanana zaidi)
  - `"aes"`: Cipher ya AES katika hali ya CFB (salama zaidi)
  - `"chacha20"`: Cipher ya ChaCha20 (haijatekelezwa bado)
- `encryption_allow_plain_fallback` (bool, kawaida: `true`): Ruhusu kurudi kwa muunganisho wazi ikiwa usimbaji umeshindwa (inatumika tu wakati `encryption_mode` ni `"preferred"`)

**Vigezo vya Mazingira:**

- `CCBT_ENABLE_ENCRYPTION`: Wezesha/zima usimbaji (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: Hali ya usimbaji (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: Ukubwa wa ufunguo wa DH (`768` au `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: Pendekeza RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: Orodha iliyotenganishwa na koma (mfano, `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: Ruhusu kurudi kwa wazi (`true`/`false`)

**Mfano wa Usanidi:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**Mazingatio ya Usalama:**

1. **Ufanisi wa RC4**: RC4 inasaidiwa kwa ufanisi lakini ni dhaifu kriptografiki. Tumia AES kwa usalama bora iwezekanavyo.
2. **Ukubwa wa Ufunguo wa DH**: Ufunguo wa DH wa bit 768 hutoa usalama wa kutosha kwa matumizi mengi. Bit 1024 hutoa usalama wa nguvu zaidi lakini huongeza ucheleweshaji wa mkono.
3. **Hali za Usimbaji**:
   - `preferred`: Bora kwa ufanisi - hujaribu usimbaji lakini hurudi kwa adabu
   - `required`: Salama zaidi lakini inaweza kushindwa kuunganisha na peers ambao hawasaidii usimbaji
4. **Athari ya Utendakazi**: Usimbaji huongeza mzigo mdogo (~1-5% kwa RC4, ~2-8% kwa AES) lakini huboresha faragha na husaidia kuepuka umbizo la trafiki.

**Maelezo ya Utekelezaji:**

Utekelezaji wa usimbaji: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- Mkono wa MSE: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Seti za Cipher: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Mabadilishano ya Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### Usanidi wa ML

Mipangilio ya kujifunza kwa mashine: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

Mfano wa usanidi wa ML: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Dashboard

Mipangilio ya dashboard: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

Mfano wa usanidi wa dashboard: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## Vigezo vya Mazingira

Vigezo vya mazingira hutumia kiambishi `CCBT_` na hufuata mpangilio wa majina wa kihierarkia.

Marejeo: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

Muundo: `CCBT_<SECTION>_<OPTION>=<value>`

Mifano:
- Mtandao: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- Diski: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- Mkakati: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- Ugunduzi: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- Uchunguzi: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- Mipaka: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- Usalama: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

Uchambuzi wa vigezo vya mazingira: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## Mpango wa Usanidi

Mpango wa usanidi na uthibitishaji: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

Mpango unafafanua:
- Aina za sehemu na vikwazo
- Thamani za kawaida
- Sheria za uthibitishaji
- Hati

## Uwezo wa Usanidi

Uwezo wa usanidi na ugunduzi wa kipengele: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## Mfano wa Usanidi

Mfano wa usanidi uliofafanuliwa hapo awali: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

Mfano kwa:
- Usanidi wa utendakazi wa juu
- Usanidi wa rasilimali za chini
- Usanidi unaolenga usalama
- Usanidi wa maendeleo

## Mifano ya Usanidi

Mifano ya usanidi inapatikana katika saraka ya [examples/](examples/):

- Usanidi wa msingi: [example-config-basic.toml](examples/example-config-basic.toml)
- Usanidi wa hali ya juu: [example-config-advanced.toml](examples/example-config-advanced.toml)
- Usanidi wa utendakazi: [example-config-performance.toml](examples/example-config-performance.toml)
- Usanidi wa usalama: [example-config-security.toml](examples/example-config-security.toml)

## Upakiaji wa Joto

Msaada wa upakiaji wa joto wa usanidi: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

Mfumo wa usanidi unasaidia upakiaji upya wa mabadiliko bila kuanzisha upya klienti.

## Uhamishaji wa Usanidi

Zana za uhamishaji wa usanidi: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

Zana za kuhamisha kati ya matoleo ya usanidi.

## Usanidi wa Backup na Tofauti

Zana za usimamizi wa usanidi:
- Backup: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Tofauti: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## Usanidi wa Masharti

Msaada wa usanidi wa masharti: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## Vidokezo na Mbinu Bora

### Urekebishaji wa Utendakazi

- Ongeza `disk.write_buffer_kib` kwa kuandika kwa mpangilio kwa kiasi kikubwa: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Wezesha `direct_io` kwenye Linux/NVMe kwa utoaji bora wa kuandika: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- Rekebisha `network.pipeline_depth` na `network.block_size_kib` kwa mtandao wako: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### Uboreshaji wa Rasilimali

- Rekebisha `disk.hash_workers` kulingana na cores za CPU: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- Sanidi `disk.cache_size_mb` kulingana na RAM inayopatikana: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- Weka `network.max_global_peers` kulingana na bandwidth: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### Usanidi wa Mtandao

- Sanidi muda wa mwisho kulingana na hali ya mtandao: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Wezesha/zima itifaki kama inahitajika: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Weka mipaka ya kasi kwa usahihi: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

Kwa urekebishaji wa kina wa utendakazi, angalia [Mwongozo wa Urekebishaji wa Utendakazi](performance.md).






ccBitTorrent hutumia mfumo kamili wa usanidi na msaada wa TOML, uthibitishaji, upakiaji wa joto, na upakiaji wa kihierarkia kutoka vyanzo vingi.

Mfumo wa usanidi: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## Vyanzo vya Usanidi na Kipaumbele

Usanidi hupakiwa kwa mpangilio huu (vyanzo vya baadaye vinabadilisha vya awali):

1. **Vigezo vya Kawaida**: Vigezo vya kawaida vya akili vya ndani kutoka [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **Faili ya Usanidi**: `ccbt.toml` katika saraka ya sasa au `~/.config/ccbt/ccbt.toml`. Angalia: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **Vigezo vya Mazingira**: Vigezo vilivyo na kiambishi `CCBT_*`. Angalia: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **Hoja za CLI**: Mabadiliko ya mstari wa amri. Angalia: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **Kwa Torrent**: Mipangilio ya torrent ya kibinafsi (kipengele cha baadaye)

Upakiaji wa usanidi: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## Faili ya Usanidi

### Usanidi wa Kawaida

Rejea faili ya usanidi wa kawaida: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

Usanidi umepangwa katika sehemu:

### Usanidi wa Mtandao

Mipangilio ya mtandao: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- Mipaka ya muunganisho: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- Bomba la maombi: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- Urekebishaji wa socket: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- Muda wa mwisho: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Mipangilio ya kusikiliza: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- Itifaki za usafiri: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Mipaka ya kasi: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- Mkakati wa kukaba: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- Mipangilio ya tracker: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

Mfano wa usanidi wa mtandao: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Diski

Mipangilio ya diski: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- Utayarishaji: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- Uboreshaji wa kuandika: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- Uthibitishaji wa hash: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- Threading ya I/O: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- Mipangilio ya hali ya juu: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- Mipangilio ya huduma ya uhifadhi: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: Kikomo cha juu cha ukubwa wa faili katika MB kwa huduma ya uhifadhi (0 au None = bila kikomo, upeo 1048576 = 1TB). Inazuia kuandika diski bila kikomo wakati wa majaribio na inaweza kusanidiwa kwa matumizi ya uzalishaji.
- Mipangilio ya alama ya kuangalia: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

Mfano wa usanidi wa diski: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Mkakati

Mipangilio ya mkakati: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- Uchaguzi wa kipande: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- Mkakati wa hali ya juu: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- Kipaumbele cha vipande: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

Mfano wa usanidi wa mkakati: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Ugunduzi

Mipangilio ya ugunduzi: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- Mipangilio ya DHT: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- Mipangilio ya PEX: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- Mipangilio ya tracker: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Muda wa kutangaza tracker kwa sekunde (kawaida: 1800.0, anuwai: 60.0-86400.0)
  - `tracker_scrape_interval`: Muda wa kukwaruza tracker kwa sekunde kwa kukwaruza mara kwa mara (kawaida: 3600.0, anuwai: 60.0-86400.0)
  - `tracker_auto_scrape`: Kukwaruza trackers kiotomatiki wakati torrents zinaongezwa (BEP 48) (kawaida: false)
  - Vigezo vya mazingira: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

Mfano wa usanidi wa ugunduzi: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Mipaka

Mipaka ya kasi: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- Mipaka ya kimataifa: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- Mipaka ya torrent: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- Mipaka ya peer: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- Mipangilio ya ratiba: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

Mfano wa usanidi wa mipaka: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Uchunguzi

Mipangilio ya uchunguzi: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- Uwekaji alama: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- Vipimo: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- Ufuatiliaji na tahadhari: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

Mfano wa usanidi wa uchunguzi: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Usalama

Mipangilio ya usalama: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

Mfano wa usanidi wa usalama: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### Usanidi wa Usimbaji

ccBitTorrent inasaidia BEP 3 Message Stream Encryption (MSE) na Protocol Encryption (PE) kwa muunganisho salama wa peer.

**Mipangilio ya Usimbaji:**

- `enable_encryption` (bool, kawaida: `false`): Wezesha msaada wa usimbaji wa itifaki
- `encryption_mode` (str, kawaida: `"preferred"`): Hali ya usimbaji
  - `"disabled"`: Hakuna usimbaji (muunganisho wazi tu)
  - `"preferred"`: Jaribu usimbaji, rudi kwa wazi ikiwa haipatikani
  - `"required"`: Usimbaji ni lazima, muunganisho unashindwa ikiwa usimbaji haupatikani
- `encryption_dh_key_size` (int, kawaida: `768`): Ukubwa wa ufunguo wa Diffie-Hellman kwa bits (768 au 1024)
- `encryption_prefer_rc4` (bool, kawaida: `true`): Pendekeza cipher RC4 kwa ufanisi na wateja wa zamani
- `encryption_allowed_ciphers` (list[str], kawaida: `["rc4", "aes"]`): Aina za cipher zinazoruhusiwa
  - `"rc4"`: Cipher ya mkondo wa RC4 (inayofanana zaidi)
  - `"aes"`: Cipher ya AES katika hali ya CFB (salama zaidi)
  - `"chacha20"`: Cipher ya ChaCha20 (haijatekelezwa bado)
- `encryption_allow_plain_fallback` (bool, kawaida: `true`): Ruhusu kurudi kwa muunganisho wazi ikiwa usimbaji umeshindwa (inatumika tu wakati `encryption_mode` ni `"preferred"`)

**Vigezo vya Mazingira:**

- `CCBT_ENABLE_ENCRYPTION`: Wezesha/zima usimbaji (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: Hali ya usimbaji (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: Ukubwa wa ufunguo wa DH (`768` au `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: Pendekeza RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: Orodha iliyotenganishwa na koma (mfano, `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: Ruhusu kurudi kwa wazi (`true`/`false`)

**Mfano wa Usanidi:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**Mazingatio ya Usalama:**

1. **Ufanisi wa RC4**: RC4 inasaidiwa kwa ufanisi lakini ni dhaifu kriptografiki. Tumia AES kwa usalama bora iwezekanavyo.
2. **Ukubwa wa Ufunguo wa DH**: Ufunguo wa DH wa bit 768 hutoa usalama wa kutosha kwa matumizi mengi. Bit 1024 hutoa usalama wa nguvu zaidi lakini huongeza ucheleweshaji wa mkono.
3. **Hali za Usimbaji**:
   - `preferred`: Bora kwa ufanisi - hujaribu usimbaji lakini hurudi kwa adabu
   - `required`: Salama zaidi lakini inaweza kushindwa kuunganisha na peers ambao hawasaidii usimbaji
4. **Athari ya Utendakazi**: Usimbaji huongeza mzigo mdogo (~1-5% kwa RC4, ~2-8% kwa AES) lakini huboresha faragha na husaidia kuepuka umbizo la trafiki.

**Maelezo ya Utekelezaji:**

Utekelezaji wa usimbaji: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- Mkono wa MSE: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Seti za Cipher: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Mabadilishano ya Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### Usanidi wa ML

Mipangilio ya kujifunza kwa mashine: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

Mfano wa usanidi wa ML: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Usanidi wa Dashboard

Mipangilio ya dashboard: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

Mfano wa usanidi wa dashboard: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## Vigezo vya Mazingira

Vigezo vya mazingira hutumia kiambishi `CCBT_` na hufuata mpangilio wa majina wa kihierarkia.

Marejeo: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

Muundo: `CCBT_<SECTION>_<OPTION>=<value>`

Mifano:
- Mtandao: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- Diski: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- Mkakati: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- Ugunduzi: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- Uchunguzi: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- Mipaka: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- Usalama: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

Uchambuzi wa vigezo vya mazingira: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## Mpango wa Usanidi

Mpango wa usanidi na uthibitishaji: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

Mpango unafafanua:
- Aina za sehemu na vikwazo
- Thamani za kawaida
- Sheria za uthibitishaji
- Hati

## Uwezo wa Usanidi

Uwezo wa usanidi na ugunduzi wa kipengele: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## Mfano wa Usanidi

Mfano wa usanidi uliofafanuliwa hapo awali: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

Mfano kwa:
- Usanidi wa utendakazi wa juu
- Usanidi wa rasilimali za chini
- Usanidi unaolenga usalama
- Usanidi wa maendeleo

## Mifano ya Usanidi

Mifano ya usanidi inapatikana katika saraka ya [examples/](examples/):

- Usanidi wa msingi: [example-config-basic.toml](examples/example-config-basic.toml)
- Usanidi wa hali ya juu: [example-config-advanced.toml](examples/example-config-advanced.toml)
- Usanidi wa utendakazi: [example-config-performance.toml](examples/example-config-performance.toml)
- Usanidi wa usalama: [example-config-security.toml](examples/example-config-security.toml)

## Upakiaji wa Joto

Msaada wa upakiaji wa joto wa usanidi: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

Mfumo wa usanidi unasaidia upakiaji upya wa mabadiliko bila kuanzisha upya klienti.

## Uhamishaji wa Usanidi

Zana za uhamishaji wa usanidi: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

Zana za kuhamisha kati ya matoleo ya usanidi.

## Usanidi wa Backup na Tofauti

Zana za usimamizi wa usanidi:
- Backup: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Tofauti: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## Usanidi wa Masharti

Msaada wa usanidi wa masharti: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## Vidokezo na Mbinu Bora

### Urekebishaji wa Utendakazi

- Ongeza `disk.write_buffer_kib` kwa kuandika kwa mpangilio kwa kiasi kikubwa: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Wezesha `direct_io` kwenye Linux/NVMe kwa utoaji bora wa kuandika: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- Rekebisha `network.pipeline_depth` na `network.block_size_kib` kwa mtandao wako: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### Uboreshaji wa Rasilimali

- Rekebisha `disk.hash_workers` kulingana na cores za CPU: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- Sanidi `disk.cache_size_mb` kulingana na RAM inayopatikana: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- Weka `network.max_global_peers` kulingana na bandwidth: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### Usanidi wa Mtandao

- Sanidi muda wa mwisho kulingana na hali ya mtandao: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Wezesha/zima itifaki kama inahitajika: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Weka mipaka ya kasi kwa usahihi: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

Kwa urekebishaji wa kina wa utendakazi, angalia [Mwongozo wa Urekebishaji wa Utendakazi](performance.md).




























































































































































































