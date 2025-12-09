# ترتیب گائیڈ

ccBitTorrent TOML سپورٹ، تصدیق، ہاٹ-ری لوڈ، اور متعدد ذرائع سے ہائرارکیکل لوڈنگ کے ساتھ ایک جامع ترتیب کا نظام استعمال کرتا ہے۔

ترتیب کا نظام: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## ترتیب کے ذرائع اور ترجیح

ترتیب اس ترتیب میں لوڈ ہوتی ہے (بعد کے ذرائع پہلے والوں کو اوور رائیڈ کرتے ہیں):

1. **ڈیفالٹ**: [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) سے بلٹ-ان سمجھدار ڈیفالٹ
2. **ترتیب فائل**: موجودہ ڈائریکٹری یا `~/.config/ccbt/ccbt.toml` میں `ccbt.toml`۔ دیکھیں: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **ماحولیاتی متغیرات**: `CCBT_*` پریفکس والے متغیرات۔ دیکھیں: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI دلائل**: کمانڈ-لائن اوور رائیڈز۔ دیکھیں: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **فی-ٹورنٹ**: انفرادی ٹورنٹ سیٹنگز (مستقبل کی خصوصیت)

ترتیب لوڈنگ: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## ترتیب فائل

### ڈیفالٹ ترتیب

ڈیفالٹ ترتیب فائل دیکھیں: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

ترتیب حصوں میں منظم ہے:

### نیٹ ورک ترتیب

نیٹ ورک سیٹنگز: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- کنکشن کی حدیں: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- درخواست پائپ لائن: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- ساکٹ ٹیوننگ: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- ٹائم آؤٹس: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- سننے کی سیٹنگز: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- ٹرانسپورٹ پروٹوکولز: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- شرح کی حدیں: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- چوکنگ حکمت عملی: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- ٹریکر سیٹنگز: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

نیٹ ورک ترتیب ماڈل: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ڈسک ترتیب

ڈسک سیٹنگز: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- پری-الوکیشن: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- لکھنے کی بہتری: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- ہیش تصدیق: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O تھریڈنگ: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- اعلیٰ درجے کی سیٹنگز: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- اسٹوریج سروس سیٹنگز: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: اسٹوریج سروس کے لیے MB میں زیادہ سے زیادہ فائل سائز کی حد (0 یا None = لامحدود، زیادہ سے زیادہ 1048576 = 1TB)۔ ٹیسٹنگ کے دوران لامحدود ڈسک لکھنے کو روکتا ہے اور پروڈکشن استعمال کے لیے ترتیب دیا جا سکتا ہے۔
- چیک پوائنٹ سیٹنگز: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

ڈسک ترتیب ماڈل: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### حکمت عملی ترتیب

حکمت عملی سیٹنگز: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- ٹکڑا انتخاب: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- اعلیٰ درجے کی حکمت عملی: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- ٹکڑا ترجیحات: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

حکمت عملی ترتیب ماڈل: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### دریافت ترتیب

دریافت سیٹنگز: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT سیٹنگز: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX سیٹنگز: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- ٹریکر سیٹنگز: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: سیکنڈ میں ٹریکر اعلان وقفہ (ڈیفالٹ: 1800.0, حد: 60.0-86400.0)
  - `tracker_scrape_interval`: دورانیہ سکریپنگ کے لیے سیکنڈ میں ٹریکر سکریپ وقفہ (ڈیفالٹ: 3600.0, حد: 60.0-86400.0)
  - `tracker_auto_scrape`: torrents شامل ہونے پر خودکار طور پر trackers کو سکریپ کریں (BEP 48) (ڈیفالٹ: false)
  - ماحولیاتی متغیرات: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

دریافت ترتیب ماڈل: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### حدیں ترتیب

شرح کی حدیں: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- عالمی حدیں: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- فی-ٹورنٹ حدیں: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- فی-پیئر حدیں: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- شیڈولر سیٹنگز: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

حدیں ترتیب ماڈل: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### مشاہدہ ترتیب

مشاہدہ سیٹنگز: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- لاگنگ: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- میٹرکس: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- ٹریسنگ اور الرٹس: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

مشاہدہ ترتیب ماڈل: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### سیکیورٹی ترتیب

سیکیورٹی سیٹنگز: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

سیکیورٹی ترتیب ماڈل: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### Encryption ترتیب

ccBitTorrent محفوظ peer کنکشنز کے لیے BEP 3 Message Stream Encryption (MSE) اور Protocol Encryption (PE) کو سپورٹ کرتا ہے۔

**Encryption سیٹنگز:**

- `enable_encryption` (bool, ڈیفالٹ: `false`): پروٹوکول encryption سپورٹ کو فعال کریں
- `encryption_mode` (str, ڈیفالٹ: `"preferred"`): encryption موڈ
  - `"disabled"`: کوئی encryption نہیں (صرف سادہ کنکشنز)
  - `"preferred"`: encryption کی کوشش کریں، دستیاب نہ ہونے پر سادہ میں فال بیک
  - `"required"`: encryption لازمی، encryption دستیاب نہ ہونے پر کنکشن ناکام
- `encryption_dh_key_size` (int, ڈیفالٹ: `768`): بٹس میں Diffie-Hellman کلید کا سائز (768 یا 1024)
- `encryption_prefer_rc4` (bool, ڈیفالٹ: `true`): پرانے کلائنٹس کے ساتھ مطابقت کے لیے RC4 cipher ترجیح دیں
- `encryption_allowed_ciphers` (list[str], ڈیفالٹ: `["rc4", "aes"]`): اجازت شدہ cipher اقسام
  - `"rc4"`: RC4 سٹریم cipher (سب سے زیادہ مطابقت)
  - `"aes"`: CFB موڈ میں AES cipher (زیادہ محفوظ)
  - `"chacha20"`: ChaCha20 cipher (ابھی تک لاگو نہیں)
- `encryption_allow_plain_fallback` (bool, ڈیفالٹ: `true`): encryption ناکام ہونے پر سادہ کنکشن میں فال بیک کی اجازت دیں (صرف اس وقت لاگو ہوتا ہے جب `encryption_mode` `"preferred"` ہے)

**ماحولیاتی متغیرات:**

- `CCBT_ENABLE_ENCRYPTION`: encryption فعال/غیر فعال (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: encryption موڈ (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DH کلید کا سائز (`768` یا `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: RC4 ترجیح (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: کاما-علیحدہ فہرست (مثال: `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: سادہ فال بیک کی اجازت (`true`/`false`)

**ترتیب مثال:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**سیکیورٹی کے خیالات:**

1. **RC4 مطابقت**: RC4 مطابقت کے لیے سپورٹ کیا جاتا ہے لیکن cryptographically کمزور ہے۔ جب ممکن ہو بہتر سیکیورٹی کے لیے AES استعمال کریں۔
2. **DH کلید کا سائز**: 768-بٹ DH کلیدیں زیادہ تر استعمال کے معاملات کے لیے کافی سیکیورٹی فراہم کرتی ہیں۔ 1024-بٹ زیادہ مضبوط سیکیورٹی فراہم کرتا ہے لیکن handshake تاخیر بڑھاتا ہے۔
3. **Encryption موڈز**:
   - `preferred`: مطابقت کے لیے بہترین - encryption کی کوشش کرتا ہے لیکن خوبصورتی سے فال بیک کرتا ہے
   - `required`: سب سے زیادہ محفوظ لیکن encryption کو سپورٹ نہ کرنے والے peers کے ساتھ کنکشن ناکام ہو سکتا ہے
4. **کارکردگی کا اثر**: encryption کم سے کم overhead شامل کرتا ہے (RC4 کے لیے ~1-5%, AES کے لیے ~2-8%) لیکن رازداری کو بہتر بناتا ہے اور ٹریفک shaping سے بچنے میں مدد کرتا ہے۔

**لاگو کرنے کی تفصیلات:**

Encryption لاگو کرنا: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Cipher Suites: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman Exchange: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML ترتیب

مشین لرننگ سیٹنگز: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML ترتیب ماڈل: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ڈیش بورڈ ترتیب

ڈیش بورڈ سیٹنگز: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

ڈیش بورڈ ترتیب ماڈل: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## ماحولیاتی متغیرات

ماحولیاتی متغیرات `CCBT_` پریفکس استعمال کرتے ہیں اور ایک ہائرارکیکل نامگذاری اسکیم کی پیروی کرتے ہیں۔

حوالہ: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

فارمیٹ: `CCBT_<SECTION>_<OPTION>=<value>`

مثالیں:
- نیٹ ورک: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- ڈسک: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- حکمت عملی: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- دریافت: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- مشاہدہ: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- حدیں: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- سیکیورٹی: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

ماحولیاتی متغیر پارسنگ: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## ترتیب سکیمہ

ترتیب سکیمہ اور تصدیق: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

سکیمہ تعریف کرتا ہے:
- فیلڈ اقسام اور رکاوٹیں
- ڈیفالٹ اقدار
- تصدیق کے قوانین
- دستاویزات

## ترتیب کی صلاحیتیں

ترتیب کی صلاحیتیں اور خصوصیت کا پتہ لگانا: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## ترتیب ٹیمپلیٹس

پہلے سے طے شدہ ترتیب ٹیمپلیٹس: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

ٹیمپلیٹس:
- اعلیٰ کارکردگی سیٹ اپ
- کم وسائل سیٹ اپ
- سیکیورٹی-مرکوز سیٹ اپ
- ترقیاتی سیٹ اپ

## ترتیب مثالیں

مثال ترتیبات [examples/](examples/) ڈائریکٹری میں دستیاب ہیں:

- بنیادی ترتیب: [example-config-basic.toml](examples/example-config-basic.toml)
- اعلیٰ درجے کی ترتیب: [example-config-advanced.toml](examples/example-config-advanced.toml)
- کارکردگی ترتیب: [example-config-performance.toml](examples/example-config-performance.toml)
- سیکیورٹی ترتیب: [example-config-security.toml](examples/example-config-security.toml)

## ہاٹ ری لوڈ

ترتیب ہاٹ-ری لوڈ سپورٹ: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

ترتیب کا نظام کلائنٹ کو دوبارہ شروع کیے بغیر تبدیلیوں کو ری لوڈ کرنے کی حمایت کرتا ہے۔

## ترتیب مائیگریشن

ترتیب مائیگریشن یوٹیلیٹیز: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

ترتیب کے ورژنز کے درمیان مائیگریٹ کرنے کے لیے ٹولز۔

## ترتیب بیک اپ اور Diff

ترتیب مینجمنٹ یوٹیلیٹیز:
- بیک اپ: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Diff: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## مشروط ترتیب

مشروط ترتیب سپورٹ: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## تجاویز اور بہترین طریقے

### کارکردگی ٹیوننگ

- بڑے ترتیبی لکھنے کے لیے `disk.write_buffer_kib` بڑھائیں: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- بہتر لکھنے کے throughput کے لیے Linux/NVMe پر `direct_io` فعال کریں: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- اپنے نیٹ ورک کے لیے `network.pipeline_depth` اور `network.block_size_kib` ٹیون کریں: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### وسائل کی بہتری

- CPU cores کے مطابق `disk.hash_workers` ایڈجسٹ کریں: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- دستیاب RAM کے مطابق `disk.cache_size_mb` ترتیب دیں: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- bandwidth کے مطابق `network.max_global_peers` سیٹ کریں: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### نیٹ ورک ترتیب

- نیٹ ورک کی شرائط کے مطابق timeouts ترتیب دیں: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- ضرورت کے مطابق پروٹوکولز فعال/غیر فعال کریں: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- مناسب طریقے سے شرح کی حدیں سیٹ کریں: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

تفصیلی کارکردگی ٹیوننگ کے لیے [کارکردگی ٹیوننگ گائیڈ](performance.md) دیکھیں۔






ccBitTorrent TOML سپورٹ، تصدیق، ہاٹ-ری لوڈ، اور متعدد ذرائع سے ہائرارکیکل لوڈنگ کے ساتھ ایک جامع ترتیب کا نظام استعمال کرتا ہے۔

ترتیب کا نظام: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## ترتیب کے ذرائع اور ترجیح

ترتیب اس ترتیب میں لوڈ ہوتی ہے (بعد کے ذرائع پہلے والوں کو اوور رائیڈ کرتے ہیں):

1. **ڈیفالٹ**: [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) سے بلٹ-ان سمجھدار ڈیفالٹ
2. **ترتیب فائل**: موجودہ ڈائریکٹری یا `~/.config/ccbt/ccbt.toml` میں `ccbt.toml`۔ دیکھیں: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **ماحولیاتی متغیرات**: `CCBT_*` پریفکس والے متغیرات۔ دیکھیں: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI دلائل**: کمانڈ-لائن اوور رائیڈز۔ دیکھیں: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **فی-ٹورنٹ**: انفرادی ٹورنٹ سیٹنگز (مستقبل کی خصوصیت)

ترتیب لوڈنگ: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## ترتیب فائل

### ڈیفالٹ ترتیب

ڈیفالٹ ترتیب فائل دیکھیں: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

ترتیب حصوں میں منظم ہے:

### نیٹ ورک ترتیب

نیٹ ورک سیٹنگز: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- کنکشن کی حدیں: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- درخواست پائپ لائن: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- ساکٹ ٹیوننگ: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- ٹائم آؤٹس: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- سننے کی سیٹنگز: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- ٹرانسپورٹ پروٹوکولز: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- شرح کی حدیں: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- چوکنگ حکمت عملی: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- ٹریکر سیٹنگز: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

نیٹ ورک ترتیب ماڈل: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ڈسک ترتیب

ڈسک سیٹنگز: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- پری-الوکیشن: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- لکھنے کی بہتری: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- ہیش تصدیق: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O تھریڈنگ: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- اعلیٰ درجے کی سیٹنگز: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- اسٹوریج سروس سیٹنگز: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: اسٹوریج سروس کے لیے MB میں زیادہ سے زیادہ فائل سائز کی حد (0 یا None = لامحدود، زیادہ سے زیادہ 1048576 = 1TB)۔ ٹیسٹنگ کے دوران لامحدود ڈسک لکھنے کو روکتا ہے اور پروڈکشن استعمال کے لیے ترتیب دیا جا سکتا ہے۔
- چیک پوائنٹ سیٹنگز: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

ڈسک ترتیب ماڈل: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### حکمت عملی ترتیب

حکمت عملی سیٹنگز: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- ٹکڑا انتخاب: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- اعلیٰ درجے کی حکمت عملی: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- ٹکڑا ترجیحات: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

حکمت عملی ترتیب ماڈل: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### دریافت ترتیب

دریافت سیٹنگز: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT سیٹنگز: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX سیٹنگز: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- ٹریکر سیٹنگز: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: سیکنڈ میں ٹریکر اعلان وقفہ (ڈیفالٹ: 1800.0, حد: 60.0-86400.0)
  - `tracker_scrape_interval`: دورانیہ سکریپنگ کے لیے سیکنڈ میں ٹریکر سکریپ وقفہ (ڈیفالٹ: 3600.0, حد: 60.0-86400.0)
  - `tracker_auto_scrape`: torrents شامل ہونے پر خودکار طور پر trackers کو سکریپ کریں (BEP 48) (ڈیفالٹ: false)
  - ماحولیاتی متغیرات: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

دریافت ترتیب ماڈل: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### حدیں ترتیب

شرح کی حدیں: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- عالمی حدیں: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- فی-ٹورنٹ حدیں: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- فی-پیئر حدیں: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- شیڈولر سیٹنگز: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

حدیں ترتیب ماڈل: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### مشاہدہ ترتیب

مشاہدہ سیٹنگز: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- لاگنگ: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- میٹرکس: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- ٹریسنگ اور الرٹس: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

مشاہدہ ترتیب ماڈل: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### سیکیورٹی ترتیب

سیکیورٹی سیٹنگز: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

سیکیورٹی ترتیب ماڈل: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### Encryption ترتیب

ccBitTorrent محفوظ peer کنکشنز کے لیے BEP 3 Message Stream Encryption (MSE) اور Protocol Encryption (PE) کو سپورٹ کرتا ہے۔

**Encryption سیٹنگز:**

- `enable_encryption` (bool, ڈیفالٹ: `false`): پروٹوکول encryption سپورٹ کو فعال کریں
- `encryption_mode` (str, ڈیفالٹ: `"preferred"`): encryption موڈ
  - `"disabled"`: کوئی encryption نہیں (صرف سادہ کنکشنز)
  - `"preferred"`: encryption کی کوشش کریں، دستیاب نہ ہونے پر سادہ میں فال بیک
  - `"required"`: encryption لازمی، encryption دستیاب نہ ہونے پر کنکشن ناکام
- `encryption_dh_key_size` (int, ڈیفالٹ: `768`): بٹس میں Diffie-Hellman کلید کا سائز (768 یا 1024)
- `encryption_prefer_rc4` (bool, ڈیفالٹ: `true`): پرانے کلائنٹس کے ساتھ مطابقت کے لیے RC4 cipher ترجیح دیں
- `encryption_allowed_ciphers` (list[str], ڈیفالٹ: `["rc4", "aes"]`): اجازت شدہ cipher اقسام
  - `"rc4"`: RC4 سٹریم cipher (سب سے زیادہ مطابقت)
  - `"aes"`: CFB موڈ میں AES cipher (زیادہ محفوظ)
  - `"chacha20"`: ChaCha20 cipher (ابھی تک لاگو نہیں)
- `encryption_allow_plain_fallback` (bool, ڈیفالٹ: `true`): encryption ناکام ہونے پر سادہ کنکشن میں فال بیک کی اجازت دیں (صرف اس وقت لاگو ہوتا ہے جب `encryption_mode` `"preferred"` ہے)

**ماحولیاتی متغیرات:**

- `CCBT_ENABLE_ENCRYPTION`: encryption فعال/غیر فعال (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: encryption موڈ (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DH کلید کا سائز (`768` یا `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: RC4 ترجیح (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: کاما-علیحدہ فہرست (مثال: `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: سادہ فال بیک کی اجازت (`true`/`false`)

**ترتیب مثال:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**سیکیورٹی کے خیالات:**

1. **RC4 مطابقت**: RC4 مطابقت کے لیے سپورٹ کیا جاتا ہے لیکن cryptographically کمزور ہے۔ جب ممکن ہو بہتر سیکیورٹی کے لیے AES استعمال کریں۔
2. **DH کلید کا سائز**: 768-بٹ DH کلیدیں زیادہ تر استعمال کے معاملات کے لیے کافی سیکیورٹی فراہم کرتی ہیں۔ 1024-بٹ زیادہ مضبوط سیکیورٹی فراہم کرتا ہے لیکن handshake تاخیر بڑھاتا ہے۔
3. **Encryption موڈز**:
   - `preferred`: مطابقت کے لیے بہترین - encryption کی کوشش کرتا ہے لیکن خوبصورتی سے فال بیک کرتا ہے
   - `required`: سب سے زیادہ محفوظ لیکن encryption کو سپورٹ نہ کرنے والے peers کے ساتھ کنکشن ناکام ہو سکتا ہے
4. **کارکردگی کا اثر**: encryption کم سے کم overhead شامل کرتا ہے (RC4 کے لیے ~1-5%, AES کے لیے ~2-8%) لیکن رازداری کو بہتر بناتا ہے اور ٹریفک shaping سے بچنے میں مدد کرتا ہے۔

**لاگو کرنے کی تفصیلات:**

Encryption لاگو کرنا: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Cipher Suites: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman Exchange: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML ترتیب

مشین لرننگ سیٹنگز: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML ترتیب ماڈل: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### ڈیش بورڈ ترتیب

ڈیش بورڈ سیٹنگز: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

ڈیش بورڈ ترتیب ماڈل: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## ماحولیاتی متغیرات

ماحولیاتی متغیرات `CCBT_` پریفکس استعمال کرتے ہیں اور ایک ہائرارکیکل نامگذاری اسکیم کی پیروی کرتے ہیں۔

حوالہ: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

فارمیٹ: `CCBT_<SECTION>_<OPTION>=<value>`

مثالیں:
- نیٹ ورک: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- ڈسک: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- حکمت عملی: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- دریافت: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- مشاہدہ: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- حدیں: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- سیکیورٹی: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

ماحولیاتی متغیر پارسنگ: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## ترتیب سکیمہ

ترتیب سکیمہ اور تصدیق: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

سکیمہ تعریف کرتا ہے:
- فیلڈ اقسام اور رکاوٹیں
- ڈیفالٹ اقدار
- تصدیق کے قوانین
- دستاویزات

## ترتیب کی صلاحیتیں

ترتیب کی صلاحیتیں اور خصوصیت کا پتہ لگانا: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## ترتیب ٹیمپلیٹس

پہلے سے طے شدہ ترتیب ٹیمپلیٹس: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

ٹیمپلیٹس:
- اعلیٰ کارکردگی سیٹ اپ
- کم وسائل سیٹ اپ
- سیکیورٹی-مرکوز سیٹ اپ
- ترقیاتی سیٹ اپ

## ترتیب مثالیں

مثال ترتیبات [examples/](examples/) ڈائریکٹری میں دستیاب ہیں:

- بنیادی ترتیب: [example-config-basic.toml](examples/example-config-basic.toml)
- اعلیٰ درجے کی ترتیب: [example-config-advanced.toml](examples/example-config-advanced.toml)
- کارکردگی ترتیب: [example-config-performance.toml](examples/example-config-performance.toml)
- سیکیورٹی ترتیب: [example-config-security.toml](examples/example-config-security.toml)

## ہاٹ ری لوڈ

ترتیب ہاٹ-ری لوڈ سپورٹ: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

ترتیب کا نظام کلائنٹ کو دوبارہ شروع کیے بغیر تبدیلیوں کو ری لوڈ کرنے کی حمایت کرتا ہے۔

## ترتیب مائیگریشن

ترتیب مائیگریشن یوٹیلیٹیز: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

ترتیب کے ورژنز کے درمیان مائیگریٹ کرنے کے لیے ٹولز۔

## ترتیب بیک اپ اور Diff

ترتیب مینجمنٹ یوٹیلیٹیز:
- بیک اپ: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Diff: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## مشروط ترتیب

مشروط ترتیب سپورٹ: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## تجاویز اور بہترین طریقے

### کارکردگی ٹیوننگ

- بڑے ترتیبی لکھنے کے لیے `disk.write_buffer_kib` بڑھائیں: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- بہتر لکھنے کے throughput کے لیے Linux/NVMe پر `direct_io` فعال کریں: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- اپنے نیٹ ورک کے لیے `network.pipeline_depth` اور `network.block_size_kib` ٹیون کریں: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### وسائل کی بہتری

- CPU cores کے مطابق `disk.hash_workers` ایڈجسٹ کریں: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- دستیاب RAM کے مطابق `disk.cache_size_mb` ترتیب دیں: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- bandwidth کے مطابق `network.max_global_peers` سیٹ کریں: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### نیٹ ورک ترتیب

- نیٹ ورک کی شرائط کے مطابق timeouts ترتیب دیں: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- ضرورت کے مطابق پروٹوکولز فعال/غیر فعال کریں: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- مناسب طریقے سے شرح کی حدیں سیٹ کریں: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

تفصیلی کارکردگی ٹیوننگ کے لیے [کارکردگی ٹیوننگ گائیڈ](performance.md) دیکھیں۔
































































































































































































