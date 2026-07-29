# ตัวอย่าง

ส่วนนี้ให้ตัวอย่างและตัวอย่างโค้ดที่ใช้งานได้สำหรับการใช้ ccBitTorrent

## ตัวอย่างการกำหนดค่า

### การกำหนดค่าพื้นฐาน

ไฟล์การกำหนดค่าขั้นต่ำเพื่อเริ่มต้น:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

ดู [example-config-basic.toml](examples/example-config-basic.toml) สำหรับการกำหนดค่าพื้นฐานแบบเต็ม

### การกำหนดค่าขั้นสูง

สำหรับผู้ใช้ขั้นสูงที่ต้องการการควบคุมอย่างละเอียด:

ดู [example-config-advanced.toml](examples/example-config-advanced.toml) สำหรับตัวเลือกการกำหนดค่าขั้นสูง

### การกำหนดค่าประสิทธิภาพ

การตั้งค่าที่ปรับให้เหมาะสำหรับประสิทธิภาพสูงสุด:

ดู [example-config-performance.toml](examples/example-config-performance.toml) สำหรับการปรับแต่งประสิทธิภาพ

### การกำหนดค่าความปลอดภัย

การกำหนดค่าที่เน้นความปลอดภัยพร้อมการเข้ารหัสและการตรวจสอบ:

ดู [example-config-security.toml](examples/example-config-security.toml) สำหรับการตั้งค่าความปลอดภัย

## ตัวอย่าง BEP 52

### สร้าง Torrent v2

สร้างไฟล์ torrent BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# สร้าง torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # ชิ้นส่วน 16KB
)
```

ดู [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) สำหรับตัวอย่างแบบเต็ม

### สร้าง Torrent แบบ Hybrid

สร้าง torrent แบบ hybrid ที่ทำงานกับไคลเอนต์ v1 และ v2:

ดู [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) สำหรับตัวอย่างแบบเต็ม

### แยกวิเคราะห์ Torrent v2

แยกวิเคราะห์และตรวจสอบไฟล์ torrent BitTorrent v2:

ดู [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) สำหรับตัวอย่างแบบเต็ม

### เซสชันโปรโตคอล v2

ใช้โปรโตคอล BitTorrent v2 ในเซสชัน:

ดู [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) สำหรับตัวอย่างแบบเต็ม

## เริ่มต้น

สำหรับข้อมูลเพิ่มเติมเกี่ยวกับการเริ่มต้นด้วย ccBitTorrent ดู [คู่มือเริ่มต้น](getting-started.md)






ส่วนนี้ให้ตัวอย่างและตัวอย่างโค้ดที่ใช้งานได้สำหรับการใช้ ccBitTorrent

## ตัวอย่างการกำหนดค่า

### การกำหนดค่าพื้นฐาน

ไฟล์การกำหนดค่าขั้นต่ำเพื่อเริ่มต้น:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

ดู [example-config-basic.toml](examples/example-config-basic.toml) สำหรับการกำหนดค่าพื้นฐานแบบเต็ม

### การกำหนดค่าขั้นสูง

สำหรับผู้ใช้ขั้นสูงที่ต้องการการควบคุมอย่างละเอียด:

ดู [example-config-advanced.toml](examples/example-config-advanced.toml) สำหรับตัวเลือกการกำหนดค่าขั้นสูง

### การกำหนดค่าประสิทธิภาพ

การตั้งค่าที่ปรับให้เหมาะสำหรับประสิทธิภาพสูงสุด:

ดู [example-config-performance.toml](examples/example-config-performance.toml) สำหรับการปรับแต่งประสิทธิภาพ

### การกำหนดค่าความปลอดภัย

การกำหนดค่าที่เน้นความปลอดภัยพร้อมการเข้ารหัสและการตรวจสอบ:

ดู [example-config-security.toml](examples/example-config-security.toml) สำหรับการตั้งค่าความปลอดภัย

## ตัวอย่าง BEP 52

### สร้าง Torrent v2

สร้างไฟล์ torrent BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# สร้าง torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # ชิ้นส่วน 16KB
)
```

ดู [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) สำหรับตัวอย่างแบบเต็ม

### สร้าง Torrent แบบ Hybrid

สร้าง torrent แบบ hybrid ที่ทำงานกับไคลเอนต์ v1 และ v2:

ดู [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) สำหรับตัวอย่างแบบเต็ม

### แยกวิเคราะห์ Torrent v2

แยกวิเคราะห์และตรวจสอบไฟล์ torrent BitTorrent v2:

ดู [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) สำหรับตัวอย่างแบบเต็ม

### เซสชันโปรโตคอล v2

ใช้โปรโตคอล BitTorrent v2 ในเซสชัน:

ดู [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) สำหรับตัวอย่างแบบเต็ม

## เริ่มต้น

สำหรับข้อมูลเพิ่มเติมเกี่ยวกับการเริ่มต้นด้วย ccBitTorrent ดู [คู่มือเริ่มต้น](getting-started.md)
































































































































































































