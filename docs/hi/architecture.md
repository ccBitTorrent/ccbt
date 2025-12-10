# आर्किटेक्चर अवलोकन

यह दस्तावेज़ ccBitTorrent की वास्तुकला, घटकों और डेटा प्रवाह का तकनीकी अवलोकन प्रदान करता है。

## समग्र वास्तुकला

ccBitTorrent एक उच्च-प्रदर्शन BitTorrent क्लाइंट है जो आधुनिक वास्तुकला के साथ अतुल्यकालिक और इवेंट-संचालित पैटर्न का उपयोग करता है।

### वास्तुकला परतें

1. **CLI परत**: कमांड-लाइन इंटरफ़ेस और उपयोगकर्ता इंटरैक्शन
2. **सत्र परत**: torrent जीवनचक्र प्रबंधन और घटक समन्वय
3. **कोर परत**: BitTorrent डोमेन तर्क CLI/सत्र निर्भरताओं के बिना
4. **नेटवर्क परत**: पीयर कनेक्शन प्रबंधन और प्रोटोकॉल संचार
5. **स्टोरेज परत**: डिस्क I/O संचालन और फ़ाइल प्रबंधन

### सत्र प्रबंधन

`AsyncSessionManager` कई torrent सत्रों का समन्वय करता है और विशेष नियंत्रकों को सौंपता है:

- `ccbt/session/announce.py`: Tracker घोषणाएँ
- `ccbt/session/checkpointing.py`: Checkpoint संचालन
- `ccbt/session/download_startup.py`: डाउनलोड प्रारंभिकीकरण
- `ccbt/session/torrent_addition.py`: Torrent जोड़ने का प्रवाह
- `ccbt/session/manager_startup.py`: घटक स्टार्टअप अनुक्रम

### निर्भरता इंजेक्शन

वैकल्पिक DI `ccbt/utils/di.py` के माध्यम से: कारखानों के लिए `DIContainer` (सुरक्षा, DHT, NAT, TCP सर्वर)

### ExecutorManager

CLI और डेमन के लिए एकीकृत कमांड निष्पादन प्रबंधन।

### XetSyncManager

XET प्रोटोकॉल (BEP XET) के लिए फ़ोल्डर सिंक्रनाइज़ेशन प्रबंधन।

## प्रमुख घटक

### पीयर प्रबंधन

- `AsyncPeerConnectionManager`: कनेक्शन पूलिंग के साथ पीयर कनेक्शन प्रबंधन
- `AsyncPeerConnection`: पाइपलाइनिंग, tit-for-tat choking और अनुकूली ब्लॉक आकार के साथ अतुल्यकालिक पीयर कनेक्शन

### पीस प्रबंधन

- `AsyncPieceManager`: दुर्लभतम-पहले और endgame के साथ उन्नत पीस चयन
- `FileSelectionManager`: बहु-फ़ाइल torrent के लिए फ़ाइल चयन और प्राथमिकता प्रबंधन

### खोज

- `AsyncDHTClient`: पीयर खोज के लिए पूर्ण Kademlia कार्यान्वयन के साथ बढ़ाया DHT क्लाइंट (BEP 5)
- `AsyncTrackerClient`: उच्च-प्रदर्शन अतुल्यकालिक tracker संचार
- `AsyncUDPTrackerClient`: अतुल्यकालिक UDP tracker क्लाइंट कार्यान्वयन (BEP 15)

### भंडारण

- `DiskIOManager`: पूर्व-आवंटन, बैचिंग, मेमोरी-मैप्ड I/O और अतुल्यकालिक संचालन के साथ उच्च-प्रदर्शन डिस्क I/O प्रबंधक
- `FileAssembler`: पीस को पूर्ण फ़ाइलों में असेंबल करना
- `CheckpointManager`: रिज़्यूम कार्यक्षमता के लिए checkpoint प्रबंधन

## अतिरिक्त संसाधन

- [शुरुआती गाइड](getting-started.md) - त्वरित प्रारंभ गाइड
- [कॉन्फ़िगरेशन गाइड](configuration.md) - विस्तृत कॉन्फ़िगरेशन
- [API संदर्भ](API.md) - पूर्ण API दस्तावेज़ीकरण

