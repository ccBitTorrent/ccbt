# شروع

به ccBitTorrent خوش آمدید! این راهنما به شما کمک می‌کند تا به سرعت با کلاینت BitTorrent با کارایی بالا ما شروع به کار کنید.

!!! tip "ویژگی کلیدی: افزونه پروتکل BEP XET"
    ccBitTorrent شامل **افزونه پروتکل Xet (BEP XET)** است که تکه‌بندی تعریف‌شده محتوا و حذف تکراری بین تورنت را امکان‌پذیر می‌کند. این BitTorrent را به یک سیستم فایل peer-to-peer فوق‌العاده سریع و قابل به‌روزرسانی بهینه‌شده برای همکاری تبدیل می‌کند. [بیشتر درباره BEP XET بیاموزید →](bep_xet.md)

## نصب

### پیش‌نیازها

- Python 3.8 یا بالاتر
- مدیر بسته [UV](https://astral.sh/uv) (توصیه می‌شود)

### نصب UV

UV را از اسکریپت نصب رسمی نصب کنید:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### نصب ccBitTorrent

نصب از PyPI:
```bash
uv pip install ccbittorrent
```

یا نصب از منبع:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

نقاط ورودی در [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81) تعریف شده‌اند.

## نقاط ورودی اصلی

ccBitTorrent سه نقطه ورودی اصلی ارائه می‌دهد:

### 1. Bitonic (توصیه می‌شود)

**Bitonic** رابط داشبورد ترمینال اصلی است. این یک نمای زنده و تعاملی از تمام تورنت‌ها، همتاها و معیارهای سیستم ارائه می‌دهد.

- نقطه ورودی: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- تعریف شده در: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- راه‌اندازی: `uv run bitonic` یا `uv run ccbt dashboard`

برای استفاده تفصیلی، [راهنمای Bitonic](bitonic.md) را ببینید.

### 2. btbt CLI

**btbt** رابط خط فرمان پیشرفته با ویژگی‌های غنی است.

- نقطه ورودی: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- تعریف شده در: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- راه‌اندازی: `uv run btbt`

برای تمام دستورات موجود، [مرجع btbt CLI](btbt-cli.md) را ببینید.

### 3. ccbt (CLI پایه)

**ccbt** رابط CLI پایه است.

- نقطه ورودی: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- تعریف شده در: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- راه‌اندازی: `uv run ccbt`

## شروع سریع

### راه‌اندازی Bitonic (توصیه می‌شود)

شروع داشبورد ترمینال:
```bash
uv run bitonic
```

یا از طریق CLI:
```bash
uv run ccbt dashboard
```

با نرخ تازه‌سازی سفارشی:
```bash
uv run ccbt dashboard --refresh 2.0
```

### دانلود یک Torrent

با استفاده از CLI:
```bash
# دانلود از فایل torrent
uv run btbt download movie.torrent

# دانلود از لینک magnet
uv run btbt magnet "magnet:?xt=urn:btih:..."

# با محدودیت‌های نرخ
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

برای تمام گزینه‌های دانلود، [مرجع btbt CLI](btbt-cli.md) را ببینید.

### پیکربندی ccBitTorrent

یک فایل `ccbt.toml` در دایرکتوری کاری خود ایجاد کنید. به پیکربندی نمونه مراجعه کنید:
- پیکربندی پیش‌فرض: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- متغیرهای محیطی: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- سیستم پیکربندی: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

برای گزینه‌های پیکربندی تفصیلی، [راهنمای پیکربندی](configuration.md) را ببینید.

## گزارش‌های پروژه

مشاهده معیارهای کیفیت پروژه و گزارش‌ها:

- **پوشش کد**: [reports/coverage.md](reports/coverage.md) - تجزیه و تحلیل جامع پوشش کد
- **گزارش امنیتی**: [reports/bandit/index.md](reports/bandit/index.md) - نتایج اسکن امنیتی از Bandit
- **معیارهای عملکرد**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - نتایج معیار عملکرد

این گزارش‌ها به‌طور خودکار به‌عنوان بخشی از فرآیند یکپارچه‌سازی مداوم ما تولید و به‌روزرسانی می‌شوند.

## مراحل بعدی

- [Bitonic](bitonic.md) - درباره رابط داشبورد ترمینال بیاموزید
- [btbt CLI](btbt-cli.md) - مرجع کامل رابط خط فرمان
- [پیکربندی](configuration.md) - گزینه‌های پیکربندی تفصیلی
- [تنظیم عملکرد](performance.md) - راهنمای بهینه‌سازی
- [مرجع API](API.md) - مستندات API Python شامل ویژگی‌های نظارت

## دریافت کمک

- از `uv run bitonic --help` یا `uv run btbt --help` برای کمک دستور استفاده کنید
- [مرجع btbt CLI](btbt-cli.md) را برای گزینه‌های تفصیلی بررسی کنید
- برای مسائل و بحث‌ها به [مخزن GitHub](https://github.com/yourusername/ccbittorrent) ما مراجعه کنید






به ccBitTorrent خوش آمدید! این راهنما به شما کمک می‌کند تا به سرعت با کلاینت BitTorrent با کارایی بالا ما شروع به کار کنید.

!!! tip "ویژگی کلیدی: افزونه پروتکل BEP XET"
    ccBitTorrent شامل **افزونه پروتکل Xet (BEP XET)** است که تکه‌بندی تعریف‌شده محتوا و حذف تکراری بین تورنت را امکان‌پذیر می‌کند. این BitTorrent را به یک سیستم فایل peer-to-peer فوق‌العاده سریع و قابل به‌روزرسانی بهینه‌شده برای همکاری تبدیل می‌کند. [بیشتر درباره BEP XET بیاموزید →](bep_xet.md)

## نصب

### پیش‌نیازها

- Python 3.8 یا بالاتر
- مدیر بسته [UV](https://astral.sh/uv) (توصیه می‌شود)

### نصب UV

UV را از اسکریپت نصب رسمی نصب کنید:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### نصب ccBitTorrent

نصب از PyPI:
```bash
uv pip install ccbittorrent
```

یا نصب از منبع:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

نقاط ورودی در [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81) تعریف شده‌اند.

## نقاط ورودی اصلی

ccBitTorrent سه نقطه ورودی اصلی ارائه می‌دهد:

### 1. Bitonic (توصیه می‌شود)

**Bitonic** رابط داشبورد ترمینال اصلی است. این یک نمای زنده و تعاملی از تمام تورنت‌ها، همتاها و معیارهای سیستم ارائه می‌دهد.

- نقطه ورودی: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- تعریف شده در: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- راه‌اندازی: `uv run bitonic` یا `uv run ccbt dashboard`

برای استفاده تفصیلی، [راهنمای Bitonic](bitonic.md) را ببینید.

### 2. btbt CLI

**btbt** رابط خط فرمان پیشرفته با ویژگی‌های غنی است.

- نقطه ورودی: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- تعریف شده در: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- راه‌اندازی: `uv run btbt`

برای تمام دستورات موجود، [مرجع btbt CLI](btbt-cli.md) را ببینید.

### 3. ccbt (CLI پایه)

**ccbt** رابط CLI پایه است.

- نقطه ورودی: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- تعریف شده در: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- راه‌اندازی: `uv run ccbt`

## شروع سریع

### راه‌اندازی Bitonic (توصیه می‌شود)

شروع داشبورد ترمینال:
```bash
uv run bitonic
```

یا از طریق CLI:
```bash
uv run ccbt dashboard
```

با نرخ تازه‌سازی سفارشی:
```bash
uv run ccbt dashboard --refresh 2.0
```

### دانلود یک Torrent

با استفاده از CLI:
```bash
# دانلود از فایل torrent
uv run btbt download movie.torrent

# دانلود از لینک magnet
uv run btbt magnet "magnet:?xt=urn:btih:..."

# با محدودیت‌های نرخ
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

برای تمام گزینه‌های دانلود، [مرجع btbt CLI](btbt-cli.md) را ببینید.

### پیکربندی ccBitTorrent

یک فایل `ccbt.toml` در دایرکتوری کاری خود ایجاد کنید. به پیکربندی نمونه مراجعه کنید:
- پیکربندی پیش‌فرض: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- متغیرهای محیطی: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- سیستم پیکربندی: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

برای گزینه‌های پیکربندی تفصیلی، [راهنمای پیکربندی](configuration.md) را ببینید.

## گزارش‌های پروژه

مشاهده معیارهای کیفیت پروژه و گزارش‌ها:

- **پوشش کد**: [reports/coverage.md](reports/coverage.md) - تجزیه و تحلیل جامع پوشش کد
- **گزارش امنیتی**: [reports/bandit/index.md](reports/bandit/index.md) - نتایج اسکن امنیتی از Bandit
- **معیارهای عملکرد**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - نتایج معیار عملکرد

این گزارش‌ها به‌طور خودکار به‌عنوان بخشی از فرآیند یکپارچه‌سازی مداوم ما تولید و به‌روزرسانی می‌شوند.

## مراحل بعدی

- [Bitonic](bitonic.md) - درباره رابط داشبورد ترمینال بیاموزید
- [btbt CLI](btbt-cli.md) - مرجع کامل رابط خط فرمان
- [پیکربندی](configuration.md) - گزینه‌های پیکربندی تفصیلی
- [تنظیم عملکرد](performance.md) - راهنمای بهینه‌سازی
- [مرجع API](API.md) - مستندات API Python شامل ویژگی‌های نظارت

## دریافت کمک

- از `uv run bitonic --help` یا `uv run btbt --help` برای کمک دستور استفاده کنید
- [مرجع btbt CLI](btbt-cli.md) را برای گزینه‌های تفصیلی بررسی کنید
- برای مسائل و بحث‌ها به [مخزن GitHub](https://github.com/yourusername/ccbittorrent) ما مراجعه کنید
































































































































































































