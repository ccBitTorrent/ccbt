# نمونه‌ها

این بخش نمونه‌های عملی و نمونه‌های کد برای استفاده از ccBitTorrent ارائه می‌دهد.

## نمونه‌های پیکربندی

### پیکربندی پایه

یک فایل پیکربندی حداقلی برای شروع:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

برای پیکربندی پایه کامل، [example-config-basic.toml](examples/example-config-basic.toml) را ببینید.

### پیکربندی پیشرفته

برای کاربران پیشرفته که نیاز به کنترل دقیق دارند:

برای گزینه‌های پیکربندی پیشرفته، [example-config-advanced.toml](examples/example-config-advanced.toml) را ببینید.

### پیکربندی عملکرد

تنظیمات بهینه‌شده برای حداکثر عملکرد:

برای تنظیم عملکرد، [example-config-performance.toml](examples/example-config-performance.toml) را ببینید.

### پیکربندی امنیت

پیکربندی متمرکز بر امنیت با رمزگذاری و اعتبارسنجی:

برای تنظیمات امنیتی، [example-config-security.toml](examples/example-config-security.toml) را ببینید.

## نمونه‌های BEP 52

### ایجاد یک Torrent v2

ایجاد فایل torrent BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# ایجاد torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # قطعات 16KB
)
```

برای نمونه کامل، [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) را ببینید.

### ایجاد یک Torrent ترکیبی

ایجاد یک torrent ترکیبی که با کلاینت‌های v1 و v2 کار می‌کند:

برای نمونه کامل، [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) را ببینید.

### تجزیه یک Torrent v2

تجزیه و بررسی فایل torrent BitTorrent v2:

برای نمونه کامل، [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) را ببینید.

### جلسه پروتکل v2

استفاده از پروتکل BitTorrent v2 در یک جلسه:

برای نمونه کامل، [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) را ببینید.

## شروع

برای اطلاعات بیشتر در مورد شروع با ccBitTorrent، [راهنمای شروع](getting-started.md) را ببینید.






این بخش نمونه‌های عملی و نمونه‌های کد برای استفاده از ccBitTorrent ارائه می‌دهد.

## نمونه‌های پیکربندی

### پیکربندی پایه

یک فایل پیکربندی حداقلی برای شروع:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

برای پیکربندی پایه کامل، [example-config-basic.toml](examples/example-config-basic.toml) را ببینید.

### پیکربندی پیشرفته

برای کاربران پیشرفته که نیاز به کنترل دقیق دارند:

برای گزینه‌های پیکربندی پیشرفته، [example-config-advanced.toml](examples/example-config-advanced.toml) را ببینید.

### پیکربندی عملکرد

تنظیمات بهینه‌شده برای حداکثر عملکرد:

برای تنظیم عملکرد، [example-config-performance.toml](examples/example-config-performance.toml) را ببینید.

### پیکربندی امنیت

پیکربندی متمرکز بر امنیت با رمزگذاری و اعتبارسنجی:

برای تنظیمات امنیتی، [example-config-security.toml](examples/example-config-security.toml) را ببینید.

## نمونه‌های BEP 52

### ایجاد یک Torrent v2

ایجاد فایل torrent BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# ایجاد torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # قطعات 16KB
)
```

برای نمونه کامل، [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) را ببینید.

### ایجاد یک Torrent ترکیبی

ایجاد یک torrent ترکیبی که با کلاینت‌های v1 و v2 کار می‌کند:

برای نمونه کامل، [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) را ببینید.

### تجزیه یک Torrent v2

تجزیه و بررسی فایل torrent BitTorrent v2:

برای نمونه کامل، [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) را ببینید.

### جلسه پروتکل v2

استفاده از پروتکل BitTorrent v2 در یک جلسه:

برای نمونه کامل، [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) را ببینید.

## شروع

برای اطلاعات بیشتر در مورد شروع با ccBitTorrent، [راهنمای شروع](getting-started.md) را ببینید.
































































































































































































