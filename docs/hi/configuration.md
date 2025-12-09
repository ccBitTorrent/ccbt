# कॉन्फ़िगरेशन गाइड

ccBitTorrent TOML समर्थन, सत्यापन, हॉट-रीलोड, और कई स्रोतों से पदानुक्रमित लोडिंग के साथ एक व्यापक कॉन्फ़िगरेशन सिस्टम का उपयोग करता है।

कॉन्फ़िगरेशन सिस्टम: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## कॉन्फ़िगरेशन स्रोत और प्राथमिकता

कॉन्फ़िगरेशन इस क्रम में लोड होता है (बाद के स्रोत पहले वाले को ओवरराइड करते हैं):

1. **डिफ़ॉल्ट**: [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) से अंतर्निहित समझदार डिफ़ॉल्ट
2. **कॉन्फ़िग फ़ाइल**: वर्तमान निर्देशिका या `~/.config/ccbt/ccbt.toml` में `ccbt.toml`। देखें: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **पर्यावरण चर**: `CCBT_*` उपसर्ग चर। देखें: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI तर्क**: कमांड-लाइन ओवरराइड। देखें: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **प्रति-टोरेंट**: व्यक्तिगत टोरेंट सेटिंग्स (भविष्य की सुविधा)

कॉन्फ़िगरेशन लोडिंग: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## कॉन्फ़िगरेशन फ़ाइल

### डिफ़ॉल्ट कॉन्फ़िगरेशन

डिफ़ॉल्ट कॉन्फ़िगरेशन फ़ाइल देखें: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

कॉन्फ़िगरेशन खंडों में व्यवस्थित है:

### नेटवर्क कॉन्फ़िगरेशन

नेटवर्क सेटिंग्स: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- कनेक्शन सीमाएं: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- अनुरोध पाइपलाइन: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- सॉकेट ट्यूनिंग: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- टाइमआउट: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- सुनने की सेटिंग्स: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- परिवहन प्रोटोकॉल: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- दर सीमाएं: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- चोकिंग रणनीति: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- ट्रैकर सेटिंग्स: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

नेटवर्क कॉन्फ़िग मॉडल: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### डिस्क कॉन्फ़िगरेशन

डिस्क सेटिंग्स: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- पूर्व-आवंटन: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- लेखन अनुकूलन: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- हैश सत्यापन: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O थ्रेडिंग: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- उन्नत सेटिंग्स: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- स्टोरेज सेवा सेटिंग्स: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: स्टोरेज सेवा के लिए MB में अधिकतम फ़ाइल आकार सीमा (0 या None = असीमित, अधिकतम 1048576 = 1TB)। परीक्षण के दौरान असीमित डिस्क लेखन को रोकता है और उत्पादन उपयोग के लिए कॉन्फ़िगर किया जा सकता है।
- चेकपॉइंट सेटिंग्स: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

डिस्क कॉन्फ़िग मॉडल: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### रणनीति कॉन्फ़िगरेशन

रणनीति सेटिंग्स: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- टुकड़ा चयन: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- उन्नत रणनीति: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- टुकड़ा प्राथमिकताएं: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

रणनीति कॉन्फ़िग मॉडल: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### खोज कॉन्फ़िगरेशन

खोज सेटिंग्स: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT सेटिंग्स: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX सेटिंग्स: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- ट्रैकर सेटिंग्स: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: सेकंड में ट्रैकर घोषणा अंतराल (डिफ़ॉल्ट: 1800.0, सीमा: 60.0-86400.0)
  - `tracker_scrape_interval`: आवधिक स्क्रैपिंग के लिए सेकंड में ट्रैकर स्क्रैप अंतराल (डिफ़ॉल्ट: 3600.0, सीमा: 60.0-86400.0)
  - `tracker_auto_scrape`: टोरेंट्स जोड़े जाने पर स्वचालित रूप से ट्रैकर्स को स्क्रैप करें (BEP 48) (डिफ़ॉल्ट: false)
  - पर्यावरण चर: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

खोज कॉन्फ़िग मॉडल: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### सीमा कॉन्फ़िगरेशन

दर सीमाएं: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- वैश्विक सीमाएं: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- प्रति-टोरेंट सीमाएं: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- प्रति-पीयर सीमाएं: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- शेड्यूलर सेटिंग्स: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

सीमा कॉन्फ़िग मॉडल: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### अवलोकन कॉन्फ़िगरेशन

अवलोकन सेटिंग्स: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- लॉगिंग: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- मेट्रिक्स: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- ट्रेसिंग और अलर्ट: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

अवलोकन कॉन्फ़िग मॉडल: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### सुरक्षा कॉन्फ़िगरेशन

सुरक्षा सेटिंग्स: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

सुरक्षा कॉन्फ़िग मॉडल: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### एन्क्रिप्शन कॉन्फ़िगरेशन

ccBitTorrent सुरक्षित पीयर कनेक्शन के लिए BEP 3 Message Stream Encryption (MSE) और Protocol Encryption (PE) का समर्थन करता है।

**एन्क्रिप्शन सेटिंग्स:**

- `enable_encryption` (bool, डिफ़ॉल्ट: `false`): प्रोटोकॉल एन्क्रिप्शन समर्थन सक्षम करें
- `encryption_mode` (str, डिफ़ॉल्ट: `"preferred"`): एन्क्रिप्शन मोड
  - `"disabled"`: कोई एन्क्रिप्शन नहीं (केवल सादे कनेक्शन)
  - `"preferred"`: एन्क्रिप्शन का प्रयास करें, अनुपलब्ध होने पर सादे में फॉलबैक
  - `"required"`: एन्क्रिप्शन अनिवार्य, एन्क्रिप्शन अनुपलब्ध होने पर कनेक्शन विफल
- `encryption_dh_key_size` (int, डिफ़ॉल्ट: `768`): बिट्स में Diffie-Hellman कुंजी आकार (768 या 1024)
- `encryption_prefer_rc4` (bool, डिफ़ॉल्ट: `true`): पुराने क्लाइंट के साथ संगतता के लिए RC4 सिफर पसंद करें
- `encryption_allowed_ciphers` (list[str], डिफ़ॉल्ट: `["rc4", "aes"]`): अनुमतित सिफर प्रकार
  - `"rc4"`: RC4 स्ट्रीम सिफर (सबसे संगत)
  - `"aes"`: CFB मोड में AES सिफर (अधिक सुरक्षित)
  - `"chacha20"`: ChaCha20 सिफर (अभी तक लागू नहीं)
- `encryption_allow_plain_fallback` (bool, डिफ़ॉल्ट: `true`): एन्क्रिप्शन विफल होने पर सादे कनेक्शन में फॉलबैक की अनुमति दें (केवल तब लागू होता है जब `encryption_mode` `"preferred"` है)

**पर्यावरण चर:**

- `CCBT_ENABLE_ENCRYPTION`: एन्क्रिप्शन सक्षम/अक्षम (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: एन्क्रिप्शन मोड (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DH कुंजी आकार (`768` या `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: RC4 पसंद करें (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: अल्पविराम-विभाजित सूची (उदा., `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: सादा फॉलबैक की अनुमति दें (`true`/`false`)

**कॉन्फ़िगरेशन उदाहरण:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**सुरक्षा विचार:**

1. **RC4 संगतता**: RC4 संगतता के लिए समर्थित है लेकिन क्रिप्टोग्राफिक रूप से कमजोर है। जब संभव हो तो बेहतर सुरक्षा के लिए AES का उपयोग करें।
2. **DH कुंजी आकार**: 768-बिट DH कुंजियां अधिकांश उपयोग मामलों के लिए पर्याप्त सुरक्षा प्रदान करती हैं। 1024-बिट अधिक मजबूत सुरक्षा प्रदान करता है लेकिन हैंडशेक विलंबता बढ़ाता है।
3. **एन्क्रिप्शन मोड**:
   - `preferred`: संगतता के लिए सर्वोत्तम - एन्क्रिप्शन का प्रयास करता है लेकिन सुरुचिपूर्ण रूप से फॉलबैक करता है
   - `required`: सबसे सुरक्षित लेकिन एन्क्रिप्शन का समर्थन न करने वाले पीयर्स से कनेक्ट करने में विफल हो सकता है
4. **प्रदर्शन प्रभाव**: एन्क्रिप्शन न्यूनतम ओवरहेड जोड़ता है (RC4 के लिए ~1-5%, AES के लिए ~2-8%) लेकिन गोपनीयता में सुधार करता है और ट्रैफ़िक शेपिंग से बचने में मदद करता है।

**कार्यान्वयन विवरण:**

एन्क्रिप्शन कार्यान्वयन: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE हैंडशेक: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- सिफर सूट: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman एक्सचेंज: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML कॉन्फ़िगरेशन

मशीन लर्निंग सेटिंग्स: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML कॉन्फ़िग मॉडल: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### डैशबोर्ड कॉन्फ़िगरेशन

डैशबोर्ड सेटिंग्स: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

डैशबोर्ड कॉन्फ़िग मॉडल: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## पर्यावरण चर

पर्यावरण चर `CCBT_` उपसर्ग का उपयोग करते हैं और एक पदानुक्रमित नामकरण योजना का पालन करते हैं।

संदर्भ: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

प्रारूप: `CCBT_<SECTION>_<OPTION>=<value>`

उदाहरण:
- नेटवर्क: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- डिस्क: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- रणनीति: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- खोज: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- अवलोकन: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- सीमाएं: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- सुरक्षा: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

पर्यावरण चर पार्सिंग: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## कॉन्फ़िगरेशन स्कीमा

कॉन्फ़िगरेशन स्कीमा और सत्यापन: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

स्कीमा परिभाषित करता है:
- फ़ील्ड प्रकार और बाधाएं
- डिफ़ॉल्ट मान
- सत्यापन नियम
- दस्तावेज़ीकरण

## कॉन्फ़िगरेशन क्षमताएं

कॉन्फ़िगरेशन क्षमताएं और सुविधा पहचान: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## कॉन्फ़िगरेशन टेम्प्लेट

पूर्वनिर्धारित कॉन्फ़िगरेशन टेम्प्लेट: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

टेम्प्लेट:
- उच्च प्रदर्शन सेटअप
- कम संसाधन सेटअप
- सुरक्षा-केंद्रित सेटअप
- विकास सेटअप

## कॉन्फ़िगरेशन उदाहरण

उदाहरण कॉन्फ़िगरेशन [examples/](examples/) निर्देशिका में उपलब्ध हैं:

- मूल कॉन्फ़िगरेशन: [example-config-basic.toml](examples/example-config-basic.toml)
- उन्नत कॉन्फ़िगरेशन: [example-config-advanced.toml](examples/example-config-advanced.toml)
- प्रदर्शन कॉन्फ़िगरेशन: [example-config-performance.toml](examples/example-config-performance.toml)
- सुरक्षा कॉन्फ़िगरेशन: [example-config-security.toml](examples/example-config-security.toml)

## हॉट रीलोड

कॉन्फ़िगरेशन हॉट-रीलोड समर्थन: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

कॉन्फ़िगरेशन सिस्टम क्लाइंट को पुनरारंभ किए बिना परिवर्तनों को रीलोड करने का समर्थन करता है।

## कॉन्फ़िगरेशन माइग्रेशन

कॉन्फ़िगरेशन माइग्रेशन उपयोगिताएं: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

कॉन्फ़िगरेशन संस्करणों के बीच माइग्रेट करने के लिए उपकरण।

## कॉन्फ़िगरेशन बैकअप और डिफ

कॉन्फ़िगरेशन प्रबंधन उपयोगिताएं:
- बैकअप: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- डिफ: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## सशर्त कॉन्फ़िगरेशन

सशर्त कॉन्फ़िगरेशन समर्थन: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## सुझाव और सर्वोत्तम अभ्यास

### प्रदर्शन ट्यूनिंग

- बड़े अनुक्रमिक लेखन के लिए `disk.write_buffer_kib` बढ़ाएं: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- बेहतर लेखन थ्रूपुट के लिए Linux/NVMe पर `direct_io` सक्षम करें: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- अपने नेटवर्क के लिए `network.pipeline_depth` और `network.block_size_kib` ट्यून करें: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### संसाधन अनुकूलन

- CPU कोर के आधार पर `disk.hash_workers` समायोजित करें: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- उपलब्ध RAM के आधार पर `disk.cache_size_mb` कॉन्फ़िगर करें: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- बैंडविड्थ के आधार पर `network.max_global_peers` सेट करें: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### नेटवर्क कॉन्फ़िगरेशन

- नेटवर्क स्थितियों के आधार पर टाइमआउट कॉन्फ़िगर करें: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- आवश्यकतानुसार प्रोटोकॉल सक्षम/अक्षम करें: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- उचित रूप से दर सीमाएं सेट करें: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

विस्तृत प्रदर्शन ट्यूनिंग के लिए [प्रदर्शन ट्यूनिंग गाइड](performance.md) देखें।






ccBitTorrent TOML समर्थन, सत्यापन, हॉट-रीलोड, और कई स्रोतों से पदानुक्रमित लोडिंग के साथ एक व्यापक कॉन्फ़िगरेशन सिस्टम का उपयोग करता है।

कॉन्फ़िगरेशन सिस्टम: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## कॉन्फ़िगरेशन स्रोत और प्राथमिकता

कॉन्फ़िगरेशन इस क्रम में लोड होता है (बाद के स्रोत पहले वाले को ओवरराइड करते हैं):

1. **डिफ़ॉल्ट**: [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py) से अंतर्निहित समझदार डिफ़ॉल्ट
2. **कॉन्फ़िग फ़ाइल**: वर्तमान निर्देशिका या `~/.config/ccbt/ccbt.toml` में `ccbt.toml`। देखें: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **पर्यावरण चर**: `CCBT_*` उपसर्ग चर। देखें: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **CLI तर्क**: कमांड-लाइन ओवरराइड। देखें: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **प्रति-टोरेंट**: व्यक्तिगत टोरेंट सेटिंग्स (भविष्य की सुविधा)

कॉन्फ़िगरेशन लोडिंग: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## कॉन्फ़िगरेशन फ़ाइल

### डिफ़ॉल्ट कॉन्फ़िगरेशन

डिफ़ॉल्ट कॉन्फ़िगरेशन फ़ाइल देखें: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

कॉन्फ़िगरेशन खंडों में व्यवस्थित है:

### नेटवर्क कॉन्फ़िगरेशन

नेटवर्क सेटिंग्स: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- कनेक्शन सीमाएं: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- अनुरोध पाइपलाइन: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- सॉकेट ट्यूनिंग: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- टाइमआउट: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- सुनने की सेटिंग्स: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- परिवहन प्रोटोकॉल: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- दर सीमाएं: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- चोकिंग रणनीति: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- ट्रैकर सेटिंग्स: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

नेटवर्क कॉन्फ़िग मॉडल: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### डिस्क कॉन्फ़िगरेशन

डिस्क सेटिंग्स: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- पूर्व-आवंटन: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- लेखन अनुकूलन: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- हैश सत्यापन: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O थ्रेडिंग: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- उन्नत सेटिंग्स: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- स्टोरेज सेवा सेटिंग्स: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: स्टोरेज सेवा के लिए MB में अधिकतम फ़ाइल आकार सीमा (0 या None = असीमित, अधिकतम 1048576 = 1TB)। परीक्षण के दौरान असीमित डिस्क लेखन को रोकता है और उत्पादन उपयोग के लिए कॉन्फ़िगर किया जा सकता है।
- चेकपॉइंट सेटिंग्स: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

डिस्क कॉन्फ़िग मॉडल: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### रणनीति कॉन्फ़िगरेशन

रणनीति सेटिंग्स: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- टुकड़ा चयन: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- उन्नत रणनीति: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- टुकड़ा प्राथमिकताएं: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

रणनीति कॉन्फ़िग मॉडल: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### खोज कॉन्फ़िगरेशन

खोज सेटिंग्स: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- DHT सेटिंग्स: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- PEX सेटिंग्स: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- ट्रैकर सेटिंग्स: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: सेकंड में ट्रैकर घोषणा अंतराल (डिफ़ॉल्ट: 1800.0, सीमा: 60.0-86400.0)
  - `tracker_scrape_interval`: आवधिक स्क्रैपिंग के लिए सेकंड में ट्रैकर स्क्रैप अंतराल (डिफ़ॉल्ट: 3600.0, सीमा: 60.0-86400.0)
  - `tracker_auto_scrape`: टोरेंट्स जोड़े जाने पर स्वचालित रूप से ट्रैकर्स को स्क्रैप करें (BEP 48) (डिफ़ॉल्ट: false)
  - पर्यावरण चर: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

खोज कॉन्फ़िग मॉडल: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### सीमा कॉन्फ़िगरेशन

दर सीमाएं: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- वैश्विक सीमाएं: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- प्रति-टोरेंट सीमाएं: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- प्रति-पीयर सीमाएं: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- शेड्यूलर सेटिंग्स: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

सीमा कॉन्फ़िग मॉडल: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### अवलोकन कॉन्फ़िगरेशन

अवलोकन सेटिंग्स: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- लॉगिंग: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- मेट्रिक्स: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- ट्रेसिंग और अलर्ट: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

अवलोकन कॉन्फ़िग मॉडल: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### सुरक्षा कॉन्फ़िगरेशन

सुरक्षा सेटिंग्स: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

सुरक्षा कॉन्फ़िग मॉडल: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### एन्क्रिप्शन कॉन्फ़िगरेशन

ccBitTorrent सुरक्षित पीयर कनेक्शन के लिए BEP 3 Message Stream Encryption (MSE) और Protocol Encryption (PE) का समर्थन करता है।

**एन्क्रिप्शन सेटिंग्स:**

- `enable_encryption` (bool, डिफ़ॉल्ट: `false`): प्रोटोकॉल एन्क्रिप्शन समर्थन सक्षम करें
- `encryption_mode` (str, डिफ़ॉल्ट: `"preferred"`): एन्क्रिप्शन मोड
  - `"disabled"`: कोई एन्क्रिप्शन नहीं (केवल सादे कनेक्शन)
  - `"preferred"`: एन्क्रिप्शन का प्रयास करें, अनुपलब्ध होने पर सादे में फॉलबैक
  - `"required"`: एन्क्रिप्शन अनिवार्य, एन्क्रिप्शन अनुपलब्ध होने पर कनेक्शन विफल
- `encryption_dh_key_size` (int, डिफ़ॉल्ट: `768`): बिट्स में Diffie-Hellman कुंजी आकार (768 या 1024)
- `encryption_prefer_rc4` (bool, डिफ़ॉल्ट: `true`): पुराने क्लाइंट के साथ संगतता के लिए RC4 सिफर पसंद करें
- `encryption_allowed_ciphers` (list[str], डिफ़ॉल्ट: `["rc4", "aes"]`): अनुमतित सिफर प्रकार
  - `"rc4"`: RC4 स्ट्रीम सिफर (सबसे संगत)
  - `"aes"`: CFB मोड में AES सिफर (अधिक सुरक्षित)
  - `"chacha20"`: ChaCha20 सिफर (अभी तक लागू नहीं)
- `encryption_allow_plain_fallback` (bool, डिफ़ॉल्ट: `true`): एन्क्रिप्शन विफल होने पर सादे कनेक्शन में फॉलबैक की अनुमति दें (केवल तब लागू होता है जब `encryption_mode` `"preferred"` है)

**पर्यावरण चर:**

- `CCBT_ENABLE_ENCRYPTION`: एन्क्रिप्शन सक्षम/अक्षम (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: एन्क्रिप्शन मोड (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: DH कुंजी आकार (`768` या `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: RC4 पसंद करें (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: अल्पविराम-विभाजित सूची (उदा., `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: सादा फॉलबैक की अनुमति दें (`true`/`false`)

**कॉन्फ़िगरेशन उदाहरण:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**सुरक्षा विचार:**

1. **RC4 संगतता**: RC4 संगतता के लिए समर्थित है लेकिन क्रिप्टोग्राफिक रूप से कमजोर है। जब संभव हो तो बेहतर सुरक्षा के लिए AES का उपयोग करें।
2. **DH कुंजी आकार**: 768-बिट DH कुंजियां अधिकांश उपयोग मामलों के लिए पर्याप्त सुरक्षा प्रदान करती हैं। 1024-बिट अधिक मजबूत सुरक्षा प्रदान करता है लेकिन हैंडशेक विलंबता बढ़ाता है।
3. **एन्क्रिप्शन मोड**:
   - `preferred`: संगतता के लिए सर्वोत्तम - एन्क्रिप्शन का प्रयास करता है लेकिन सुरुचिपूर्ण रूप से फॉलबैक करता है
   - `required`: सबसे सुरक्षित लेकिन एन्क्रिप्शन का समर्थन न करने वाले पीयर्स से कनेक्ट करने में विफल हो सकता है
4. **प्रदर्शन प्रभाव**: एन्क्रिप्शन न्यूनतम ओवरहेड जोड़ता है (RC4 के लिए ~1-5%, AES के लिए ~2-8%) लेकिन गोपनीयता में सुधार करता है और ट्रैफ़िक शेपिंग से बचने में मदद करता है।

**कार्यान्वयन विवरण:**

एन्क्रिप्शन कार्यान्वयन: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE हैंडशेक: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- सिफर सूट: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Diffie-Hellman एक्सचेंज: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### ML कॉन्फ़िगरेशन

मशीन लर्निंग सेटिंग्स: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

ML कॉन्फ़िग मॉडल: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### डैशबोर्ड कॉन्फ़िगरेशन

डैशबोर्ड सेटिंग्स: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

डैशबोर्ड कॉन्फ़िग मॉडल: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## पर्यावरण चर

पर्यावरण चर `CCBT_` उपसर्ग का उपयोग करते हैं और एक पदानुक्रमित नामकरण योजना का पालन करते हैं।

संदर्भ: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

प्रारूप: `CCBT_<SECTION>_<OPTION>=<value>`

उदाहरण:
- नेटवर्क: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- डिस्क: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- रणनीति: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- खोज: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- अवलोकन: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- सीमाएं: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- सुरक्षा: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

पर्यावरण चर पार्सिंग: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## कॉन्फ़िगरेशन स्कीमा

कॉन्फ़िगरेशन स्कीमा और सत्यापन: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

स्कीमा परिभाषित करता है:
- फ़ील्ड प्रकार और बाधाएं
- डिफ़ॉल्ट मान
- सत्यापन नियम
- दस्तावेज़ीकरण

## कॉन्फ़िगरेशन क्षमताएं

कॉन्फ़िगरेशन क्षमताएं और सुविधा पहचान: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## कॉन्फ़िगरेशन टेम्प्लेट

पूर्वनिर्धारित कॉन्फ़िगरेशन टेम्प्लेट: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

टेम्प्लेट:
- उच्च प्रदर्शन सेटअप
- कम संसाधन सेटअप
- सुरक्षा-केंद्रित सेटअप
- विकास सेटअप

## कॉन्फ़िगरेशन उदाहरण

उदाहरण कॉन्फ़िगरेशन [examples/](examples/) निर्देशिका में उपलब्ध हैं:

- मूल कॉन्फ़िगरेशन: [example-config-basic.toml](examples/example-config-basic.toml)
- उन्नत कॉन्फ़िगरेशन: [example-config-advanced.toml](examples/example-config-advanced.toml)
- प्रदर्शन कॉन्फ़िगरेशन: [example-config-performance.toml](examples/example-config-performance.toml)
- सुरक्षा कॉन्फ़िगरेशन: [example-config-security.toml](examples/example-config-security.toml)

## हॉट रीलोड

कॉन्फ़िगरेशन हॉट-रीलोड समर्थन: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

कॉन्फ़िगरेशन सिस्टम क्लाइंट को पुनरारंभ किए बिना परिवर्तनों को रीलोड करने का समर्थन करता है।

## कॉन्फ़िगरेशन माइग्रेशन

कॉन्फ़िगरेशन माइग्रेशन उपयोगिताएं: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

कॉन्फ़िगरेशन संस्करणों के बीच माइग्रेट करने के लिए उपकरण।

## कॉन्फ़िगरेशन बैकअप और डिफ

कॉन्फ़िगरेशन प्रबंधन उपयोगिताएं:
- बैकअप: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- डिफ: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## सशर्त कॉन्फ़िगरेशन

सशर्त कॉन्फ़िगरेशन समर्थन: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## सुझाव और सर्वोत्तम अभ्यास

### प्रदर्शन ट्यूनिंग

- बड़े अनुक्रमिक लेखन के लिए `disk.write_buffer_kib` बढ़ाएं: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- बेहतर लेखन थ्रूपुट के लिए Linux/NVMe पर `direct_io` सक्षम करें: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- अपने नेटवर्क के लिए `network.pipeline_depth` और `network.block_size_kib` ट्यून करें: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### संसाधन अनुकूलन

- CPU कोर के आधार पर `disk.hash_workers` समायोजित करें: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- उपलब्ध RAM के आधार पर `disk.cache_size_mb` कॉन्फ़िगर करें: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- बैंडविड्थ के आधार पर `network.max_global_peers` सेट करें: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### नेटवर्क कॉन्फ़िगरेशन

- नेटवर्क स्थितियों के आधार पर टाइमआउट कॉन्फ़िगर करें: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- आवश्यकतानुसार प्रोटोकॉल सक्षम/अक्षम करें: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- उचित रूप से दर सीमाएं सेट करें: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

विस्तृत प्रदर्शन ट्यूनिंग के लिए [प्रदर्शन ट्यूनिंग गाइड](performance.md) देखें।
































































































































































































