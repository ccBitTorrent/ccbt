# راهنمای پیکربندی

ccBitTorrent از یک سیستم پیکربندی جامع با پشتیبانی TOML، اعتبارسنجی، بارگذاری مجدد داغ و بارگذاری سلسله‌مراتبی از چندین منبع استفاده می‌کند.

سیستم پیکربندی: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## منابع پیکربندی و اولویت

پیکربندی به این ترتیب بارگذاری می‌شود (منابع بعدی منابع قبلی را بازنویسی می‌کنند):

1. **پیش‌فرض‌ها**: مقادیر پیش‌فرض منطقی داخلی از [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **فایل پیکربندی**: `ccbt.toml` در دایرکتوری فعلی یا `~/.config/ccbt/ccbt.toml`. ببینید: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **متغیرهای محیطی**: متغیرهای پیشوند `CCBT_*`. ببینید: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **آرگومان‌های CLI**: بازنویسی‌های خط فرمان. ببینید: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **هر تورنت**: تنظیمات تورنت فردی (ویژگی آینده)

بارگذاری پیکربندی: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## فایل پیکربندی

### پیکربندی پیش‌فرض

به فایل پیکربندی پیش‌فرض مراجعه کنید: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

پیکربندی به بخش‌ها سازماندهی شده است:

### پیکربندی شبکه

تنظیمات شبکه: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- محدودیت‌های اتصال: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- خط لوله درخواست: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- تنظیم سوکت: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- زمان‌بندی‌ها: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- تنظیمات گوش دادن: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- پروتکل‌های حمل و نقل: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- محدودیت‌های نرخ: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- استراتژی خفه‌سازی: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- تنظیمات ردیاب: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

مدل پیکربندی شبکه: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی دیسک

تنظیمات دیسک: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- پیش‌تخصیص: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- بهینه‌سازی نوشتن: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- تأیید هش: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- نخ‌بندی I/O: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- تنظیمات پیشرفته: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- تنظیمات سرویس ذخیره‌سازی: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: محدودیت حداکثر اندازه فایل به MB برای سرویس ذخیره‌سازی (0 یا None = نامحدود، حداکثر 1048576 = 1TB). از نوشتن نامحدود دیسک در طول آزمایش جلوگیری می‌کند و می‌تواند برای استفاده در تولید پیکربندی شود.
- تنظیمات نقطه بررسی: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

مدل پیکربندی دیسک: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی استراتژی

تنظیمات استراتژی: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- انتخاب قطعه: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- استراتژی پیشرفته: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- اولویت‌های قطعه: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

مدل پیکربندی استراتژی: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی کشف

تنظیمات کشف: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- تنظیمات DHT: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- تنظیمات PEX: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- تنظیمات ردیاب: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: فاصله اعلان ردیاب به ثانیه (پیش‌فرض: 1800.0، محدوده: 60.0-86400.0)
  - `tracker_scrape_interval`: فاصله خراش ردیاب به ثانیه برای خراش دوره‌ای (پیش‌فرض: 3600.0، محدوده: 60.0-86400.0)
  - `tracker_auto_scrape`: به‌طور خودکار ردیاب‌ها را هنگام افزودن تورنت‌ها خراش دهید (BEP 48) (پیش‌فرض: false)
  - متغیرهای محیطی: `CCBT_TRACKER_ANNOUNCE_INTERVAL`، `CCBT_TRACKER_SCRAPE_INTERVAL`، `CCBT_TRACKER_AUTO_SCRAPE`

مدل پیکربندی کشف: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی محدودیت‌ها

محدودیت‌های نرخ: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- محدودیت‌های سراسری: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- محدودیت‌های هر تورنت: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- محدودیت‌های هر همتا: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- تنظیمات زمان‌بند: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

مدل پیکربندی محدودیت‌ها: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی قابلیت مشاهده

تنظیمات قابلیت مشاهده: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- ثبت: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- معیارها: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- ردیابی و هشدارها: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

مدل پیکربندی قابلیت مشاهده: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی امنیت

تنظیمات امنیت: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

مدل پیکربندی امنیت: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### پیکربندی رمزگذاری

ccBitTorrent از BEP 3 Message Stream Encryption (MSE) و Protocol Encryption (PE) برای اتصالات همتای امن پشتیبانی می‌کند.

**تنظیمات رمزگذاری:**

- `enable_encryption` (bool، پیش‌فرض: `false`): فعال‌سازی پشتیبانی رمزگذاری پروتکل
- `encryption_mode` (str، پیش‌فرض: `"preferred"`): حالت رمزگذاری
  - `"disabled"`: بدون رمزگذاری (فقط اتصالات ساده)
  - `"preferred"`: تلاش برای رمزگذاری، بازگشت به ساده در صورت عدم دسترسی
  - `"required"`: رمزگذاری اجباری، اتصال در صورت عدم دسترسی رمزگذاری ناموفق می‌شود
- `encryption_dh_key_size` (int، پیش‌فرض: `768`): اندازه کلید Diffie-Hellman به بیت (768 یا 1024)
- `encryption_prefer_rc4` (bool، پیش‌فرض: `true`): ترجیح رمز RC4 برای سازگاری با کلاینت‌های قدیمی
- `encryption_allowed_ciphers` (list[str]، پیش‌فرض: `["rc4", "aes"]`): انواع رمز مجاز
  - `"rc4"`: رمز جریان RC4 (بیشترین سازگاری)
  - `"aes"`: رمز AES در حالت CFB (امن‌تر)
  - `"chacha20"`: رمز ChaCha20 (هنوز پیاده‌سازی نشده)
- `encryption_allow_plain_fallback` (bool، پیش‌فرض: `true`): اجازه بازگشت به اتصال ساده در صورت شکست رمزگذاری (فقط زمانی اعمال می‌شود که `encryption_mode` `"preferred"` باشد)

**متغیرهای محیطی:**

- `CCBT_ENABLE_ENCRYPTION`: فعال/غیرفعال کردن رمزگذاری (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: حالت رمزگذاری (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: اندازه کلید DH (`768` یا `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: ترجیح RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: فهرست جدا شده با کاما (مثلاً `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: اجازه بازگشت ساده (`true`/`false`)

**مثال پیکربندی:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**ملاحظات امنیتی:**

1. **سازگاری RC4**: RC4 برای سازگاری پشتیبانی می‌شود اما از نظر رمزنگاری ضعیف است. در صورت امکان از AES برای امنیت بهتر استفاده کنید.
2. **اندازه کلید DH**: کلیدهای DH 768 بیتی امنیت کافی برای بیشتر موارد استفاده ارائه می‌دهند. 1024 بیتی امنیت قوی‌تری ارائه می‌دهد اما تأخیر handshake را افزایش می‌دهد.
3. **حالت‌های رمزگذاری**:
   - `preferred`: بهترین برای سازگاری - رمزگذاری را امتحان می‌کند اما به‌طور ظریف بازمی‌گردد
   - `required`: امن‌ترین اما ممکن است در اتصال با همتاهایی که رمزگذاری را پشتیبانی نمی‌کنند ناموفق باشد
4. **تأثیر عملکرد**: رمزگذاری سربار حداقل اضافه می‌کند (~1-5% برای RC4، ~2-8% برای AES) اما حریم خصوصی را بهبود می‌بخشد و به جلوگیری از شکل‌دهی ترافیک کمک می‌کند.

**جزئیات پیاده‌سازی:**

پیاده‌سازی رمزگذاری: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- Handshake MSE: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- مجموعه‌های رمز: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- تبادل Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### پیکربندی ML

تنظیمات یادگیری ماشین: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

مدل پیکربندی ML: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی داشبورد

تنظیمات داشبورد: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

مدل پیکربندی داشبورد: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## متغیرهای محیطی

متغیرهای محیطی از پیشوند `CCBT_` استفاده می‌کنند و از یک طرح نامگذاری سلسله‌مراتبی پیروی می‌کنند.

مرجع: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

فرمت: `CCBT_<SECTION>_<OPTION>=<value>`

مثال‌ها:
- شبکه: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- دیسک: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- استراتژی: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- کشف: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- قابلیت مشاهده: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- محدودیت‌ها: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- امنیت: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

تجزیه متغیرهای محیطی: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## طرح پیکربندی

طرح پیکربندی و اعتبارسنجی: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

طرح تعریف می‌کند:
- انواع فیلد و محدودیت‌ها
- مقادیر پیش‌فرض
- قوانین اعتبارسنجی
- مستندات

## قابلیت‌های پیکربندی

قابلیت‌های پیکربندی و تشخیص ویژگی: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## الگوهای پیکربندی

الگوهای پیکربندی از پیش تعریف شده: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

الگوها برای:
- تنظیمات با کارایی بالا
- تنظیمات با منابع کم
- تنظیمات متمرکز بر امنیت
- تنظیمات توسعه

## نمونه‌های پیکربندی

نمونه‌های پیکربندی در دایرکتوری [examples/](examples/) موجود است:

- پیکربندی پایه: [example-config-basic.toml](examples/example-config-basic.toml)
- پیکربندی پیشرفته: [example-config-advanced.toml](examples/example-config-advanced.toml)
- پیکربندی عملکرد: [example-config-performance.toml](examples/example-config-performance.toml)
- پیکربندی امنیت: [example-config-security.toml](examples/example-config-security.toml)

## بارگذاری مجدد داغ

پشتیبانی از بارگذاری مجدد داغ پیکربندی: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

سیستم پیکربندی از بارگذاری مجدد تغییرات بدون راه‌اندازی مجدد کلاینت پشتیبانی می‌کند.

## مهاجرت پیکربندی

ابزارهای مهاجرت پیکربندی: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

ابزارهایی برای مهاجرت بین نسخه‌های پیکربندی.

## پشتیبان‌گیری و تفاوت پیکربندی

ابزارهای مدیریت پیکربندی:
- پشتیبان‌گیری: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- تفاوت: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## پیکربندی شرطی

پشتیبانی از پیکربندی شرطی: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## نکات و بهترین شیوه‌ها

### تنظیم عملکرد

- برای نوشتن‌های ترتیبی بزرگ `disk.write_buffer_kib` را افزایش دهید: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- برای بهبود توان عملیاتی نوشتن `direct_io` را در Linux/NVMe فعال کنید: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- `network.pipeline_depth` و `network.block_size_kib` را برای شبکه خود تنظیم کنید: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### بهینه‌سازی منابع

- `disk.hash_workers` را بر اساس هسته‌های CPU تنظیم کنید: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- `disk.cache_size_mb` را بر اساس RAM موجود پیکربندی کنید: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- `network.max_global_peers` را بر اساس پهنای باند تنظیم کنید: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### پیکربندی شبکه

- زمان‌بندی‌ها را بر اساس شرایط شبکه پیکربندی کنید: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- پروتکل‌ها را در صورت نیاز فعال/غیرفعال کنید: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- محدودیت‌های نرخ را به‌طور مناسب تنظیم کنید: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

برای تنظیم تفصیلی عملکرد، [راهنمای تنظیم عملکرد](performance.md) را ببینید.






ccBitTorrent از یک سیستم پیکربندی جامع با پشتیبانی TOML، اعتبارسنجی، بارگذاری مجدد داغ و بارگذاری سلسله‌مراتبی از چندین منبع استفاده می‌کند.

سیستم پیکربندی: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## منابع پیکربندی و اولویت

پیکربندی به این ترتیب بارگذاری می‌شود (منابع بعدی منابع قبلی را بازنویسی می‌کنند):

1. **پیش‌فرض‌ها**: مقادیر پیش‌فرض منطقی داخلی از [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **فایل پیکربندی**: `ccbt.toml` در دایرکتوری فعلی یا `~/.config/ccbt/ccbt.toml`. ببینید: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **متغیرهای محیطی**: متغیرهای پیشوند `CCBT_*`. ببینید: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **آرگومان‌های CLI**: بازنویسی‌های خط فرمان. ببینید: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **هر تورنت**: تنظیمات تورنت فردی (ویژگی آینده)

بارگذاری پیکربندی: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## فایل پیکربندی

### پیکربندی پیش‌فرض

به فایل پیکربندی پیش‌فرض مراجعه کنید: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

پیکربندی به بخش‌ها سازماندهی شده است:

### پیکربندی شبکه

تنظیمات شبکه: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- محدودیت‌های اتصال: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- خط لوله درخواست: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- تنظیم سوکت: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- زمان‌بندی‌ها: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- تنظیمات گوش دادن: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- پروتکل‌های حمل و نقل: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- محدودیت‌های نرخ: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- استراتژی خفه‌سازی: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- تنظیمات ردیاب: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

مدل پیکربندی شبکه: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی دیسک

تنظیمات دیسک: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- پیش‌تخصیص: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- بهینه‌سازی نوشتن: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- تأیید هش: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- نخ‌بندی I/O: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- تنظیمات پیشرفته: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- تنظیمات سرویس ذخیره‌سازی: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: محدودیت حداکثر اندازه فایل به MB برای سرویس ذخیره‌سازی (0 یا None = نامحدود، حداکثر 1048576 = 1TB). از نوشتن نامحدود دیسک در طول آزمایش جلوگیری می‌کند و می‌تواند برای استفاده در تولید پیکربندی شود.
- تنظیمات نقطه بررسی: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

مدل پیکربندی دیسک: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی استراتژی

تنظیمات استراتژی: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- انتخاب قطعه: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- استراتژی پیشرفته: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- اولویت‌های قطعه: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

مدل پیکربندی استراتژی: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی کشف

تنظیمات کشف: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- تنظیمات DHT: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- تنظیمات PEX: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- تنظیمات ردیاب: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: فاصله اعلان ردیاب به ثانیه (پیش‌فرض: 1800.0، محدوده: 60.0-86400.0)
  - `tracker_scrape_interval`: فاصله خراش ردیاب به ثانیه برای خراش دوره‌ای (پیش‌فرض: 3600.0، محدوده: 60.0-86400.0)
  - `tracker_auto_scrape`: به‌طور خودکار ردیاب‌ها را هنگام افزودن تورنت‌ها خراش دهید (BEP 48) (پیش‌فرض: false)
  - متغیرهای محیطی: `CCBT_TRACKER_ANNOUNCE_INTERVAL`، `CCBT_TRACKER_SCRAPE_INTERVAL`، `CCBT_TRACKER_AUTO_SCRAPE`

مدل پیکربندی کشف: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی محدودیت‌ها

محدودیت‌های نرخ: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- محدودیت‌های سراسری: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- محدودیت‌های هر تورنت: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- محدودیت‌های هر همتا: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- تنظیمات زمان‌بند: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

مدل پیکربندی محدودیت‌ها: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی قابلیت مشاهده

تنظیمات قابلیت مشاهده: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- ثبت: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- معیارها: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- ردیابی و هشدارها: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

مدل پیکربندی قابلیت مشاهده: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی امنیت

تنظیمات امنیت: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

مدل پیکربندی امنیت: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### پیکربندی رمزگذاری

ccBitTorrent از BEP 3 Message Stream Encryption (MSE) و Protocol Encryption (PE) برای اتصالات همتای امن پشتیبانی می‌کند.

**تنظیمات رمزگذاری:**

- `enable_encryption` (bool، پیش‌فرض: `false`): فعال‌سازی پشتیبانی رمزگذاری پروتکل
- `encryption_mode` (str، پیش‌فرض: `"preferred"`): حالت رمزگذاری
  - `"disabled"`: بدون رمزگذاری (فقط اتصالات ساده)
  - `"preferred"`: تلاش برای رمزگذاری، بازگشت به ساده در صورت عدم دسترسی
  - `"required"`: رمزگذاری اجباری، اتصال در صورت عدم دسترسی رمزگذاری ناموفق می‌شود
- `encryption_dh_key_size` (int، پیش‌فرض: `768`): اندازه کلید Diffie-Hellman به بیت (768 یا 1024)
- `encryption_prefer_rc4` (bool، پیش‌فرض: `true`): ترجیح رمز RC4 برای سازگاری با کلاینت‌های قدیمی
- `encryption_allowed_ciphers` (list[str]، پیش‌فرض: `["rc4", "aes"]`): انواع رمز مجاز
  - `"rc4"`: رمز جریان RC4 (بیشترین سازگاری)
  - `"aes"`: رمز AES در حالت CFB (امن‌تر)
  - `"chacha20"`: رمز ChaCha20 (هنوز پیاده‌سازی نشده)
- `encryption_allow_plain_fallback` (bool، پیش‌فرض: `true`): اجازه بازگشت به اتصال ساده در صورت شکست رمزگذاری (فقط زمانی اعمال می‌شود که `encryption_mode` `"preferred"` باشد)

**متغیرهای محیطی:**

- `CCBT_ENABLE_ENCRYPTION`: فعال/غیرفعال کردن رمزگذاری (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: حالت رمزگذاری (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: اندازه کلید DH (`768` یا `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: ترجیح RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: فهرست جدا شده با کاما (مثلاً `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: اجازه بازگشت ساده (`true`/`false`)

**مثال پیکربندی:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**ملاحظات امنیتی:**

1. **سازگاری RC4**: RC4 برای سازگاری پشتیبانی می‌شود اما از نظر رمزنگاری ضعیف است. در صورت امکان از AES برای امنیت بهتر استفاده کنید.
2. **اندازه کلید DH**: کلیدهای DH 768 بیتی امنیت کافی برای بیشتر موارد استفاده ارائه می‌دهند. 1024 بیتی امنیت قوی‌تری ارائه می‌دهد اما تأخیر handshake را افزایش می‌دهد.
3. **حالت‌های رمزگذاری**:
   - `preferred`: بهترین برای سازگاری - رمزگذاری را امتحان می‌کند اما به‌طور ظریف بازمی‌گردد
   - `required`: امن‌ترین اما ممکن است در اتصال با همتاهایی که رمزگذاری را پشتیبانی نمی‌کنند ناموفق باشد
4. **تأثیر عملکرد**: رمزگذاری سربار حداقل اضافه می‌کند (~1-5% برای RC4، ~2-8% برای AES) اما حریم خصوصی را بهبود می‌بخشد و به جلوگیری از شکل‌دهی ترافیک کمک می‌کند.

**جزئیات پیاده‌سازی:**

پیاده‌سازی رمزگذاری: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- Handshake MSE: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- مجموعه‌های رمز: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- تبادل Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### پیکربندی ML

تنظیمات یادگیری ماشین: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

مدل پیکربندی ML: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### پیکربندی داشبورد

تنظیمات داشبورد: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

مدل پیکربندی داشبورد: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## متغیرهای محیطی

متغیرهای محیطی از پیشوند `CCBT_` استفاده می‌کنند و از یک طرح نامگذاری سلسله‌مراتبی پیروی می‌کنند.

مرجع: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

فرمت: `CCBT_<SECTION>_<OPTION>=<value>`

مثال‌ها:
- شبکه: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- دیسک: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- استراتژی: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- کشف: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- قابلیت مشاهده: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- محدودیت‌ها: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- امنیت: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

تجزیه متغیرهای محیطی: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## طرح پیکربندی

طرح پیکربندی و اعتبارسنجی: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

طرح تعریف می‌کند:
- انواع فیلد و محدودیت‌ها
- مقادیر پیش‌فرض
- قوانین اعتبارسنجی
- مستندات

## قابلیت‌های پیکربندی

قابلیت‌های پیکربندی و تشخیص ویژگی: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## الگوهای پیکربندی

الگوهای پیکربندی از پیش تعریف شده: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

الگوها برای:
- تنظیمات با کارایی بالا
- تنظیمات با منابع کم
- تنظیمات متمرکز بر امنیت
- تنظیمات توسعه

## نمونه‌های پیکربندی

نمونه‌های پیکربندی در دایرکتوری [examples/](examples/) موجود است:

- پیکربندی پایه: [example-config-basic.toml](examples/example-config-basic.toml)
- پیکربندی پیشرفته: [example-config-advanced.toml](examples/example-config-advanced.toml)
- پیکربندی عملکرد: [example-config-performance.toml](examples/example-config-performance.toml)
- پیکربندی امنیت: [example-config-security.toml](examples/example-config-security.toml)

## بارگذاری مجدد داغ

پشتیبانی از بارگذاری مجدد داغ پیکربندی: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

سیستم پیکربندی از بارگذاری مجدد تغییرات بدون راه‌اندازی مجدد کلاینت پشتیبانی می‌کند.

## مهاجرت پیکربندی

ابزارهای مهاجرت پیکربندی: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

ابزارهایی برای مهاجرت بین نسخه‌های پیکربندی.

## پشتیبان‌گیری و تفاوت پیکربندی

ابزارهای مدیریت پیکربندی:
- پشتیبان‌گیری: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- تفاوت: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## پیکربندی شرطی

پشتیبانی از پیکربندی شرطی: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## نکات و بهترین شیوه‌ها

### تنظیم عملکرد

- برای نوشتن‌های ترتیبی بزرگ `disk.write_buffer_kib` را افزایش دهید: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- برای بهبود توان عملیاتی نوشتن `direct_io` را در Linux/NVMe فعال کنید: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- `network.pipeline_depth` و `network.block_size_kib` را برای شبکه خود تنظیم کنید: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### بهینه‌سازی منابع

- `disk.hash_workers` را بر اساس هسته‌های CPU تنظیم کنید: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- `disk.cache_size_mb` را بر اساس RAM موجود پیکربندی کنید: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- `network.max_global_peers` را بر اساس پهنای باند تنظیم کنید: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### پیکربندی شبکه

- زمان‌بندی‌ها را بر اساس شرایط شبکه پیکربندی کنید: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- پروتکل‌ها را در صورت نیاز فعال/غیرفعال کنید: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- محدودیت‌های نرخ را به‌طور مناسب تنظیم کنید: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

برای تنظیم تفصیلی عملکرد، [راهنمای تنظیم عملکرد](performance.md) را ببینید.
































































































































































































