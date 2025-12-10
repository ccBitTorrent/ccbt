# مرجع API برای ccBT

مستندات جامع API برای ccBitTorrent با ارجاع به فایل‌های پیاده‌سازی واقعی.

## نقاط ورود

### نقطه ورود اصلی (ccbt)

نقطه ورود خط فرمان اصلی برای عملیات torrent پایه.

پیاده‌سازی: [ccbt/__main__.py:main](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L18)

ویژگی‌ها:
- حالت دانلود torrent واحد
- حالت دیمن برای جلسات چند torrent: [ccbt/__main__.py:52](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L52)
- پشتیبانی از Magnet URI: [ccbt/__main__.py:73](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L73)
- اعلان Tracker: [ccbt/__main__.py:89](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L89)

پیکربندی نقطه ورود: [pyproject.toml:79](https://github.com/ccBitTorrent/ccbt/blob/main/pyproject.toml#L79)

### کمک‌کننده‌های دانلود ناهمزمان

کمک‌کننده‌ها و مدیر دانلود ناهمزمان با کارایی بالا برای عملیات پیشرفته.

پیاده‌سازی: [ccbt/session/download_manager.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/download_manager.py)

صادرات کلیدی:
- `AsyncDownloadManager`
- `download_torrent()`
- `download_magnet()`

## مدیریت جلسه

### AsyncSessionManager

مدیر جلسه ناهمزمان با کارایی بالا برای چندین torrent.

::: ccbt.session.session.AsyncSessionManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

### AsyncTorrentSession

جلسه torrent فردی که چرخه حیات یک torrent فعال را با عملیات ناهمزمان نشان می‌دهد.

::: ccbt.session.session.AsyncTorrentSession
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**روش‌های کلیدی:**

- `start()`: [ccbt/session/session.py:start](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L400) - شروع جلسه torrent، مقداردهی اولیه مدیر دانلود، trackerها و PEX
- `stop()`: [ccbt/session/session.py:stop](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L678) - توقف جلسه torrent، ذخیره checkpoint، پاکسازی منابع
- `pause()`: [ccbt/session/session.py:pause](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - توقف موقت دانلود
- `resume()`: [ccbt/session/session.py:resume](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - از سرگیری دانلود
- `get_status()`: [ccbt/session/session.py:get_status](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - دریافت وضعیت torrent

## پیکربندی

### ConfigManager

مدیریت پیکربندی با بارگذاری مجدد داغ، بارگذاری سلسله‌مراتبی و اعتبارسنجی.

::: ccbt.config.config.ConfigManager
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**ویژگی‌ها:**
- بارگذاری پیکربندی: [ccbt/config/config.py:_load_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L76)
- کشف فایل: [ccbt/config/config.py:_find_config_file](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L55)
- تجزیه متغیرهای محیطی: [ccbt/config/config.py:_get_env_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py)
- پشتیبانی از بارگذاری مجدد داغ: [ccbt/config/config.py:ConfigManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L40)
- بازنویسی CLI: [ccbt/cli/overrides.py:apply_cli_overrides](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/overrides.py)

**اولویت پیکربندی:**
1. مقادیر پیش‌فرض از `ccbt/models.py:Config`
2. فایل پیکربندی (`ccbt.toml` در دایرکتوری فعلی یا `~/.config/ccbt/ccbt.toml`)
3. متغیرهای محیطی (پیشوند `CCBT_*`)
4. آرگومان‌های CLI (از طریق `apply_cli_overrides()`)
5. مقادیر پیش‌فرض هر torrent
6. بازنویسی‌های هر torrent

## منابع بیشتر

- [راهنمای شروع](getting-started.md) - راهنمای شروع سریع
- [راهنمای پیکربندی](configuration.md) - پیکربندی دقیق
- [تنظیم عملکرد](performance.md) - بهینه‌سازی عملکرد
- [راهنمای Bitonic](bitonic.md) - داشبورد ترمینال
- [مرجع CLI btbt](btbt-cli.md) - مستندات CLI

