# ccBT API संदर्भ

ccBitTorrent के लिए व्यापक API दस्तावेज़ीकरण, वास्तविक कार्यान्वयन फ़ाइलों के संदर्भ के साथ।

## प्रवेश बिंदु

### मुख्य प्रवेश बिंदु (ccbt)

मूल torrent संचालन के लिए मुख्य कमांड-लाइन प्रवेश बिंदु।

कार्यान्वयन: [ccbt/__main__.py:main](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L18)

सुविधाएँ:
- एकल torrent डाउनलोड मोड
- बहु torrent सत्रों के लिए डेमन मोड: [ccbt/__main__.py:52](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L52)
- Magnet URI समर्थन: [ccbt/__main__.py:73](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L73)
- Tracker घोषणा: [ccbt/__main__.py:89](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/__main__.py#L89)

प्रवेश बिंदु कॉन्फ़िगरेशन: [pyproject.toml:79](https://github.com/ccBitTorrent/ccbt/blob/main/pyproject.toml#L79)

### अतुल्यकालिक डाउनलोड सहायक

उन्नत संचालन के लिए उच्च-प्रदर्शन अतुल्यकालिक सहायक और डाउनलोड प्रबंधक।

कार्यान्वयन: [ccbt/session/download_manager.py](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/download_manager.py)

मुख्य निर्यात:
- `AsyncDownloadManager`
- `download_torrent()`
- `download_magnet()`

## सत्र प्रबंधन

### AsyncSessionManager

कई torrent के लिए उच्च-प्रदर्शन अतुल्यकालिक सत्र प्रबंधक।

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

अतुल्यकालिक संचालन के साथ एक सक्रिय torrent के जीवनचक्र का प्रतिनिधित्व करने वाला व्यक्तिगत torrent सत्र।

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

**मुख्य विधियाँ:**

- `start()`: [ccbt/session/session.py:start](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L400) - torrent सत्र शुरू करें, डाउनलोड प्रबंधक, trackers और PEX को प्रारंभ करें
- `stop()`: [ccbt/session/session.py:stop](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py#L678) - torrent सत्र रोकें, checkpoint सहेजें, संसाधन साफ़ करें
- `pause()`: [ccbt/session/session.py:pause](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - डाउनलोड रोकें
- `resume()`: [ccbt/session/session.py:resume](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - डाउनलोड फिर से शुरू करें
- `get_status()`: [ccbt/session/session.py:get_status](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/session/session.py) - torrent स्थिति प्राप्त करें

## कॉन्फ़िगरेशन

### ConfigManager

हॉट-रिलोड, पदानुक्रमित लोडिंग और सत्यापन के साथ कॉन्फ़िगरेशन प्रबंधन।

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

**सुविधाएँ:**
- कॉन्फ़िगरेशन लोडिंग: [ccbt/config/config.py:_load_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L76)
- फ़ाइल खोज: [ccbt/config/config.py:_find_config_file](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L55)
- पर्यावरण चर पार्सिंग: [ccbt/config/config.py:_get_env_config](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py)
- हॉट रीलोड समर्थन: [ccbt/config/config.py:ConfigManager](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/config/config.py#L40)
- CLI ओवरराइड: [ccbt/cli/overrides.py:apply_cli_overrides](https://github.com/ccBitTorrent/ccbt/blob/main/ccbt/cli/overrides.py)

**कॉन्फ़िगरेशन प्राथमिकता:**
1. `ccbt/models.py:Config` से डिफ़ॉल्ट मान
2. कॉन्फ़िग फ़ाइल (वर्तमान निर्देशिका में `ccbt.toml` या `~/.config/ccbt/ccbt.toml`)
3. पर्यावरण चर (`CCBT_*` उपसर्ग)
4. CLI तर्क (`apply_cli_overrides()` के माध्यम से)
5. प्रति torrent डिफ़ॉल्ट
6. प्रति torrent ओवरराइड

## अतिरिक्त संसाधन

- [शुरुआती गाइड](getting-started.md) - त्वरित प्रारंभ गाइड
- [कॉन्फ़िगरेशन गाइड](configuration.md) - विस्तृत कॉन्फ़िगरेशन
- [प्रदर्शन ट्यूनिंग](performance.md) - प्रदर्शन अनुकूलन
- [Bitonic गाइड](bitonic.md) - टर्मिनल डैशबोर्ड
- [btbt CLI संदर्भ](btbt-cli.md) - CLI दस्तावेज़ीकरण

