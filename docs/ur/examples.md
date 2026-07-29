# مثالیں

یہ سیکشن ccBitTorrent استعمال کرنے کے لیے عملی مثالیں اور کوڈ نمونے فراہم کرتا ہے۔

## ترتیب مثالیں

### بنیادی ترتیب

شروع کرنے کے لیے ایک کم از کم ترتیب فائل:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

مکمل بنیادی ترتیب کے لیے [example-config-basic.toml](examples/example-config-basic.toml) دیکھیں۔

### اعلیٰ درجے کی ترتیب

اعلیٰ درجے کے صارفین کے لیے جنہیں باریک کنٹرول کی ضرورت ہے:

اعلیٰ درجے کی ترتیب کے اختیارات کے لیے [example-config-advanced.toml](examples/example-config-advanced.toml) دیکھیں۔

### کارکردگی ترتیب

زیادہ سے زیادہ کارکردگی کے لیے بہتر بنایا گیا سیٹنگز:

کارکردگی ٹیوننگ کے لیے [example-config-performance.toml](examples/example-config-performance.toml) دیکھیں۔

### سیکیورٹی ترتیب

encryption اور تصدیق کے ساتھ سیکیورٹی-مرکوز ترتیب:

سیکیورٹی سیٹنگز کے لیے [example-config-security.toml](examples/example-config-security.toml) دیکھیں۔

## BEP 52 مثالیں

### v2 Torrent بنانا

BitTorrent v2 torrent فائل بنائیں:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# v2 torrent بنائیں
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # 16KB ٹکڑے
)
```

مکمل مثال کے لیے [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) دیکھیں۔

### Hybrid Torrent بنانا

v1 اور v2 دونوں کلائنٹس کے ساتھ کام کرنے والا hybrid torrent بنائیں:

مکمل مثال کے لیے [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) دیکھیں۔

### v2 Torrent پارس کرنا

BitTorrent v2 torrent فائل پارس کریں اور معائنہ کریں:

مکمل مثال کے لیے [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) دیکھیں۔

### پروٹوکول v2 سیشن

سیشن میں BitTorrent v2 پروٹوکول استعمال کریں:

مکمل مثال کے لیے [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) دیکھیں۔

## شروع کرنا

ccBitTorrent کے ساتھ شروع کرنے کے بارے میں مزید معلومات کے لیے [شروع کرنے کی گائیڈ](getting-started.md) دیکھیں۔






یہ سیکشن ccBitTorrent استعمال کرنے کے لیے عملی مثالیں اور کوڈ نمونے فراہم کرتا ہے۔

## ترتیب مثالیں

### بنیادی ترتیب

شروع کرنے کے لیے ایک کم از کم ترتیب فائل:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

مکمل بنیادی ترتیب کے لیے [example-config-basic.toml](examples/example-config-basic.toml) دیکھیں۔

### اعلیٰ درجے کی ترتیب

اعلیٰ درجے کے صارفین کے لیے جنہیں باریک کنٹرول کی ضرورت ہے:

اعلیٰ درجے کی ترتیب کے اختیارات کے لیے [example-config-advanced.toml](examples/example-config-advanced.toml) دیکھیں۔

### کارکردگی ترتیب

زیادہ سے زیادہ کارکردگی کے لیے بہتر بنایا گیا سیٹنگز:

کارکردگی ٹیوننگ کے لیے [example-config-performance.toml](examples/example-config-performance.toml) دیکھیں۔

### سیکیورٹی ترتیب

encryption اور تصدیق کے ساتھ سیکیورٹی-مرکوز ترتیب:

سیکیورٹی سیٹنگز کے لیے [example-config-security.toml](examples/example-config-security.toml) دیکھیں۔

## BEP 52 مثالیں

### v2 Torrent بنانا

BitTorrent v2 torrent فائل بنائیں:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# v2 torrent بنائیں
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # 16KB ٹکڑے
)
```

مکمل مثال کے لیے [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) دیکھیں۔

### Hybrid Torrent بنانا

v1 اور v2 دونوں کلائنٹس کے ساتھ کام کرنے والا hybrid torrent بنائیں:

مکمل مثال کے لیے [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) دیکھیں۔

### v2 Torrent پارس کرنا

BitTorrent v2 torrent فائل پارس کریں اور معائنہ کریں:

مکمل مثال کے لیے [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) دیکھیں۔

### پروٹوکول v2 سیشن

سیشن میں BitTorrent v2 پروٹوکول استعمال کریں:

مکمل مثال کے لیے [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) دیکھیں۔

## شروع کرنا

ccBitTorrent کے ساتھ شروع کرنے کے بارے میں مزید معلومات کے لیے [شروع کرنے کی گائیڈ](getting-started.md) دیکھیں۔
































































































































































































