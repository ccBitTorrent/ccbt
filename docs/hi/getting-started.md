# शुरुआत करना

ccBitTorrent में आपका स्वागत है! यह गाइड आपको हमारे उच्च प्रदर्शन BitTorrent क्लाइंट के साथ तेजी से शुरुआत करने में मदद करेगा।

!!! tip "मुख्य सुविधा: BEP XET प्रोटोकॉल एक्सटेंशन"
    ccBitTorrent में **Xet प्रोटोकॉल एक्सटेंशन (BEP XET)** शामिल है, जो सामग्री-परिभाषित चंकिंग और क्रॉस-टोरेंट डीडुप्लिकेशन को सक्षम करता है। यह BitTorrent को सहयोग के लिए अनुकूलित एक सुपर-फास्ट, अपडेट करने योग्य peer-to-peer फ़ाइल सिस्टम में बदलता है। [BEP XET के बारे में अधिक जानें →](bep_xet.md)

## स्थापना

### आवश्यकताएं

- Python 3.8 या उच्चतर
- [UV](https://astral.sh/uv) पैकेज मैनेजर (अनुशंसित)

### UV स्थापित करें

आधिकारिक स्थापना स्क्रिप्ट से UV स्थापित करें:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ccBitTorrent स्थापित करें

PyPI से स्थापित करें:
```bash
uv pip install ccbittorrent
```

या स्रोत से स्थापित करें:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

एंट्री पॉइंट [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81) में परिभाषित हैं।

## मुख्य एंट्री पॉइंट

ccBitTorrent तीन मुख्य एंट्री पॉइंट प्रदान करता है:

### 1. Bitonic (अनुशंसित)

**Bitonic** मुख्य टर्मिनल डैशबोर्ड इंटरफ़ेस है। यह सभी टोरेंट्स, पीयर्स और सिस्टम मेट्रिक्स का लाइव, इंटरैक्टिव दृश्य प्रदान करता है।

- एंट्री पॉइंट: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- परिभाषित: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- लॉन्च: `uv run bitonic` या `uv run ccbt dashboard`

विस्तृत उपयोग के लिए [Bitonic गाइड](bitonic.md) देखें।

### 2. btbt CLI

**btbt** समृद्ध सुविधाओं के साथ वर्धित कमांड-लाइन इंटरफ़ेस है।

- एंट्री पॉइंट: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- परिभाषित: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- लॉन्च: `uv run btbt`

सभी उपलब्ध कमांड के लिए [btbt CLI संदर्भ](btbt-cli.md) देखें।

### 3. ccbt (मूल CLI)

**ccbt** मूल कमांड-लाइन इंटरफ़ेस है।

- एंट्री पॉइंट: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- परिभाषित: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- लॉन्च: `uv run ccbt`

## त्वरित प्रारंभ

### Bitonic लॉन्च करें (अनुशंसित)

टर्मिनल डैशबोर्ड शुरू करें:
```bash
uv run bitonic
```

या CLI के माध्यम से:
```bash
uv run ccbt dashboard
```

कस्टम रिफ्रेश दर के साथ:
```bash
uv run ccbt dashboard --refresh 2.0
```

### एक टोरेंट डाउनलोड करें

CLI का उपयोग करके:
```bash
# टोरेंट फ़ाइल से डाउनलोड
uv run btbt download movie.torrent

# मैग्नेट लिंक से डाउनलोड
uv run btbt magnet "magnet:?xt=urn:btih:..."

# दर सीमाओं के साथ
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

सभी डाउनलोड विकल्पों के लिए [btbt CLI संदर्भ](btbt-cli.md) देखें।

### ccBitTorrent कॉन्फ़िगर करें

अपने कार्य निर्देशिका में एक `ccbt.toml` फ़ाइल बनाएं। उदाहरण कॉन्फ़िगरेशन देखें:
- डिफ़ॉल्ट कॉन्फ़िग: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- पर्यावरण चर: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- कॉन्फ़िगरेशन सिस्टम: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

विस्तृत कॉन्फ़िगरेशन विकल्पों के लिए [कॉन्फ़िगरेशन गाइड](configuration.md) देखें।

## परियोजना रिपोर्ट

परियोजना गुणवत्ता मेट्रिक्स और रिपोर्ट देखें:

- **कोड कवरेज**: [reports/coverage.md](reports/coverage.md) - व्यापक कोड कवरेज विश्लेषण
- **सुरक्षा रिपोर्ट**: [reports/bandit/index.md](reports/bandit/index.md) - Bandit से सुरक्षा स्कैनिंग परिणाम
- **बेंचमार्क**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - प्रदर्शन बेंचमार्क परिणाम

ये रिपोर्ट हमारी निरंतर एकीकरण प्रक्रिया के हिस्से के रूप में स्वचालित रूप से उत्पन्न और अद्यतन की जाती हैं।

## अगले कदम

- [Bitonic](bitonic.md) - टर्मिनल डैशबोर्ड इंटरफ़ेस के बारे में जानें
- [btbt CLI](btbt-cli.md) - पूर्ण कमांड-लाइन इंटरफ़ेस संदर्भ
- [कॉन्फ़िगरेशन](configuration.md) - विस्तृत कॉन्फ़िगरेशन विकल्प
- [प्रदर्शन ट्यूनिंग](performance.md) - अनुकूलन गाइड
- [API संदर्भ](API.md) - निगरानी सुविधाओं सहित Python API दस्तावेज़

## मदद प्राप्त करना

- कमांड मदद के लिए `uv run bitonic --help` या `uv run btbt --help` का उपयोग करें
- विस्तृत विकल्पों के लिए [btbt CLI संदर्भ](btbt-cli.md) देखें
- समस्याओं और चर्चाओं के लिए हमारे [GitHub रिपॉजिटरी](https://github.com/yourusername/ccbittorrent) पर जाएं






ccBitTorrent में आपका स्वागत है! यह गाइड आपको हमारे उच्च प्रदर्शन BitTorrent क्लाइंट के साथ तेजी से शुरुआत करने में मदद करेगा।

!!! tip "मुख्य सुविधा: BEP XET प्रोटोकॉल एक्सटेंशन"
    ccBitTorrent में **Xet प्रोटोकॉल एक्सटेंशन (BEP XET)** शामिल है, जो सामग्री-परिभाषित चंकिंग और क्रॉस-टोरेंट डीडुप्लिकेशन को सक्षम करता है। यह BitTorrent को सहयोग के लिए अनुकूलित एक सुपर-फास्ट, अपडेट करने योग्य peer-to-peer फ़ाइल सिस्टम में बदलता है। [BEP XET के बारे में अधिक जानें →](bep_xet.md)

## स्थापना

### आवश्यकताएं

- Python 3.8 या उच्चतर
- [UV](https://astral.sh/uv) पैकेज मैनेजर (अनुशंसित)

### UV स्थापित करें

आधिकारिक स्थापना स्क्रिप्ट से UV स्थापित करें:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ccBitTorrent स्थापित करें

PyPI से स्थापित करें:
```bash
uv pip install ccbittorrent
```

या स्रोत से स्थापित करें:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

एंट्री पॉइंट [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81) में परिभाषित हैं।

## मुख्य एंट्री पॉइंट

ccBitTorrent तीन मुख्य एंट्री पॉइंट प्रदान करता है:

### 1. Bitonic (अनुशंसित)

**Bitonic** मुख्य टर्मिनल डैशबोर्ड इंटरफ़ेस है। यह सभी टोरेंट्स, पीयर्स और सिस्टम मेट्रिक्स का लाइव, इंटरैक्टिव दृश्य प्रदान करता है।

- एंट्री पॉइंट: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- परिभाषित: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- लॉन्च: `uv run bitonic` या `uv run ccbt dashboard`

विस्तृत उपयोग के लिए [Bitonic गाइड](bitonic.md) देखें।

### 2. btbt CLI

**btbt** समृद्ध सुविधाओं के साथ वर्धित कमांड-लाइन इंटरफ़ेस है।

- एंट्री पॉइंट: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- परिभाषित: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- लॉन्च: `uv run btbt`

सभी उपलब्ध कमांड के लिए [btbt CLI संदर्भ](btbt-cli.md) देखें।

### 3. ccbt (मूल CLI)

**ccbt** मूल कमांड-लाइन इंटरफ़ेस है।

- एंट्री पॉइंट: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- परिभाषित: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- लॉन्च: `uv run ccbt`

## त्वरित प्रारंभ

### Bitonic लॉन्च करें (अनुशंसित)

टर्मिनल डैशबोर्ड शुरू करें:
```bash
uv run bitonic
```

या CLI के माध्यम से:
```bash
uv run ccbt dashboard
```

कस्टम रिफ्रेश दर के साथ:
```bash
uv run ccbt dashboard --refresh 2.0
```

### एक टोरेंट डाउनलोड करें

CLI का उपयोग करके:
```bash
# टोरेंट फ़ाइल से डाउनलोड
uv run btbt download movie.torrent

# मैग्नेट लिंक से डाउनलोड
uv run btbt magnet "magnet:?xt=urn:btih:..."

# दर सीमाओं के साथ
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

सभी डाउनलोड विकल्पों के लिए [btbt CLI संदर्भ](btbt-cli.md) देखें।

### ccBitTorrent कॉन्फ़िगर करें

अपने कार्य निर्देशिका में एक `ccbt.toml` फ़ाइल बनाएं। उदाहरण कॉन्फ़िगरेशन देखें:
- डिफ़ॉल्ट कॉन्फ़िग: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- पर्यावरण चर: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- कॉन्फ़िगरेशन सिस्टम: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

विस्तृत कॉन्फ़िगरेशन विकल्पों के लिए [कॉन्फ़िगरेशन गाइड](configuration.md) देखें।

## परियोजना रिपोर्ट

परियोजना गुणवत्ता मेट्रिक्स और रिपोर्ट देखें:

- **कोड कवरेज**: [reports/coverage.md](reports/coverage.md) - व्यापक कोड कवरेज विश्लेषण
- **सुरक्षा रिपोर्ट**: [reports/bandit/index.md](reports/bandit/index.md) - Bandit से सुरक्षा स्कैनिंग परिणाम
- **बेंचमार्क**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - प्रदर्शन बेंचमार्क परिणाम

ये रिपोर्ट हमारी निरंतर एकीकरण प्रक्रिया के हिस्से के रूप में स्वचालित रूप से उत्पन्न और अद्यतन की जाती हैं।

## अगले कदम

- [Bitonic](bitonic.md) - टर्मिनल डैशबोर्ड इंटरफ़ेस के बारे में जानें
- [btbt CLI](btbt-cli.md) - पूर्ण कमांड-लाइन इंटरफ़ेस संदर्भ
- [कॉन्फ़िगरेशन](configuration.md) - विस्तृत कॉन्फ़िगरेशन विकल्प
- [प्रदर्शन ट्यूनिंग](performance.md) - अनुकूलन गाइड
- [API संदर्भ](API.md) - निगरानी सुविधाओं सहित Python API दस्तावेज़

## मदद प्राप्त करना

- कमांड मदद के लिए `uv run bitonic --help` या `uv run btbt --help` का उपयोग करें
- विस्तृत विकल्पों के लिए [btbt CLI संदर्भ](btbt-cli.md) देखें
- समस्याओं और चर्चाओं के लिए हमारे [GitHub रिपॉजिटरी](https://github.com/yourusername/ccbittorrent) पर जाएं
































































































































































































