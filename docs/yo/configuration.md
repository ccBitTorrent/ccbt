# Ìtọ́sọ́nà Ṣètò

ccBitTorrent lo ìgbàkọlé ṣètò tí ó ṣe dáadáa pẹ̀lú àtìlẹ́yìn TOML, ìjẹ́rìí, ìgbàkọlé tútù, àti ìgbàkọlé ìgbàkọlé láti ọ̀pọ̀lọpọ̀ orísun.

Ìgbàkọlé ṣètò: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## Àwọn Orísun Ṣètò àti Ìpàtàkì

A gba ṣètò ní ìlànà yìí (àwọn orísun tókàn yóò pa àwọn àkọ́kọ́):

1. **Àwọn Àkọ́kọ́**: Àwọn àkọ́kọ́ tí ó ṣe dáadáa tí ó wà nínú láti [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **Fàìlì Ṣètò**: `ccbt.toml` ní àwọn fóldà lọ́wọ́lọ́wọ́ tàbí `~/.config/ccbt/ccbt.toml`. Wo: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **Àwọn Onírúurú Ayé**: Àwọn onírúurú pẹ̀lú àkọ́lé `CCBT_*`. Wo: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **Àwọn Àgbéyẹ̀wò CLI**: Àwọn ìyípadà ìlànà àṣẹ. Wo: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **Fún Torrent**: Àwọn ṣètò torrent aládàá (ẹ̀yà ìwájú)

Ìgbàkọlé ṣètò: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## Fàìlì Ṣètò

### Ṣètò Àkọ́kọ́

Wo fàìlì ṣètò àkọ́kọ́: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

A ṣètò ṣètò sí àwọn apá:

### Ṣètò Nẹ́tíwọ̀kì

Àwọn ṣètò nẹ́tíwọ̀kì: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- Àwọn ìdíwọ̀n ìsopọ̀: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- Ìgbàkọlé ìbéèrè: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- Ìtúnṣe socket: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- Àwọn ìgbà ìparí: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Àwọn ṣètò gbọ́: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- Àwọn ìlànà gbigbé: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Àwọn ìdíwọ̀n ìyára: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- Ìlànà ìdínkù: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- Àwọn ṣètò tracker: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

Àpẹrẹ ṣètò nẹ́tíwọ̀kì: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Dísíkì

Àwọn ṣètò dísíkì: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- Ìpèsè tẹ́lẹ̀: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- Ìtúnṣe kíkọ: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- Ìjẹ́rìí hash: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- Ìgbàkọlé I/O: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- Àwọn ṣètò tó ga: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- Àwọn ṣètò iṣẹ́ ìpamọ́: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: Ìdíwọ̀n ìwọ̀n fàìlì tó pọ̀ jùlọ ní MB fún iṣẹ́ ìpamọ́ (0 tàbí None = àìní ìdíwọ̀n, tó pọ̀ jùlọ 1048576 = 1TB). Ó dènà kíkọ dísíkì àìní ìdíwọ̀n nígbà ìdánwò àti a lè ṣètò fún lilo ìgbéjáde.
- Àwọn ṣètò àkíyèsí: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

Àpẹrẹ ṣètò dísíkì: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Ìlànà

Àwọn ṣètò ìlànà: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- Ìyàn apá: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- Ìlànà tó ga: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- Àwọn ìpàtàkì apá: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

Àpẹrẹ ṣètò ìlànà: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Ìwádìí

Àwọn ṣètò ìwádìí: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- Àwọn ṣètò DHT: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- Àwọn ṣètò PEX: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- Àwọn ṣètò tracker: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Ìgbà ìsọrọ̀ tracker ní àwọn ìṣẹ́jú (àkọ́kọ́: 1800.0, ààlà: 60.0-86400.0)
  - `tracker_scrape_interval`: Ìgbà ìgbàkọlé tracker ní àwọn ìṣẹ́jú fún ìgbàkọlé ìgbàkọlé (àkọ́kọ́: 3600.0, ààlà: 60.0-86400.0)
  - `tracker_auto_scrape`: Ṣe ìgbàkọlé àìdánilójú pẹ̀lú trackers nígbà tí a fi torrents sí i (BEP 48) (àkọ́kọ́: false)
  - Àwọn onírúurú ayé: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

Àpẹrẹ ṣètò ìwádìí: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Àwọn Ìdíwọ̀n

Àwọn ìdíwọ̀n ìyára: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- Àwọn ìdíwọ̀n àgbáyé: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- Àwọn ìdíwọ̀n torrent: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- Àwọn ìdíwọ̀n peer: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- Àwọn ṣètò àgbékalẹ̀: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

Àpẹrẹ ṣètò àwọn ìdíwọ̀n: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Ìwòye

Àwọn ṣètò ìwòye: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- Ìkọ̀wé: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- Àwọn ìwọ̀n: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- Ìtọ́kàsọ̀ àti àwọn ìkìlọ̀: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

Àpẹrẹ ṣètò ìwòye: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Ààbò

Àwọn ṣètò ààbò: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

Àpẹrẹ ṣètò ààbò: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### Ṣètò Ìpamọ́

ccBitTorrent ṣe àtìlẹ́yìn BEP 3 Message Stream Encryption (MSE) àti Protocol Encryption (PE) fún àwọn ìsopọ̀ peer ààbò.

**Àwọn Ṣètò Ìpamọ́:**

- `enable_encryption` (bool, àkọ́kọ́: `false`): Mú kí àtìlẹ́yìn ìpamọ́ ìlànà ṣiṣẹ́
- `encryption_mode` (str, àkọ́kọ́: `"preferred"`): Ìpamọ́ ìpamọ́
  - `"disabled"`: Kò sí ìpamọ́ (àwọn ìsopọ̀ aláìlẹ́kọ̀n nìkan)
  - `"preferred"`: Gbìyànjú ìpamọ́, padà sí aláìlẹ́kọ̀n tí kò bá wà
  - `"required"`: Ìpamọ́ jẹ́ dandan, ìsopọ̀ bá jẹ́ tí ìpamọ́ kò bá wà
- `encryption_dh_key_size` (int, àkọ́kọ́: `768`): Ìwọ̀n bọ̀tùn Diffie-Hellman ní bits (768 tàbí 1024)
- `encryption_prefer_rc4` (bool, àkọ́kọ́: `true`): Yàn cipher RC4 fún ìbámu pẹ̀lú àwọn oníbára àtijọ́
- `encryption_allowed_ciphers` (list[str], àkọ́kọ́: `["rc4", "aes"]`): Àwọn irú cipher tí a gba
  - `"rc4"`: Cipher ìgbàkọlé RC4 (ó ṣe dáadáa jùlọ)
  - `"aes"`: Cipher AES ní ìpamọ́ CFB (ó ṣe dáadáa jùlọ)
  - `"chacha20"`: Cipher ChaCha20 (kò tíì ṣe ìgbéjáde)
- `encryption_allow_plain_fallback` (bool, àkọ́kọ́: `true`): Gba padà sí ìsopọ̀ aláìlẹ́kọ̀n tí ìpamọ́ bá ṣe àṣìṣe (ó ṣe nìkan nígbà tí `encryption_mode` jẹ́ `"preferred"`)

**Àwọn Onírúurú Ayé:**

- `CCBT_ENABLE_ENCRYPTION`: Mú kí/pa ìpamọ́ (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: Ìpamọ́ ìpamọ́ (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: Ìwọ̀n bọ̀tùn DH (`768` tàbí `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: Yàn RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: Àtòjọ tí a pin pẹ̀lú kọ́mà (àpẹrẹ, `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: Gba padà aláìlẹ́kọ̀n (`true`/`false`)

**Àpẹrẹ Ṣètò:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**Àwọn Ìgbéyẹ̀wò Ààbò:**

1. **Ìbámu RC4**: A ṣe àtìlẹ́yìn RC4 fún ìbámu ṣùgbọ́n ó dẹ́rù ní kriptográfí. Lo AES fún ààbò tó ṣe dáadáa jùlọ bí ó ṣe ṣeé ṣe.
2. **Ìwọ̀n Bọ̀tùn DH**: Àwọn bọ̀tùn DH 768-bit pèsè ààbò tó tó fún ọ̀pọ̀lọpọ̀ ìlò. 1024-bit pèsè ààbò tó ṣe dáadáa jùlọ ṣùgbọ́n ó mú kí ìgbà ìgbàkọlé pọ̀ sí i.
3. **Àwọn Ìpamọ́ Ìpamọ́**:
   - `preferred`: Ó ṣe dáadáa jùlọ fún ìbámu - ó gbìyànjú ìpamọ́ ṣùgbọ́n ó padà ní ìwà rere
   - `required`: Ó ṣe dáadáa jùlọ ṣùgbọ́n ó lè ṣe àṣìṣe láti sopọ̀ pẹ̀lú peers tí kò ṣe àtìlẹ́yìn ìpamọ́
4. **Ìpa Iṣẹ́**: Ìpamọ́ mú kí ìgbàkọlé kéré pọ̀ sí i (~1-5% fún RC4, ~2-8% fún AES) ṣùgbọ́n ó mú kí ìpamọ́ ṣe dáadáa àti ó ràn lọ́wọ́ láti yẹra fún ìṣe ìgbàkọlé.

**Àwọn Àlàyé Ìgbéjáde:**

Ìgbéjáde ìpamọ́: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Àwọn Ìgbàkọlé Cipher: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Ìgbàkọlé Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### Ṣètò ML

Àwọn ṣètò ẹ̀rọ ìkọ́ni: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

Àpẹrẹ ṣètò ML: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Dashboard

Àwọn ṣètò dashboard: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

Àpẹrẹ ṣètò dashboard: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## Àwọn Onírúurú Ayé

Àwọn onírúurú ayé lo àkọ́lé `CCBT_` àti wọ́n tẹ̀lé ìlànà orúkọ ìgbàkọlé.

Àtẹ̀jáde: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

Ìlànà: `CCBT_<SECTION>_<OPTION>=<value>`

Àwọn Àpẹrẹ:
- Nẹ́tíwọ̀kì: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- Dísíkì: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- Ìlànà: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- Ìwádìí: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- Ìwòye: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- Àwọn Ìdíwọ̀n: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- Ààbò: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

Ìgbàkọlé àwọn onírúurú ayé: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## Ìlànà Ṣètò

Ìlànà ṣètò àti ìjẹ́rìí: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

Ìlànà ṣàlàyé:
- Àwọn irú àgbègbè àti àwọn ìdínkù
- Àwọn àkọ́kọ́ ìye
- Àwọn ìlànà ìjẹ́rìí
- Ìwé ìtúpalẹ̀

## Àwọn Agbára Ṣètò

Àwọn agbára ṣètò àti ìwádìí ẹ̀yà: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## Àwọn Àpẹrẹ Ṣètò

Àwọn àpẹrẹ ṣètò tí a ṣàlàyé tẹ́lẹ̀: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

Àwọn àpẹrẹ fún:
- Ìgbékalẹ̀ iṣẹ́ tó ga
- Ìgbékalẹ̀ ohun tí ó kéré
- Ìgbékalẹ̀ tí ó ṣe dáadáa fún ààbò
- Ìgbékalẹ̀ ìdàgbàsókè

## Àwọn Àpẹrẹ Ṣètò

Àwọn àpẹrẹ ṣètò wà ní àwọn fóldà [examples/](examples/):

- Ṣètò àkọ́kọ́: [example-config-basic.toml](examples/example-config-basic.toml)
- Ṣètò tó ga: [example-config-advanced.toml](examples/example-config-advanced.toml)
- Ṣètò iṣẹ́: [example-config-performance.toml](examples/example-config-performance.toml)
- Ṣètò ààbò: [example-config-security.toml](examples/example-config-security.toml)

## Ìgbàkọlé Tútù

Àtìlẹ́yìn ìgbàkọlé tútù ṣètò: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

Ìgbàkọlé ṣètò ṣe àtìlẹ́yìn ìgbàkọlé àwọn àyípadà láìsí ìtúnṣe oníbára.

## Ìgbàkọlé Ṣètò

Àwọn ohun èlò ìgbàkọlé ṣètò: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

Àwọn ohun èlò fún ìgbàkọlé láàárín àwọn ìgbàkọlé ṣètò.

## Ìgbàkọlé Ṣètò Backup àti Ìyàtọ̀

Àwọn ohun èlò ìṣàkóso ṣètò:
- Backup: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Ìyàtọ̀: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## Ṣètò Àdàkọ

Àtìlẹ́yìn ṣètò àdàkọ: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## Àwọn Ìmọ̀ràn àti Àwọn Ìlànà Tó Ṣe Dáadáa

### Ìtúnṣe Iṣẹ́

- Mú kí `disk.write_buffer_kib` pọ̀ sí i fún àwọn kíkọ ìlànà tó tóbi: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Mú kí `direct_io` ṣiṣẹ́ lórí Linux/NVMe fún ìgbàkọlé kíkọ tó ṣe dáadáa jùlọ: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- Ṣètò `network.pipeline_depth` àti `network.block_size_kib` fún nẹ́tíwọ̀kì rẹ: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### Ìtúnṣe Ohun

- Ṣètò `disk.hash_workers` nípa àwọn cores CPU: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- Ṣètò `disk.cache_size_mb` nípa RAM tí ó wà: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- Ṣètò `network.max_global_peers` nípa bandwidth: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### Ṣètò Nẹ́tíwọ̀kì

- Ṣètò àwọn ìgbà ìparí nípa àwọn ìpamọ́ nẹ́tíwọ̀kì: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Mú kí/pa àwọn ìlànà bí ó ṣe nilo: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Ṣètò àwọn ìdíwọ̀n ìyára bí ó ṣe tọ́: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

Fún ìtúnṣe iṣẹ́ tí ó ṣe dáadáa, wo [Ìtọ́sọ́nà Ìtúnṣe Iṣẹ́](performance.md).






ccBitTorrent lo ìgbàkọlé ṣètò tí ó ṣe dáadáa pẹ̀lú àtìlẹ́yìn TOML, ìjẹ́rìí, ìgbàkọlé tútù, àti ìgbàkọlé ìgbàkọlé láti ọ̀pọ̀lọpọ̀ orísun.

Ìgbàkọlé ṣètò: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## Àwọn Orísun Ṣètò àti Ìpàtàkì

A gba ṣètò ní ìlànà yìí (àwọn orísun tókàn yóò pa àwọn àkọ́kọ́):

1. **Àwọn Àkọ́kọ́**: Àwọn àkọ́kọ́ tí ó ṣe dáadáa tí ó wà nínú láti [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **Fàìlì Ṣètò**: `ccbt.toml` ní àwọn fóldà lọ́wọ́lọ́wọ́ tàbí `~/.config/ccbt/ccbt.toml`. Wo: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **Àwọn Onírúurú Ayé**: Àwọn onírúurú pẹ̀lú àkọ́lé `CCBT_*`. Wo: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **Àwọn Àgbéyẹ̀wò CLI**: Àwọn ìyípadà ìlànà àṣẹ. Wo: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **Fún Torrent**: Àwọn ṣètò torrent aládàá (ẹ̀yà ìwájú)

Ìgbàkọlé ṣètò: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## Fàìlì Ṣètò

### Ṣètò Àkọ́kọ́

Wo fàìlì ṣètò àkọ́kọ́: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

A ṣètò ṣètò sí àwọn apá:

### Ṣètò Nẹ́tíwọ̀kì

Àwọn ṣètò nẹ́tíwọ̀kì: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- Àwọn ìdíwọ̀n ìsopọ̀: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- Ìgbàkọlé ìbéèrè: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- Ìtúnṣe socket: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- Àwọn ìgbà ìparí: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Àwọn ṣètò gbọ́: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- Àwọn ìlànà gbigbé: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Àwọn ìdíwọ̀n ìyára: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- Ìlànà ìdínkù: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- Àwọn ṣètò tracker: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

Àpẹrẹ ṣètò nẹ́tíwọ̀kì: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Dísíkì

Àwọn ṣètò dísíkì: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- Ìpèsè tẹ́lẹ̀: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- Ìtúnṣe kíkọ: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- Ìjẹ́rìí hash: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- Ìgbàkọlé I/O: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- Àwọn ṣètò tó ga: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- Àwọn ṣètò iṣẹ́ ìpamọ́: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: Ìdíwọ̀n ìwọ̀n fàìlì tó pọ̀ jùlọ ní MB fún iṣẹ́ ìpamọ́ (0 tàbí None = àìní ìdíwọ̀n, tó pọ̀ jùlọ 1048576 = 1TB). Ó dènà kíkọ dísíkì àìní ìdíwọ̀n nígbà ìdánwò àti a lè ṣètò fún lilo ìgbéjáde.
- Àwọn ṣètò àkíyèsí: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

Àpẹrẹ ṣètò dísíkì: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Ìlànà

Àwọn ṣètò ìlànà: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- Ìyàn apá: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- Ìlànà tó ga: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- Àwọn ìpàtàkì apá: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

Àpẹrẹ ṣètò ìlànà: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Ìwádìí

Àwọn ṣètò ìwádìí: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- Àwọn ṣètò DHT: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- Àwọn ṣètò PEX: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- Àwọn ṣètò tracker: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Ìgbà ìsọrọ̀ tracker ní àwọn ìṣẹ́jú (àkọ́kọ́: 1800.0, ààlà: 60.0-86400.0)
  - `tracker_scrape_interval`: Ìgbà ìgbàkọlé tracker ní àwọn ìṣẹ́jú fún ìgbàkọlé ìgbàkọlé (àkọ́kọ́: 3600.0, ààlà: 60.0-86400.0)
  - `tracker_auto_scrape`: Ṣe ìgbàkọlé àìdánilójú pẹ̀lú trackers nígbà tí a fi torrents sí i (BEP 48) (àkọ́kọ́: false)
  - Àwọn onírúurú ayé: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

Àpẹrẹ ṣètò ìwádìí: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Àwọn Ìdíwọ̀n

Àwọn ìdíwọ̀n ìyára: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- Àwọn ìdíwọ̀n àgbáyé: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- Àwọn ìdíwọ̀n torrent: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- Àwọn ìdíwọ̀n peer: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- Àwọn ṣètò àgbékalẹ̀: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

Àpẹrẹ ṣètò àwọn ìdíwọ̀n: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Ìwòye

Àwọn ṣètò ìwòye: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- Ìkọ̀wé: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- Àwọn ìwọ̀n: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- Ìtọ́kàsọ̀ àti àwọn ìkìlọ̀: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

Àpẹrẹ ṣètò ìwòye: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Ààbò

Àwọn ṣètò ààbò: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

Àpẹrẹ ṣètò ààbò: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### Ṣètò Ìpamọ́

ccBitTorrent ṣe àtìlẹ́yìn BEP 3 Message Stream Encryption (MSE) àti Protocol Encryption (PE) fún àwọn ìsopọ̀ peer ààbò.

**Àwọn Ṣètò Ìpamọ́:**

- `enable_encryption` (bool, àkọ́kọ́: `false`): Mú kí àtìlẹ́yìn ìpamọ́ ìlànà ṣiṣẹ́
- `encryption_mode` (str, àkọ́kọ́: `"preferred"`): Ìpamọ́ ìpamọ́
  - `"disabled"`: Kò sí ìpamọ́ (àwọn ìsopọ̀ aláìlẹ́kọ̀n nìkan)
  - `"preferred"`: Gbìyànjú ìpamọ́, padà sí aláìlẹ́kọ̀n tí kò bá wà
  - `"required"`: Ìpamọ́ jẹ́ dandan, ìsopọ̀ bá jẹ́ tí ìpamọ́ kò bá wà
- `encryption_dh_key_size` (int, àkọ́kọ́: `768`): Ìwọ̀n bọ̀tùn Diffie-Hellman ní bits (768 tàbí 1024)
- `encryption_prefer_rc4` (bool, àkọ́kọ́: `true`): Yàn cipher RC4 fún ìbámu pẹ̀lú àwọn oníbára àtijọ́
- `encryption_allowed_ciphers` (list[str], àkọ́kọ́: `["rc4", "aes"]`): Àwọn irú cipher tí a gba
  - `"rc4"`: Cipher ìgbàkọlé RC4 (ó ṣe dáadáa jùlọ)
  - `"aes"`: Cipher AES ní ìpamọ́ CFB (ó ṣe dáadáa jùlọ)
  - `"chacha20"`: Cipher ChaCha20 (kò tíì ṣe ìgbéjáde)
- `encryption_allow_plain_fallback` (bool, àkọ́kọ́: `true`): Gba padà sí ìsopọ̀ aláìlẹ́kọ̀n tí ìpamọ́ bá ṣe àṣìṣe (ó ṣe nìkan nígbà tí `encryption_mode` jẹ́ `"preferred"`)

**Àwọn Onírúurú Ayé:**

- `CCBT_ENABLE_ENCRYPTION`: Mú kí/pa ìpamọ́ (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: Ìpamọ́ ìpamọ́ (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: Ìwọ̀n bọ̀tùn DH (`768` tàbí `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: Yàn RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: Àtòjọ tí a pin pẹ̀lú kọ́mà (àpẹrẹ, `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: Gba padà aláìlẹ́kọ̀n (`true`/`false`)

**Àpẹrẹ Ṣètò:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**Àwọn Ìgbéyẹ̀wò Ààbò:**

1. **Ìbámu RC4**: A ṣe àtìlẹ́yìn RC4 fún ìbámu ṣùgbọ́n ó dẹ́rù ní kriptográfí. Lo AES fún ààbò tó ṣe dáadáa jùlọ bí ó ṣe ṣeé ṣe.
2. **Ìwọ̀n Bọ̀tùn DH**: Àwọn bọ̀tùn DH 768-bit pèsè ààbò tó tó fún ọ̀pọ̀lọpọ̀ ìlò. 1024-bit pèsè ààbò tó ṣe dáadáa jùlọ ṣùgbọ́n ó mú kí ìgbà ìgbàkọlé pọ̀ sí i.
3. **Àwọn Ìpamọ́ Ìpamọ́**:
   - `preferred`: Ó ṣe dáadáa jùlọ fún ìbámu - ó gbìyànjú ìpamọ́ ṣùgbọ́n ó padà ní ìwà rere
   - `required`: Ó ṣe dáadáa jùlọ ṣùgbọ́n ó lè ṣe àṣìṣe láti sopọ̀ pẹ̀lú peers tí kò ṣe àtìlẹ́yìn ìpamọ́
4. **Ìpa Iṣẹ́**: Ìpamọ́ mú kí ìgbàkọlé kéré pọ̀ sí i (~1-5% fún RC4, ~2-8% fún AES) ṣùgbọ́n ó mú kí ìpamọ́ ṣe dáadáa àti ó ràn lọ́wọ́ láti yẹra fún ìṣe ìgbàkọlé.

**Àwọn Àlàyé Ìgbéjáde:**

Ìgbéjáde ìpamọ́: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Àwọn Ìgbàkọlé Cipher: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Ìgbàkọlé Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### Ṣètò ML

Àwọn ṣètò ẹ̀rọ ìkọ́ni: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

Àpẹrẹ ṣètò ML: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### Ṣètò Dashboard

Àwọn ṣètò dashboard: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

Àpẹrẹ ṣètò dashboard: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## Àwọn Onírúurú Ayé

Àwọn onírúurú ayé lo àkọ́lé `CCBT_` àti wọ́n tẹ̀lé ìlànà orúkọ ìgbàkọlé.

Àtẹ̀jáde: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

Ìlànà: `CCBT_<SECTION>_<OPTION>=<value>`

Àwọn Àpẹrẹ:
- Nẹ́tíwọ̀kì: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- Dísíkì: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- Ìlànà: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- Ìwádìí: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- Ìwòye: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- Àwọn Ìdíwọ̀n: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- Ààbò: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

Ìgbàkọlé àwọn onírúurú ayé: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## Ìlànà Ṣètò

Ìlànà ṣètò àti ìjẹ́rìí: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

Ìlànà ṣàlàyé:
- Àwọn irú àgbègbè àti àwọn ìdínkù
- Àwọn àkọ́kọ́ ìye
- Àwọn ìlànà ìjẹ́rìí
- Ìwé ìtúpalẹ̀

## Àwọn Agbára Ṣètò

Àwọn agbára ṣètò àti ìwádìí ẹ̀yà: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## Àwọn Àpẹrẹ Ṣètò

Àwọn àpẹrẹ ṣètò tí a ṣàlàyé tẹ́lẹ̀: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

Àwọn àpẹrẹ fún:
- Ìgbékalẹ̀ iṣẹ́ tó ga
- Ìgbékalẹ̀ ohun tí ó kéré
- Ìgbékalẹ̀ tí ó ṣe dáadáa fún ààbò
- Ìgbékalẹ̀ ìdàgbàsókè

## Àwọn Àpẹrẹ Ṣètò

Àwọn àpẹrẹ ṣètò wà ní àwọn fóldà [examples/](examples/):

- Ṣètò àkọ́kọ́: [example-config-basic.toml](examples/example-config-basic.toml)
- Ṣètò tó ga: [example-config-advanced.toml](examples/example-config-advanced.toml)
- Ṣètò iṣẹ́: [example-config-performance.toml](examples/example-config-performance.toml)
- Ṣètò ààbò: [example-config-security.toml](examples/example-config-security.toml)

## Ìgbàkọlé Tútù

Àtìlẹ́yìn ìgbàkọlé tútù ṣètò: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

Ìgbàkọlé ṣètò ṣe àtìlẹ́yìn ìgbàkọlé àwọn àyípadà láìsí ìtúnṣe oníbára.

## Ìgbàkọlé Ṣètò

Àwọn ohun èlò ìgbàkọlé ṣètò: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

Àwọn ohun èlò fún ìgbàkọlé láàárín àwọn ìgbàkọlé ṣètò.

## Ìgbàkọlé Ṣètò Backup àti Ìyàtọ̀

Àwọn ohun èlò ìṣàkóso ṣètò:
- Backup: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Ìyàtọ̀: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## Ṣètò Àdàkọ

Àtìlẹ́yìn ṣètò àdàkọ: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## Àwọn Ìmọ̀ràn àti Àwọn Ìlànà Tó Ṣe Dáadáa

### Ìtúnṣe Iṣẹ́

- Mú kí `disk.write_buffer_kib` pọ̀ sí i fún àwọn kíkọ ìlànà tó tóbi: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- Mú kí `direct_io` ṣiṣẹ́ lórí Linux/NVMe fún ìgbàkọlé kíkọ tó ṣe dáadáa jùlọ: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- Ṣètò `network.pipeline_depth` àti `network.block_size_kib` fún nẹ́tíwọ̀kì rẹ: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### Ìtúnṣe Ohun

- Ṣètò `disk.hash_workers` nípa àwọn cores CPU: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- Ṣètò `disk.cache_size_mb` nípa RAM tí ó wà: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- Ṣètò `network.max_global_peers` nípa bandwidth: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### Ṣètò Nẹ́tíwọ̀kì

- Ṣètò àwọn ìgbà ìparí nípa àwọn ìpamọ́ nẹ́tíwọ̀kì: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- Mú kí/pa àwọn ìlànà bí ó ṣe nilo: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- Ṣètò àwọn ìdíwọ̀n ìyára bí ó ṣe tọ́: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

Fún ìtúnṣe iṣẹ́ tí ó ṣe dáadáa, wo [Ìtọ́sọ́nà Ìtúnṣe Iṣẹ́](performance.md).




























































































































































































