# Konfigurazio Gida

ccBitTorrent-ek TOML euskarria, baliozkotzea, karga berri beroa eta hainbat iturritik karga hierarkikoa dituen konfigurazio sistema osatu bat erabiltzen du.

Konfigurazio sistema: [ccbt/config/config.py:ConfigManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L40)

## Konfigurazio Iturriak eta Lehentasuna

Konfigurazioa ordena honetan kargatzen da (ondorengo iturriek aurrekoak gainidazten dituzte):

1. **Lehenetsiak**: [ccbt/models.py:Config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py) barneko lehenetsi zentzudunak
2. **Konfigurazio Fitxategia**: `ccbt.toml` uneko direktorioan edo `~/.config/ccbt/ccbt.toml`. Ikusi: [ccbt/config/config.py:_find_config_file](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L55)
3. **Ingurune Aldagaiak**: `CCBT_*` aurrizkidun aldagaiak. Ikusi: [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
4. **CLI Argumentuak**: Komando-lerroko gainidazketak. Ikusi: [ccbt/cli/overrides.py:apply_cli_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/overrides.py#L1) {#cli-overrides}
5. **Torrent Bakoitzeko - Lehenetsiak**: Torrent bakoitzeko aukera global lehenetsiak. Ikusi [Torrent Bakoitzeko Konfigurazioa](#per-torrent-configuration) atala
6. **Torrent Bakoitzeko - Gainidazketak**: Torrent banakako ezarpenak (CLI, TUI edo programazioz definituta)

Konfigurazio karga: [ccbt/config/config.py:_load_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L76)

### Windows Bide Ebazpena {#daemon-home-dir}

**KRITIKOA**: Erabili `_get_daemon_home_dir()` laguntzailea `ccbt/daemon/daemon_manager.py`-tik deabruarekin lotutako bide guztietarako.

**Zergatik**: Windows-ek `Path.home()` edo `os.path.expanduser("~")` modu desberdinean ebaztu ditzake prozesu desberdinetan, bereziki erabiltzaile izenetan espazioak daudenean.

**Eredua**: Laguntzaileak hainbat metodo saiatzen ditu (`expanduser`, `USERPROFILE`, `HOME`, `Path.home()`) eta `Path.resolve()` erabiltzen du bide kanonikorako.

**Erabilera**: Erabili beti laguntzailea `Path.home()` edo `os.path.expanduser("~")` zuzenean erabili beharrean deabruaren PID fitxategiak, egoera direktorioak, konfigurazio fitxategiak.

**Kaltetutako fitxategiak**: `DaemonManager`, `StateManager`, `IPCClient`, deabruaren PID fitxategia edo egoera irakurtzen/idazten duen edozein kode.

**Emaitza**: Ziurtatzen du deabruak eta CLI-k bide kanoniko bera erabiltzen dutela, detekzio hutsegiteak ekidituz.

Inplementazioa: [ccbt/daemon/daemon_manager.py:_get_daemon_home_dir](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/daemon_manager.py#L25)

## Konfigurazio Fitxategia

### Konfigurazio Lehenetsia

Ikusi konfigurazio lehenetsi fitxategia: [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

Konfigurazioa ataletan antolatuta dago:

### Sare Konfigurazioa

Sare ezarpenak: [ccbt.toml:4-43](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L4-L43)

- Konexio mugak: [ccbt.toml:6-8](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6-L8)
- Eskaera hoditeria: [ccbt.toml:11-14](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L11-L14)
- Socket doikuntza: [ccbt.toml:17-19](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L17-L19)
- Denbora-mugak: [ccbt.toml:22-26](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22-L26)
- Entzun ezarpenak: [ccbt.toml:29-31](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L29-L31)
- Garraio protokoloak: [ccbt.toml:34-36](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L34-L36)
- Abiadura mugak: [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L39-L42)
- Itotze estrategia: [ccbt.toml:45-47](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L45-L47)
- Tracker ezarpenak: [ccbt.toml:50-54](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L50-L54)

Sare konfigurazio modelo: [ccbt/models.py:NetworkConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Disko Konfigurazioa

Disko ezarpenak: [ccbt.toml:57-96](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L57-L96)

- Aurre-esleipena: [ccbt.toml:59-60](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L59-L60)
- Idazketa optimizazioa: [ccbt.toml:63-67](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63-L67)
- Hash baliozkotzea: [ccbt.toml:70-73](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70-L73)
- I/O hariztatzea: [ccbt.toml:76-78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L76-L78)
- Ezarpen aurreratuak: [ccbt.toml:81-85](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L81-L85)
- Biltegiratze zerbitzu ezarpenak: [ccbt.toml:87-89](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: Biltegiratze zerbitzuarentzako fitxategi tamaina muga maximoa MB-tan (0 edo None = mugagabea, gehienez 1048576 = 1TB). Probetan disko idazketa mugagabeak eragozten ditu eta produkzio erabilerarako konfiguratu daiteke.
- Kontrol-puntu ezarpenak: [ccbt.toml:91-96](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L91-L96)

Disko konfigurazio modelo: [ccbt/models.py:DiskConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Estrategia Konfigurazioa

Estrategia ezarpenak: [ccbt.toml:99-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L99-L114)

- Pieza hautaketa: [ccbt.toml:101-104](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101-L104)
- Estrategia aurreratua: [ccbt.toml:107-109](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L107-L109)
- Pieza lehentasunak: [ccbt.toml:112-113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L112-L113)

Estrategia konfigurazio modelo: [ccbt/models.py:StrategyConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Aurkikuntza Konfigurazioa

Aurkikuntza ezarpenak: [ccbt.toml:116-136](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L116-L136)

- DHT ezarpenak: [ccbt.toml:118-125](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L118-L125)
- PEX ezarpenak: [ccbt.toml:128-129](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L128-L129)
- Tracker ezarpenak: [ccbt.toml:132-135](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Tracker iragarpen tartea segundotan (lehenetsia: 1800.0, tartea: 60.0-86400.0)
  - `tracker_scrape_interval`: Tracker scrape tartea segundotan scrape periodikorako (lehenetsia: 3600.0, tartea: 60.0-86400.0)
  - `tracker_auto_scrape`: Automatikoki scrape egin trackerrekin torrent gehitzean (BEP 48) (lehenetsia: false)
  - Ingurune aldagaiak: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

Aurkikuntza konfigurazio modelo: [ccbt/models.py:DiscoveryConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Muga Konfigurazioa

Abiadura mugak: [ccbt.toml:138-152](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L138-L152)

- Muga globalak: [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140-L141)
- Torrent bakoitzeko mugak: [ccbt.toml:144-145](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L144-L145)
- Peer bakoitzeko mugak: [ccbt.toml:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L148)
- Programatzaile ezarpenak: [ccbt.toml:151](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L151)

Muga konfigurazio modelo: [ccbt/models.py:LimitsConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Behatzeko Konfigurazioa

Behatzeko ezarpenak: [ccbt.toml:154-171](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L154-L171)

- Erregistroa: [ccbt.toml:156-160](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L156-L160)
- Metrikak: [ccbt.toml:163-165](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L163-L165)
- Jarraipena eta alertak: [ccbt.toml:168-170](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L168-L170)

Behatzeko konfigurazio modelo: [ccbt/models.py:ObservabilityConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Optimizazio Konfigurazioa {#optimization-profile}

Optimizazio profileek kasu erabilera desberdinetarako aurrez konfiguratutako ezarpenak eskaintzen dituzte.

::: ccbt.models.OptimizationProfile
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3

**Eskuragarri dauden Profileak:**
- `BALANCED`: Errendimendu eta baliabide erabilera orekatua (lehenetsia)
- `SPEED`: Deskarga abiadura maximoa
- `EFFICIENCY`: Banda-zabalera eraginkortasun maximoa
- `LOW_RESOURCE`: Baliabide baxuko sistemetarako optimizatua
- `CUSTOM`: Erabili ezarpen pertsonalizatuak profil gainidazketarik gabe

Optimizazio konfigurazio modelo: [ccbt/models.py:OptimizationConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Segurtasun Konfigurazioa

Segurtasun ezarpenak: [ccbt.toml:173-178](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L173-L178)

Segurtasun konfigurazio modelo: [ccbt/models.py:SecurityConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

#### Enkriptazio Konfigurazioa

ccBitTorrent-ek BEP 3 Message Stream Encryption (MSE) eta Protocol Encryption (PE) onartzen ditu peer konexio seguruetarako.

**Enkriptazio Ezarpenak:**

- `enable_encryption` (bool, lehenetsia: `false`): Gaitu protokolo enkriptazio euskarria
- `encryption_mode` (str, lehenetsia: `"preferred"`): Enkriptazio modua
  - `"disabled"`: Enkriptaziorik ez (konexio soilak bakarrik)
  - `"preferred"`: Saiatu enkriptazioa, erori soilera eskuragarri ez bada
  - `"required"`: Enkriptazioa beharrezkoa, konexioa huts egiten du enkriptazioa eskuragarri ez bada
- `encryption_dh_key_size` (int, lehenetsia: `768`): Diffie-Hellman gako tamaina bitetan (768 edo 1024)
- `encryption_prefer_rc4` (bool, lehenetsia: `true`): Lehentu RC4 zifratua bezero zaharrekin bateragarritasunerako
- `encryption_allowed_ciphers` (list[str], lehenetsia: `["rc4", "aes"]`): Onartutako zifratu motak
  - `"rc4"`: RC4 korronte zifratua (bateragarriena)
  - `"aes"`: AES zifratua CFB moduan (seguruagoa)
  - `"chacha20"`: ChaCha20 zifratua (oraindik ez da inplementatu)
- `encryption_allow_plain_fallback` (bool, lehenetsia: `true`): Baimendu erorketa konexio soilera enkriptazioak huts egiten badu (soilik aplikatzen da `encryption_mode` `"preferred"` denean)

**Ingurune Aldagaiak:**

- `CCBT_ENABLE_ENCRYPTION`: Gaitu/desgaitu enkriptazioa (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: Enkriptazio modua (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DH gako tamaina (`768` edo `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: Lehentu RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: Koma banandutako zerrenda (adib. `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: Baimendu erorketa soila (`true`/`false`)

**Konfigurazio Adibidea:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**Segurtasun Kontsiderazioak:**

1. **RC4 Bateragarritasuna**: RC4 bateragarritasunerako onartzen da baina kriptografikoki ahula da. Erabili AES segurtasun hobeagorako ahal den bezainbeste.
2. **DH Gako Tamaina**: 768 bit-eko DH gakoek erabilera kasu gehienetarako segurtasun nahikoa ematen dute. 1024 bit-ekoak segurtasun sendoagoa ematen dute baina esku-ukitu atzerapena handitzen dute.
3. **Enkriptazio Moduak**:
   - `preferred`: Bateragarritasunerako onena - saiatzen da enkriptazioa baina modu dotorean erortzen da
   - `required`: Seguruena baina enkriptazioa onartzen ez duten peerrekin konektatzean huts egin dezake
4. **Errendimendu Eragina**: Enkriptazioak gehikuntza minimoa gehitzen du (~1-5% RC4-rako, ~2-8% AES-rako) baina pribatutasuna hobetzen du eta trafiko moldaketari ihes egiten laguntzen du.

**Inplementazio Xehetasunak:**

Enkriptazio inplementazioa: [ccbt/security/encryption.py:EncryptionManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/encryption.py#L131)

- MSE Esku-ukitua: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/mse_handshake.py#L45)
- Zifratu Multzoak: [ccbt/security/ciphers/__init__.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman Trukea: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/dh_exchange.py)

### ML Konfigurazioa

Makina ikaskuntza ezarpenak: [ccbt.toml:180-183](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L180-L183)

ML konfigurazio modelo: [ccbt/models.py:MLConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Panel Konfigurazioa

Panel ezarpenak: [ccbt.toml:185-191](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L185-L191)

Panel konfigurazio modelo: [ccbt/models.py:DashboardConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

## Ingurune Aldagaiak

Ingurune aldagaiak `CCBT_` aurrizkia erabiltzen dute eta izendapen eskem hierarkiko bat jarraitzen dute.

Erreferentzia: [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)

Formatua: `CCBT_<SECTION>_<OPTION>=<value>`

Adibideak:
- Sarea: [env.example:10-58](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L10-L58)
- Diskoa: [env.example:62-102](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L62-L102)
- Estrategia: [env.example:106-121](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L106-L121)
- Aurkikuntza: [env.example:125-141](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L125-L141)
- Behatzeko: [env.example:145-162](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L145-L162)
- Mugak: [env.example:166-180](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L166-L180)
- Segurtasuna: [env.example:184-189](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L193-L196)

Ingurune aldagai parsing: [ccbt/config/config.py:_get_env_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)

## Konfigurazio Eskema

Konfigurazio eschema eta baliozkotzea: [ccbt/config/config_schema.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_schema.py)

Eskemak definitzen du:
- Eremu motak eta murrizketak
- Lehenetsi balioak
- Baliozkotze arauak
- Dokumentazioa

## Konfigurazio Ahalmenak

Konfigurazio ahalmenak eta ezaugarri detekzioa: [ccbt/config/config_capabilities.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_capabilities.py)

## Konfigurazio Txantiloiak

Aurredefinitutako konfigurazio txantiloiak: [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Txantiloiak:
- Errendimendu altuko konfigurazioa
- Baliabide baxuko konfigurazioa
- Segurtasun zentratutako konfigurazioa
- Garapen konfigurazioa

## Konfigurazio Adibideak

Konfigurazio adibideak [examples/](examples/) direktorioan eskuragarri daude:

- Konfigurazio oinarrizkoa: [example-config-basic.toml](examples/example-config-basic.toml)
- Konfigurazio aurreratua: [example-config-advanced.toml](examples/example-config-advanced.toml)
- Errendimendu konfigurazioa: [example-config-performance.toml](examples/example-config-performance.toml)
- Segurtasun konfigurazioa: [example-config-security.toml](examples/example-config-security.toml)

## Karga Berri Beroa

Konfigurazio karga berri bero euskarria: [ccbt/config/config.py:ConfigManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L40)

Konfigurazio sistemak bezeroa berrabiarazi gabe aldaketak berriro kargatzea onartzen du.

## Konfigurazio Migrazioa

Konfigurazio migrazioa tresnak: [ccbt/config/config_migration.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_migration.py)

Konfigurazio bertsioen arteko migratzeko tresnak.

## Konfigurazio Babeskopia eta Diferentzia

Konfigurazio kudeaketa tresnak:
- Babeskopia: [ccbt/config/config_backup.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_backup.py)
- Diferentzia: [ccbt/config/config_diff.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_diff.py)

## Konfigurazio Baldintzatua

Konfigurazio baldintzatu euskarria: [ccbt/config/config_conditional.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_conditional.py)

## Torrent Bakoitzeko Konfigurazioa

Torrent bakoitzeko konfigurazioak ezarpen globalak torrent banakakoentzat gainidaztea ahalbidetzen du. Ezarpen hauek kontrol puntuetan eta deabruaren egoeran gordetzen dira, berrabiarazteetatik biziraun dutela ziurtatuz.

### Torrent Bakoitzeko Aukerak

Torrent bakoitzeko aukerak `AsyncTorrentSession.options`-en gordetzen dira eta honakoak barne ditzake:

- `piece_selection`: Pieza hautaketa estrategia (`"rarest_first"`, `"sequential"`, `"random"`)
- `streaming_mode`: Gaitu streaming modua multimedia fitxategientzat (`true`/`false`)
- `sequential_window_size`: Deskarga sekuentzial leihoaren tamaina (byte)
- `max_peers_per_torrent`: Torrent honentzat peer kopuru maximoa
- Beharrezko aukera pertsonalizatuak

Inplementazioa: [ccbt/session/session.py:AsyncTorrentSession](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L63)

### Torrent Bakoitzeko Abiadura Mugak

Abiadura mugak torrent bakoitzeko ezar daitezke `AsyncSessionManager.set_rate_limits()` erabiliz:

- `down_kib`: Deskarga abiadura muga KiB/s-tan (0 = mugagabea)
- `up_kib`: Igo abiadura muga KiB/s-tan (0 = mugagabea)

Inplementazioa: [ccbt/session/session.py:set_rate_limits](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L1735)

### Torrent Bakoitzeko Global Lehenetsiak

Torrent bakoitzeko lehenetsi aukerak ezar ditzakezu zure `ccbt.toml` fitxategian:

```toml
[per_torrent_defaults]
piece_selection = "rarest_first"
streaming_mode = false
max_peers_per_torrent = 50
sequential_window_size = 10485760  # 10 MiB
```

Lehenetsi hauek torrent bakoitzeko aukeretan fusionatzen dira torrent saioa sortzen denean.

Modeloa: [ccbt/models.py:PerTorrentDefaultsConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Torrent Bakoitzeko Aukerak Ezarri

#### CLI Bidez

```bash
# Ezarri torrent bakoitzeko aukera
uv run btbt torrent config set <info_hash> piece_selection sequential

# Ezarri abiadura mugak (saio kudeatzailearen bidez)
# Oharra: Abiadura mugak normalean TUI edo programazioz ezartzen dira
```

Ikusi [CLI Erreferentzia](btbt-cli.md#per-torrent-configuration) CLI dokumentazio osoagatik.

#### TUI Bidez

Terminal panelak interfaze interaktiboa eskaintzen du torrent bakoitzeko konfigurazioa kudeatzeko:

- Nabigatu torrent konfigurazio pantailara
- Editatu aukerak eta abiadura mugak
- Aldaketak automatikoki gordetzen dira kontrol puntuetan

Inplementazioa: [ccbt/interface/screens/config/torrent_config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/screens/config/torrent_config.py)

#### Programazioz

```python
# Ezarri torrent bakoitzeko aukerak
torrent_session.options["piece_selection"] = "sequential"
torrent_session.options["streaming_mode"] = True
torrent_session._apply_per_torrent_options()

# Ezarri abiadura mugak
await session_manager.set_rate_limits(info_hash_hex, down_kib=100, up_kib=50)
```

### Iraunkortasuna

Torrent bakoitzeko konfigurazioa honetan gordetzen da:

1. **Kontrol Puntuak**: Automatikoki gordetzen dira kontrol puntuak sortzen direnean. Kontrol puntutik berrekin denean berreskuratzen dira.
   - Modeloa: [ccbt/models.py:TorrentCheckpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py#L2017)
   - Gorde: [ccbt/session/checkpointing.py:save_checkpoint_state](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/checkpointing.py)
   - Kargatu: [ccbt/session/session.py:_resume_from_checkpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L947)

2. **Deabruaren Egoera**: Gordetzen da deabruaren egoera gordetzen denean. Berreskuratzen da deabrua berrabiarazten denean.
   - Modeloa: [ccbt/daemon/state_models.py:TorrentState](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/state_models.py)
   - Gorde: [ccbt/daemon/state_manager.py:_build_state](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/state_manager.py#L212)
   - Kargatu: [ccbt/daemon/main.py:_restore_torrent_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/main.py#L29)

## Aholkuak eta Praktika Onenak

### Errendimendu Doikuntza

- Handitu `disk.write_buffer_kib` idazketa sekuentzial handietarako: [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L64)
- Gaitu `direct_io` Linux/NVMe-n idazketa errendimendua hobetzeko: [ccbt.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L81)
- Doitu `network.pipeline_depth` eta `network.block_size_kib` zure sarearako: [ccbt.toml:11-13](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L11-L13)

### Baliabide Optimizazioa

- Doitu `disk.hash_workers` CPU nukleoetan oinarrituta: [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70)
- Konfiguratu `disk.cache_size_mb` eskuragarri dagoen RAM-an oinarrituta: [ccbt.toml:78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L78)
- Ezarri `network.max_global_peers` banda-zabaleran oinarrituta: [ccbt.toml:6](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6)

### Sare Konfigurazioa

- Konfiguratu denbora-mugak sare baldintzetan oinarrituta: [ccbt.toml:22-26](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22-L26)
- Gaitu/desgaitu protokoloak behar bezala: [ccbt.toml:34-36](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L34-L36)
- Ezarri abiadura mugak egoki: [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L39-L42)

Errendimendu doikuntza xehatuagatik, ikusi [Errendimendu Doikuntza Gida](performance.md).
