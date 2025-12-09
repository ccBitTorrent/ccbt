# เริ่มต้น

ยินดีต้อนรับสู่ ccBitTorrent! คู่มือนี้จะช่วยให้คุณเริ่มต้นใช้งานไคลเอนต์ BitTorrent ประสิทธิภาพสูงของเราได้อย่างรวดเร็ว

!!! tip "คุณสมบัติหลัก: ส่วนขยายโปรโตคอล BEP XET"
    ccBitTorrent รวม **ส่วนขยายโปรโตคอล Xet (BEP XET)** ซึ่งเปิดใช้งานการแบ่งส่วนตามเนื้อหาและการลบข้อมูลซ้ำข้าม torrent ซึ่งเปลี่ยน BitTorrent เป็นระบบไฟล์ peer-to-peer ที่เร็วมากและอัปเดตได้ซึ่งปรับให้เหมาะสำหรับการทำงานร่วมกัน [เรียนรู้เพิ่มเติมเกี่ยวกับ BEP XET →](bep_xet.md)

## การติดตั้ง

### ความต้องการเบื้องต้น

- Python 3.8 หรือสูงกว่า
- ตัวจัดการแพ็คเกจ [UV](https://astral.sh/uv) (แนะนำ)

### ติดตั้ง UV

ติดตั้ง UV จากสคริปต์การติดตั้งอย่างเป็นทางการ:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ติดตั้ง ccBitTorrent

ติดตั้งจาก PyPI:
```bash
uv pip install ccbittorrent
```

หรือติดตั้งจากซอร์สโค้ด:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

จุดเข้าใช้งานถูกกำหนดไว้ใน [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81)

## จุดเข้าใช้งานหลัก

ccBitTorrent ให้จุดเข้าใช้งานหลักสามจุด:

### 1. Bitonic (แนะนำ)

**Bitonic** เป็นอินเทอร์เฟซแดชบอร์ดเทอร์มินัลหลัก มันให้มุมมองแบบเรียลไทม์และโต้ตอบได้ของ torrent ทั้งหมด peer และเมตริกระบบ

- จุดเข้าใช้งาน: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- กำหนดไว้ใน: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- เริ่มต้น: `uv run bitonic` หรือ `uv run ccbt dashboard`

ดู [คู่มือ Bitonic](bitonic.md) สำหรับการใช้งานโดยละเอียด

### 2. btbt CLI

**btbt** เป็นอินเทอร์เฟซบรรทัดคำสั่งที่ปรับปรุงแล้วพร้อมคุณสมบัติที่หลากหลาย

- จุดเข้าใช้งาน: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- กำหนดไว้ใน: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- เริ่มต้น: `uv run btbt`

ดู [อ้างอิง btbt CLI](btbt-cli.md) สำหรับคำสั่งทั้งหมดที่มี

### 3. ccbt (CLI พื้นฐาน)

**ccbt** เป็นอินเทอร์เฟซบรรทัดคำสั่งพื้นฐาน

- จุดเข้าใช้งาน: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- กำหนดไว้ใน: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- เริ่มต้น: `uv run ccbt`

## เริ่มต้นอย่างรวดเร็ว

### เริ่ม Bitonic (แนะนำ)

เริ่มแดชบอร์ดเทอร์มินัล:
```bash
uv run bitonic
```

หรือผ่าน CLI:
```bash
uv run ccbt dashboard
```

ด้วยอัตราการรีเฟรชแบบกำหนดเอง:
```bash
uv run ccbt dashboard --refresh 2.0
```

### ดาวน์โหลด Torrent

ใช้ CLI:
```bash
# ดาวน์โหลดจากไฟล์ torrent
uv run btbt download movie.torrent

# ดาวน์โหลดจากลิงก์ magnet
uv run btbt magnet "magnet:?xt=urn:btih:..."

# พร้อมขีดจำกัดอัตรา
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

ดู [อ้างอิง btbt CLI](btbt-cli.md) สำหรับตัวเลือกการดาวน์โหลดทั้งหมด

### กำหนดค่า ccBitTorrent

สร้างไฟล์ `ccbt.toml` ในไดเรกทอรีการทำงานของคุณ ดูการกำหนดค่าตัวอย่าง:
- การกำหนดค่าเริ่มต้น: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- ตัวแปรสภาพแวดล้อม: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- ระบบการกำหนดค่า: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

ดู [คู่มือการกำหนดค่า](configuration.md) สำหรับตัวเลือกการกำหนดค่าโดยละเอียด

## รายงานโครงการ

ดูเมตริกคุณภาพโครงการและรายงาน:

- **ความครอบคลุมของโค้ด**: [reports/coverage.md](reports/coverage.md) - การวิเคราะห์ความครอบคลุมของโค้ดแบบครอบคลุม
- **รายงานความปลอดภัย**: [reports/bandit/index.md](reports/bandit/index.md) - ผลการสแกนความปลอดภัยจาก Bandit
- **เกณฑ์มาตรฐาน**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - ผลเกณฑ์มาตรฐานประสิทธิภาพ

รายงานเหล่านี้ถูกสร้างและอัปเดตโดยอัตโนมัติเป็นส่วนหนึ่งของกระบวนการรวมต่อเนื่องของเรา

## ขั้นตอนถัดไป

- [Bitonic](bitonic.md) - เรียนรู้เกี่ยวกับอินเทอร์เฟซแดชบอร์ดเทอร์มินัล
- [btbt CLI](btbt-cli.md) - อ้างอิงอินเทอร์เฟซบรรทัดคำสั่งแบบเต็ม
- [การกำหนดค่า](configuration.md) - ตัวเลือกการกำหนดค่าโดยละเอียด
- [การปรับแต่งประสิทธิภาพ](performance.md) - คู่มือการปรับปรุง
- [อ้างอิง API](API.md) - เอกสาร API Python รวมถึงคุณสมบัติการตรวจสอบ

## ขอความช่วยเหลือ

- ใช้ `uv run bitonic --help` หรือ `uv run btbt --help` สำหรับความช่วยเหลือคำสั่ง
- ตรวจสอบ [อ้างอิง btbt CLI](btbt-cli.md) สำหรับตัวเลือกโดยละเอียด
- เยี่ยมชม [ที่เก็บ GitHub](https://github.com/yourusername/ccbittorrent) ของเราสำหรับปัญหาและการอภิปราย






ยินดีต้อนรับสู่ ccBitTorrent! คู่มือนี้จะช่วยให้คุณเริ่มต้นใช้งานไคลเอนต์ BitTorrent ประสิทธิภาพสูงของเราได้อย่างรวดเร็ว

!!! tip "คุณสมบัติหลัก: ส่วนขยายโปรโตคอล BEP XET"
    ccBitTorrent รวม **ส่วนขยายโปรโตคอล Xet (BEP XET)** ซึ่งเปิดใช้งานการแบ่งส่วนตามเนื้อหาและการลบข้อมูลซ้ำข้าม torrent ซึ่งเปลี่ยน BitTorrent เป็นระบบไฟล์ peer-to-peer ที่เร็วมากและอัปเดตได้ซึ่งปรับให้เหมาะสำหรับการทำงานร่วมกัน [เรียนรู้เพิ่มเติมเกี่ยวกับ BEP XET →](bep_xet.md)

## การติดตั้ง

### ความต้องการเบื้องต้น

- Python 3.8 หรือสูงกว่า
- ตัวจัดการแพ็คเกจ [UV](https://astral.sh/uv) (แนะนำ)

### ติดตั้ง UV

ติดตั้ง UV จากสคริปต์การติดตั้งอย่างเป็นทางการ:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ติดตั้ง ccBitTorrent

ติดตั้งจาก PyPI:
```bash
uv pip install ccbittorrent
```

หรือติดตั้งจากซอร์สโค้ด:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

จุดเข้าใช้งานถูกกำหนดไว้ใน [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81)

## จุดเข้าใช้งานหลัก

ccBitTorrent ให้จุดเข้าใช้งานหลักสามจุด:

### 1. Bitonic (แนะนำ)

**Bitonic** เป็นอินเทอร์เฟซแดชบอร์ดเทอร์มินัลหลัก มันให้มุมมองแบบเรียลไทม์และโต้ตอบได้ของ torrent ทั้งหมด peer และเมตริกระบบ

- จุดเข้าใช้งาน: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- กำหนดไว้ใน: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- เริ่มต้น: `uv run bitonic` หรือ `uv run ccbt dashboard`

ดู [คู่มือ Bitonic](bitonic.md) สำหรับการใช้งานโดยละเอียด

### 2. btbt CLI

**btbt** เป็นอินเทอร์เฟซบรรทัดคำสั่งที่ปรับปรุงแล้วพร้อมคุณสมบัติที่หลากหลาย

- จุดเข้าใช้งาน: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- กำหนดไว้ใน: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- เริ่มต้น: `uv run btbt`

ดู [อ้างอิง btbt CLI](btbt-cli.md) สำหรับคำสั่งทั้งหมดที่มี

### 3. ccbt (CLI พื้นฐาน)

**ccbt** เป็นอินเทอร์เฟซบรรทัดคำสั่งพื้นฐาน

- จุดเข้าใช้งาน: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- กำหนดไว้ใน: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- เริ่มต้น: `uv run ccbt`

## เริ่มต้นอย่างรวดเร็ว

### เริ่ม Bitonic (แนะนำ)

เริ่มแดชบอร์ดเทอร์มินัล:
```bash
uv run bitonic
```

หรือผ่าน CLI:
```bash
uv run ccbt dashboard
```

ด้วยอัตราการรีเฟรชแบบกำหนดเอง:
```bash
uv run ccbt dashboard --refresh 2.0
```

### ดาวน์โหลด Torrent

ใช้ CLI:
```bash
# ดาวน์โหลดจากไฟล์ torrent
uv run btbt download movie.torrent

# ดาวน์โหลดจากลิงก์ magnet
uv run btbt magnet "magnet:?xt=urn:btih:..."

# พร้อมขีดจำกัดอัตรา
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

ดู [อ้างอิง btbt CLI](btbt-cli.md) สำหรับตัวเลือกการดาวน์โหลดทั้งหมด

### กำหนดค่า ccBitTorrent

สร้างไฟล์ `ccbt.toml` ในไดเรกทอรีการทำงานของคุณ ดูการกำหนดค่าตัวอย่าง:
- การกำหนดค่าเริ่มต้น: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- ตัวแปรสภาพแวดล้อม: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- ระบบการกำหนดค่า: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

ดู [คู่มือการกำหนดค่า](configuration.md) สำหรับตัวเลือกการกำหนดค่าโดยละเอียด

## รายงานโครงการ

ดูเมตริกคุณภาพโครงการและรายงาน:

- **ความครอบคลุมของโค้ด**: [reports/coverage.md](reports/coverage.md) - การวิเคราะห์ความครอบคลุมของโค้ดแบบครอบคลุม
- **รายงานความปลอดภัย**: [reports/bandit/index.md](reports/bandit/index.md) - ผลการสแกนความปลอดภัยจาก Bandit
- **เกณฑ์มาตรฐาน**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - ผลเกณฑ์มาตรฐานประสิทธิภาพ

รายงานเหล่านี้ถูกสร้างและอัปเดตโดยอัตโนมัติเป็นส่วนหนึ่งของกระบวนการรวมต่อเนื่องของเรา

## ขั้นตอนถัดไป

- [Bitonic](bitonic.md) - เรียนรู้เกี่ยวกับอินเทอร์เฟซแดชบอร์ดเทอร์มินัล
- [btbt CLI](btbt-cli.md) - อ้างอิงอินเทอร์เฟซบรรทัดคำสั่งแบบเต็ม
- [การกำหนดค่า](configuration.md) - ตัวเลือกการกำหนดค่าโดยละเอียด
- [การปรับแต่งประสิทธิภาพ](performance.md) - คู่มือการปรับปรุง
- [อ้างอิง API](API.md) - เอกสาร API Python รวมถึงคุณสมบัติการตรวจสอบ

## ขอความช่วยเหลือ

- ใช้ `uv run bitonic --help` หรือ `uv run btbt --help` สำหรับความช่วยเหลือคำสั่ง
- ตรวจสอบ [อ้างอิง btbt CLI](btbt-cli.md) สำหรับตัวเลือกโดยละเอียด
- เยี่ยมชม [ที่เก็บ GitHub](https://github.com/yourusername/ccbittorrent) ของเราสำหรับปัญหาและการอภิปราย
































































































































































































