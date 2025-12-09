# شروع کرنا

ccBitTorrent میں خوش آمدید! یہ گائیڈ آپ کو ہمارے اعلیٰ کارکردگی BitTorrent کلائنٹ کے ساتھ تیزی سے شروع کرنے اور چلانے میں مدد کرے گا۔

!!! tip "اہم خصوصیت: BEP XET پروٹوکول ایکسٹینشن"
    ccBitTorrent میں **Xet پروٹوکول ایکسٹینشن (BEP XET)** شامل ہے، جو مواد-تعریف شدہ چنکنگ اور کراس-ٹورنٹ ڈیڈپلیکیشن کو قابل بناتا ہے۔ یہ BitTorrent کو تعاون کے لیے بہتر بنایا گیا ایک سپر-فاسٹ، اپ ڈیٹ کرنے کے قابل peer-to-peer فائل سسٹم میں تبدیل کرتا ہے۔ [BEP XET کے بارے میں مزید جانیں →](bep_xet.md)

## انسٹالیشن

### ضروریات

- Python 3.8 یا اس سے زیادہ
- [UV](https://astral.sh/uv) پیکیج مینیجر (تجویز کردہ)

### UV انسٹال کریں

سرکاری انسٹالیشن سکرپٹ سے UV انسٹال کریں:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ccBitTorrent انسٹال کریں

PyPI سے انسٹال کریں:
```bash
uv pip install ccbittorrent
```

یا سورس سے انسٹال کریں:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

ایٹری پوائنٹس [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81) میں تعریف کیے گئے ہیں۔

## اہم داخلہ نکات

ccBitTorrent تین اہم داخلہ نکات فراہم کرتا ہے:

### 1. Bitonic (تجویز کردہ)

**Bitonic** اہم ٹرمینل ڈیش بورڈ انٹرفیس ہے۔ یہ تمام torrents، peers، اور سسٹم میٹرکس کا لائیو، انٹرایکٹو منظر فراہم کرتا ہے۔

- داخلہ نقطہ: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- میں تعریف: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- لانچ: `uv run bitonic` یا `uv run ccbt dashboard`

تفصیلی استعمال کے لیے [Bitonic گائیڈ](bitonic.md) دیکھیں۔

### 2. btbt CLI

**btbt** بہتر کمانڈ-لائن انٹرفیس ہے جس میں بھرپور خصوصیات ہیں۔

- داخلہ نقطہ: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- میں تعریف: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- لانچ: `uv run btbt`

تمام دستیاب کمانڈز کے لیے [btbt CLI حوالہ](btbt-cli.md) دیکھیں۔

### 3. ccbt (بنیادی CLI)

**ccbt** بنیادی کمانڈ-لائن انٹرفیس ہے۔

- داخلہ نقطہ: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- میں تعریف: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- لانچ: `uv run ccbt`

## تیز شروع

### Bitonic لانچ کریں (تجویز کردہ)

ٹرمینل ڈیش بورڈ شروع کریں:
```bash
uv run bitonic
```

یا CLI کے ذریعے:
```bash
uv run ccbt dashboard
```

کسٹم ریفریش ریٹ کے ساتھ:
```bash
uv run ccbt dashboard --refresh 2.0
```

### ایک Torrent ڈاؤن لوڈ کریں

CLI استعمال کرتے ہوئے:
```bash
# torrent فائل سے ڈاؤن لوڈ
uv run btbt download movie.torrent

# magnet لنک سے ڈاؤن لوڈ
uv run btbt magnet "magnet:?xt=urn:btih:..."

# شرح کی حدوں کے ساتھ
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

تمام ڈاؤن لوڈ اختیارات کے لیے [btbt CLI حوالہ](btbt-cli.md) دیکھیں۔

### ccBitTorrent ترتیب دیں

اپنی کام کی ڈائریکٹری میں ایک `ccbt.toml` فائل بنائیں۔ مثال کی ترتیب دیکھیں:
- ڈیفالٹ ترتیب: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- ماحولیاتی متغیرات: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- ترتیب کا نظام: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

تفصیلی ترتیب کے اختیارات کے لیے [ترتیب گائیڈ](configuration.md) دیکھیں۔

## منصوبے کی رپورٹس

منصوبے کے معیار کے میٹرکس اور رپورٹس دیکھیں:

- **کوڈ کوریج**: [reports/coverage.md](reports/coverage.md) - جامع کوڈ کوریج تجزیہ
- **سیکیورٹی رپورٹ**: [reports/bandit/index.md](reports/bandit/index.md) - Bandit سے سیکیورٹی اسکیننگ کے نتائج
- **بینچ مارکس**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - کارکردگی بینچ مارک نتائج

یہ رپورٹس ہمارے مسلسل انضمام کے عمل کے حصے کے طور پر خودکار طریقے سے تیار اور اپ ڈیٹ کی جاتی ہیں۔

## اگلے اقدامات

- [Bitonic](bitonic.md) - ٹرمینل ڈیش بورڈ انٹرفیس کے بارے میں جانیں
- [btbt CLI](btbt-cli.md) - مکمل کمانڈ-لائن انٹرفیس حوالہ
- [ترتیب](configuration.md) - تفصیلی ترتیب کے اختیارات
- [کارکردگی کی ٹیوننگ](performance.md) - بہتری گائیڈ
- [API حوالہ](API.md) - نگرانی کی خصوصیات سمیت Python API دستاویزات

## مدد حاصل کریں

- کمانڈ مدد کے لیے `uv run bitonic --help` یا `uv run btbt --help` استعمال کریں
- تفصیلی اختیارات کے لیے [btbt CLI حوالہ](btbt-cli.md) چیک کریں
- مسائل اور بحث کے لیے ہمارے [GitHub ریپوزٹری](https://github.com/yourusername/ccbittorrent) پر جائیں






ccBitTorrent میں خوش آمدید! یہ گائیڈ آپ کو ہمارے اعلیٰ کارکردگی BitTorrent کلائنٹ کے ساتھ تیزی سے شروع کرنے اور چلانے میں مدد کرے گا۔

!!! tip "اہم خصوصیت: BEP XET پروٹوکول ایکسٹینشن"
    ccBitTorrent میں **Xet پروٹوکول ایکسٹینشن (BEP XET)** شامل ہے، جو مواد-تعریف شدہ چنکنگ اور کراس-ٹورنٹ ڈیڈپلیکیشن کو قابل بناتا ہے۔ یہ BitTorrent کو تعاون کے لیے بہتر بنایا گیا ایک سپر-فاسٹ، اپ ڈیٹ کرنے کے قابل peer-to-peer فائل سسٹم میں تبدیل کرتا ہے۔ [BEP XET کے بارے میں مزید جانیں →](bep_xet.md)

## انسٹالیشن

### ضروریات

- Python 3.8 یا اس سے زیادہ
- [UV](https://astral.sh/uv) پیکیج مینیجر (تجویز کردہ)

### UV انسٹال کریں

سرکاری انسٹالیشن سکرپٹ سے UV انسٹال کریں:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ccBitTorrent انسٹال کریں

PyPI سے انسٹال کریں:
```bash
uv pip install ccbittorrent
```

یا سورس سے انسٹال کریں:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

ایٹری پوائنٹس [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81) میں تعریف کیے گئے ہیں۔

## اہم داخلہ نکات

ccBitTorrent تین اہم داخلہ نکات فراہم کرتا ہے:

### 1. Bitonic (تجویز کردہ)

**Bitonic** اہم ٹرمینل ڈیش بورڈ انٹرفیس ہے۔ یہ تمام torrents، peers، اور سسٹم میٹرکس کا لائیو، انٹرایکٹو منظر فراہم کرتا ہے۔

- داخلہ نقطہ: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- میں تعریف: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- لانچ: `uv run bitonic` یا `uv run ccbt dashboard`

تفصیلی استعمال کے لیے [Bitonic گائیڈ](bitonic.md) دیکھیں۔

### 2. btbt CLI

**btbt** بہتر کمانڈ-لائن انٹرفیس ہے جس میں بھرپور خصوصیات ہیں۔

- داخلہ نقطہ: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- میں تعریف: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- لانچ: `uv run btbt`

تمام دستیاب کمانڈز کے لیے [btbt CLI حوالہ](btbt-cli.md) دیکھیں۔

### 3. ccbt (بنیادی CLI)

**ccbt** بنیادی کمانڈ-لائن انٹرفیس ہے۔

- داخلہ نقطہ: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- میں تعریف: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- لانچ: `uv run ccbt`

## تیز شروع

### Bitonic لانچ کریں (تجویز کردہ)

ٹرمینل ڈیش بورڈ شروع کریں:
```bash
uv run bitonic
```

یا CLI کے ذریعے:
```bash
uv run ccbt dashboard
```

کسٹم ریفریش ریٹ کے ساتھ:
```bash
uv run ccbt dashboard --refresh 2.0
```

### ایک Torrent ڈاؤن لوڈ کریں

CLI استعمال کرتے ہوئے:
```bash
# torrent فائل سے ڈاؤن لوڈ
uv run btbt download movie.torrent

# magnet لنک سے ڈاؤن لوڈ
uv run btbt magnet "magnet:?xt=urn:btih:..."

# شرح کی حدوں کے ساتھ
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

تمام ڈاؤن لوڈ اختیارات کے لیے [btbt CLI حوالہ](btbt-cli.md) دیکھیں۔

### ccBitTorrent ترتیب دیں

اپنی کام کی ڈائریکٹری میں ایک `ccbt.toml` فائل بنائیں۔ مثال کی ترتیب دیکھیں:
- ڈیفالٹ ترتیب: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- ماحولیاتی متغیرات: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- ترتیب کا نظام: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

تفصیلی ترتیب کے اختیارات کے لیے [ترتیب گائیڈ](configuration.md) دیکھیں۔

## منصوبے کی رپورٹس

منصوبے کے معیار کے میٹرکس اور رپورٹس دیکھیں:

- **کوڈ کوریج**: [reports/coverage.md](reports/coverage.md) - جامع کوڈ کوریج تجزیہ
- **سیکیورٹی رپورٹ**: [reports/bandit/index.md](reports/bandit/index.md) - Bandit سے سیکیورٹی اسکیننگ کے نتائج
- **بینچ مارکس**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - کارکردگی بینچ مارک نتائج

یہ رپورٹس ہمارے مسلسل انضمام کے عمل کے حصے کے طور پر خودکار طریقے سے تیار اور اپ ڈیٹ کی جاتی ہیں۔

## اگلے اقدامات

- [Bitonic](bitonic.md) - ٹرمینل ڈیش بورڈ انٹرفیس کے بارے میں جانیں
- [btbt CLI](btbt-cli.md) - مکمل کمانڈ-لائن انٹرفیس حوالہ
- [ترتیب](configuration.md) - تفصیلی ترتیب کے اختیارات
- [کارکردگی کی ٹیوننگ](performance.md) - بہتری گائیڈ
- [API حوالہ](API.md) - نگرانی کی خصوصیات سمیت Python API دستاویزات

## مدد حاصل کریں

- کمانڈ مدد کے لیے `uv run bitonic --help` یا `uv run btbt --help` استعمال کریں
- تفصیلی اختیارات کے لیے [btbt CLI حوالہ](btbt-cli.md) چیک کریں
- مسائل اور بحث کے لیے ہمارے [GitHub ریپوزٹری](https://github.com/yourusername/ccbittorrent) پر جائیں
































































































































































































