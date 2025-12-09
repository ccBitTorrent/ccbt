# คู่มือการกำหนดค่า

ccBitTorrent ใช้ระบบการกำหนดค่าที่ครอบคลุมพร้อมการรองรับ TOML การตรวจสอบ การโหลดซ้ำแบบร้อน และการโหลดแบบลำดับชั้นจากหลายแหล่ง

ระบบการกำหนดค่า: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## แหล่งที่มาของการกำหนดค่าและลำดับความสำคัญ

การกำหนดค่าถูกโหลดตามลำดับนี้ (แหล่งที่มาทีหลังจะแทนที่แหล่งที่มาก่อน):

1. **ค่าเริ่มต้น**: ค่าเริ่มต้นที่สมเหตุสมผลในตัวจาก [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **ไฟล์การกำหนดค่า**: `ccbt.toml` ในไดเรกทอรีปัจจุบันหรือ `~/.config/ccbt/ccbt.toml` ดู: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **ตัวแปรสภาพแวดล้อม**: ตัวแปรที่มีคำนำหน้า `CCBT_*` ดู: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **อาร์กิวเมนต์ CLI**: การแทนที่บรรทัดคำสั่ง ดู: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **ต่อ Torrent**: การตั้งค่า torrent แต่ละรายการ (คุณสมบัติในอนาคต)

การโหลดการกำหนดค่า: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## ไฟล์การกำหนดค่า

### การกำหนดค่าเริ่มต้น

ดูไฟล์การกำหนดค่าเริ่มต้น: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

การกำหนดค่าถูกจัดระเบียบเป็นส่วน:

### การกำหนดค่าเครือข่าย

การตั้งค่าเครือข่าย: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- ขีดจำกัดการเชื่อมต่อ: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- Pipeline คำขอ: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- การปรับแต่ง Socket: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- Timeouts: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- การตั้งค่าการฟัง: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- โปรโตคอลการขนส่ง: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- ขีดจำกัดอัตรา: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- กลยุทธ์การ Choking: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- การตั้งค่า Tracker: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

โมเดลการกำหนดค่าเครือข่าย: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่าดิสก์

การตั้งค่าดิสก์: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- การจัดสรรล่วงหน้า: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- การปรับปรุงการเขียน: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- การตรวจสอบ Hash: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O Threading: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- การตั้งค่าขั้นสูง: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- การตั้งค่าบริการจัดเก็บข้อมูล: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: ขีดจำกัดขนาดไฟล์สูงสุดใน MB สำหรับบริการจัดเก็บข้อมูล (0 หรือ None = ไม่จำกัด, สูงสุด 1048576 = 1TB) ป้องกันการเขียนดิสก์ไม่จำกัดระหว่างการทดสอบและสามารถกำหนดค่าสำหรับการใช้งานในโปรดักชัน
- การตั้งค่า Checkpoint: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

โมเดลการกำหนดค่าดิสก์: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่ากลยุทธ์

การตั้งค่ากลยุทธ์: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- การเลือกชิ้นส่วน: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- กลยุทธ์ขั้นสูง: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- ลำดับความสำคัญของชิ้นส่วน: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

โมเดลการกำหนดค่ากลยุทธ์: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่าการค้นพบ

การตั้งค่าการค้นพบ: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- การตั้งค่า DHT: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- การตั้งค่า PEX: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- การตั้งค่า Tracker: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: ช่วงเวลาการประกาศ tracker เป็นวินาที (ค่าเริ่มต้น: 1800.0, ช่วง: 60.0-86400.0)
  - `tracker_scrape_interval`: ช่วงเวลาการ scrape tracker เป็นวินาทีสำหรับการ scrape แบบเป็นระยะ (ค่าเริ่มต้น: 3600.0, ช่วง: 60.0-86400.0)
  - `tracker_auto_scrape`: Scrape tracker โดยอัตโนมัติเมื่อเพิ่ม torrent (BEP 48) (ค่าเริ่มต้น: false)
  - ตัวแปรสภาพแวดล้อม: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

โมเดลการกำหนดค่าการค้นพบ: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่าขีดจำกัด

ขีดจำกัดอัตรา: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- ขีดจำกัดทั่วโลก: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- ขีดจำกัดต่อ Torrent: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- ขีดจำกัดต่อ Peer: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- การตั้งค่า Scheduler: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

โมเดลการกำหนดค่าขีดจำกัด: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่าความสามารถในการสังเกต

การตั้งค่าความสามารถในการสังเกต: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- การบันทึก: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- เมตริก: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- การติดตามและแจ้งเตือน: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

โมเดลการกำหนดค่าความสามารถในการสังเกต: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่าความปลอดภัย

การตั้งค่าความปลอดภัย: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

โมเดลการกำหนดค่าความปลอดภัย: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### การกำหนดค่า Encryption

ccBitTorrent รองรับ BEP 3 Message Stream Encryption (MSE) และ Protocol Encryption (PE) สำหรับการเชื่อมต่อ peer ที่ปลอดภัย

**การตั้งค่า Encryption:**

- `enable_encryption` (bool, ค่าเริ่มต้น: `false`): เปิดใช้งานการรองรับการเข้ารหัสโปรโตคอล
- `encryption_mode` (str, ค่าเริ่มต้น: `"preferred"`): โหมดการเข้ารหัส
  - `"disabled"`: ไม่มีการเข้ารหัส (การเชื่อมต่อแบบธรรมดาเท่านั้น)
  - `"preferred"`: ลองเข้ารหัส, ถอยกลับเป็นแบบธรรมดาหากไม่พร้อมใช้งาน
  - `"required"`: การเข้ารหัสจำเป็น, การเชื่อมต่อล้มเหลวหากการเข้ารหัสไม่พร้อมใช้งาน
- `encryption_dh_key_size` (int, ค่าเริ่มต้น: `768`): ขนาดคีย์ Diffie-Hellman เป็นบิต (768 หรือ 1024)
- `encryption_prefer_rc4` (bool, ค่าเริ่มต้น: `true`): เลือก cipher RC4 เพื่อความเข้ากันได้กับไคลเอนต์รุ่นเก่า
- `encryption_allowed_ciphers` (list[str], ค่าเริ่มต้น: `["rc4", "aes"]`): ประเภท cipher ที่อนุญาต
  - `"rc4"`: Cipher สตรีม RC4 (เข้ากันได้มากที่สุด)
  - `"aes"`: Cipher AES ในโหมด CFB (ปลอดภัยกว่า)
  - `"chacha20"`: Cipher ChaCha20 (ยังไม่ได้ใช้งาน)
- `encryption_allow_plain_fallback` (bool, ค่าเริ่มต้น: `true`): อนุญาตให้ถอยกลับเป็นการเชื่อมต่อแบบธรรมดาหากการเข้ารหัสล้มเหลว (ใช้ได้เฉพาะเมื่อ `encryption_mode` เป็น `"preferred"`)

**ตัวแปรสภาพแวดล้อม:**

- `CCBT_ENABLE_ENCRYPTION`: เปิด/ปิดการเข้ารหัส (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: โหมดการเข้ารหัส (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: ขนาดคีย์ DH (`768` หรือ `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: เลือก RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: รายการที่คั่นด้วยเครื่องหมายจุลภาค (เช่น `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: อนุญาตให้ถอยกลับแบบธรรมดา (`true`/`false`)

**ตัวอย่างการกำหนดค่า:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**ข้อพิจารณาด้านความปลอดภัย:**

1. **ความเข้ากันได้ของ RC4**: RC4 รองรับเพื่อความเข้ากันได้ แต่มีความแข็งแกร่งทางคริปโตกราฟีต่ำ ใช้ AES เพื่อความปลอดภัยที่ดีกว่าเมื่อเป็นไปได้
2. **ขนาดคีย์ DH**: คีย์ DH 768 บิตให้ความปลอดภัยที่เพียงพอสำหรับกรณีการใช้งานส่วนใหญ่ 1024 บิตให้ความปลอดภัยที่แข็งแกร่งกว่าแต่เพิ่มความหน่วงของ handshake
3. **โหมดการเข้ารหัส**:
   - `preferred`: เหมาะที่สุดสำหรับความเข้ากันได้ - ลองเข้ารหัสแต่ถอยกลับอย่างสง่างาม
   - `required`: ปลอดภัยที่สุดแต่อาจล้มเหลวในการเชื่อมต่อกับ peer ที่ไม่รองรับการเข้ารหัส
4. **ผลกระทบต่อประสิทธิภาพ**: การเข้ารหัสเพิ่มค่าใช้จ่ายขั้นต่ำ (~1-5% สำหรับ RC4, ~2-8% สำหรับ AES) แต่ปรับปรุงความเป็นส่วนตัวและช่วยหลีกเลี่ยงการปรับรูปร่างการจราจร

**รายละเอียดการใช้งาน:**

การใช้งานการเข้ารหัส: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Cipher Suites: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- การแลกเปลี่ยน Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### การกำหนดค่า ML

การตั้งค่า machine learning: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

โมเดลการกำหนดค่า ML: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่า Dashboard

การตั้งค่า dashboard: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

โมเดลการกำหนดค่า dashboard: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## ตัวแปรสภาพแวดล้อม

ตัวแปรสภาพแวดล้อมใช้คำนำหน้า `CCBT_` และทำตามโครงร่างการตั้งชื่อแบบลำดับชั้น

อ้างอิง: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

รูปแบบ: `CCBT_<SECTION>_<OPTION>=<value>`

ตัวอย่าง:
- เครือข่าย: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- ดิสก์: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- กลยุทธ์: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- การค้นพบ: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- ความสามารถในการสังเกต: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- ขีดจำกัด: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- ความปลอดภัย: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

การแยกวิเคราะห์ตัวแปรสภาพแวดล้อม: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## โครงร่างการกำหนดค่า

โครงร่างการกำหนดค่าและการตรวจสอบ: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

โครงร่างกำหนด:
- ประเภทฟิลด์และข้อจำกัด
- ค่าเริ่มต้น
- กฎการตรวจสอบ
- เอกสาร

## ความสามารถในการกำหนดค่า

ความสามารถในการกำหนดค่าและการตรวจจับคุณสมบัติ: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## เทมเพลตการกำหนดค่า

เทมเพลตการกำหนดค่าที่กำหนดไว้ล่วงหน้า: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

เทมเพลตสำหรับ:
- การตั้งค่าประสิทธิภาพสูง
- การตั้งค่าแหล่งข้อมูลต่ำ
- การตั้งค่าที่เน้นความปลอดภัย
- การตั้งค่าการพัฒนา

## ตัวอย่างการกำหนดค่า

ตัวอย่างการกำหนดค่ามีอยู่ในไดเรกทอรี [examples/](examples/):

- การกำหนดค่าพื้นฐาน: [example-config-basic.toml](examples/example-config-basic.toml)
- การกำหนดค่าขั้นสูง: [example-config-advanced.toml](examples/example-config-advanced.toml)
- การกำหนดค่าประสิทธิภาพ: [example-config-performance.toml](examples/example-config-performance.toml)
- การกำหนดค่าความปลอดภัย: [example-config-security.toml](examples/example-config-security.toml)

## Hot Reload

การรองรับการโหลดซ้ำแบบร้อนของการกำหนดค่า: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

ระบบการกำหนดค่ารองรับการโหลดซ้ำการเปลี่ยนแปลงโดยไม่ต้องรีสตาร์ทไคลเอนต์

## การย้ายการกำหนดค่า

เครื่องมือการย้ายการกำหนดค่า: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

เครื่องมือสำหรับการย้ายระหว่างเวอร์ชันการกำหนดค่า

## การสำรองข้อมูลและ Diff การกำหนดค่า

เครื่องมือการจัดการการกำหนดค่า:
- การสำรองข้อมูล: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Diff: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## การกำหนดค่าแบบมีเงื่อนไข

การรองรับการกำหนดค่าแบบมีเงื่อนไข: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## เคล็ดลับและแนวทางปฏิบัติที่ดีที่สุด

### การปรับแต่งประสิทธิภาพ

- เพิ่ม `disk.write_buffer_kib` สำหรับการเขียนแบบลำดับขนาดใหญ่: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- เปิดใช้งาน `direct_io` บน Linux/NVMe เพื่อปรับปรุง throughput การเขียน: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- ปรับ `network.pipeline_depth` และ `network.block_size_kib` สำหรับเครือข่ายของคุณ: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### การปรับปรุงทรัพยากร

- ปรับ `disk.hash_workers` ตาม CPU cores: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- กำหนดค่า `disk.cache_size_mb` ตาม RAM ที่มี: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- ตั้งค่า `network.max_global_peers` ตาม bandwidth: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### การกำหนดค่าเครือข่าย

- กำหนดค่า timeouts ตามสภาวะเครือข่าย: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- เปิด/ปิดโปรโตคอลตามความจำเป็น: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- ตั้งค่าขีดจำกัดอัตราอย่างเหมาะสม: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

สำหรับการปรับแต่งประสิทธิภาพโดยละเอียด ดู [คู่มือการปรับแต่งประสิทธิภาพ](performance.md)






ccBitTorrent ใช้ระบบการกำหนดค่าที่ครอบคลุมพร้อมการรองรับ TOML การตรวจสอบ การโหลดซ้ำแบบร้อน และการโหลดแบบลำดับชั้นจากหลายแหล่ง

ระบบการกำหนดค่า: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

## แหล่งที่มาของการกำหนดค่าและลำดับความสำคัญ

การกำหนดค่าถูกโหลดตามลำดับนี้ (แหล่งที่มาทีหลังจะแทนที่แหล่งที่มาก่อน):

1. **ค่าเริ่มต้น**: ค่าเริ่มต้นที่สมเหตุสมผลในตัวจาก [ccbt/models.py:Config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)
2. **ไฟล์การกำหนดค่า**: `ccbt.toml` ในไดเรกทอรีปัจจุบันหรือ `~/.config/ccbt/ccbt.toml` ดู: [ccbt/config/config.py:_find_config_file](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L55)
3. **ตัวแปรสภาพแวดล้อม**: ตัวแปรที่มีคำนำหน้า `CCBT_*` ดู: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
4. **อาร์กิวเมนต์ CLI**: การแทนที่บรรทัดคำสั่ง ดู: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L55)
5. **ต่อ Torrent**: การตั้งค่า torrent แต่ละรายการ (คุณสมบัติในอนาคต)

การโหลดการกำหนดค่า: [ccbt/config/config.py:_load_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L76)

## ไฟล์การกำหนดค่า

### การกำหนดค่าเริ่มต้น

ดูไฟล์การกำหนดค่าเริ่มต้น: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)

การกำหนดค่าถูกจัดระเบียบเป็นส่วน:

### การกำหนดค่าเครือข่าย

การตั้งค่าเครือข่าย: [ccbt.toml:4-43](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L4-L43)

- ขีดจำกัดการเชื่อมต่อ: [ccbt.toml:6-8](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6-L8)
- Pipeline คำขอ: [ccbt.toml:11-14](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L14)
- การปรับแต่ง Socket: [ccbt.toml:17-19](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L17-L19)
- Timeouts: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- การตั้งค่าการฟัง: [ccbt.toml:29-31](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L29-L31)
- โปรโตคอลการขนส่ง: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- ขีดจำกัดอัตรา: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)
- กลยุทธ์การ Choking: [ccbt.toml:45-47](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L45-L47)
- การตั้งค่า Tracker: [ccbt.toml:50-54](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L50-L54)

โมเดลการกำหนดค่าเครือข่าย: [ccbt/models.py:NetworkConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่าดิสก์

การตั้งค่าดิสก์: [ccbt.toml:57-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L57-L96)

- การจัดสรรล่วงหน้า: [ccbt.toml:59-60](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L59-L60)
- การปรับปรุงการเขียน: [ccbt.toml:63-67](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L63-L67)
- การตรวจสอบ Hash: [ccbt.toml:70-73](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70-L73)
- I/O Threading: [ccbt.toml:76-78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L76-L78)
- การตั้งค่าขั้นสูง: [ccbt.toml:81-85](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81-L85)
- การตั้งค่าบริการจัดเก็บข้อมูล: [ccbt.toml:87-89](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: ขีดจำกัดขนาดไฟล์สูงสุดใน MB สำหรับบริการจัดเก็บข้อมูล (0 หรือ None = ไม่จำกัด, สูงสุด 1048576 = 1TB) ป้องกันการเขียนดิสก์ไม่จำกัดระหว่างการทดสอบและสามารถกำหนดค่าสำหรับการใช้งานในโปรดักชัน
- การตั้งค่า Checkpoint: [ccbt.toml:91-96](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L91-L96)

โมเดลการกำหนดค่าดิสก์: [ccbt/models.py:DiskConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่ากลยุทธ์

การตั้งค่ากลยุทธ์: [ccbt.toml:99-114](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L99-L114)

- การเลือกชิ้นส่วน: [ccbt.toml:101-104](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L101-L104)
- กลยุทธ์ขั้นสูง: [ccbt.toml:107-109](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L107-L109)
- ลำดับความสำคัญของชิ้นส่วน: [ccbt.toml:112-113](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L112-L113)

โมเดลการกำหนดค่ากลยุทธ์: [ccbt/models.py:StrategyConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่าการค้นพบ

การตั้งค่าการค้นพบ: [ccbt.toml:116-136](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L116-L136)

- การตั้งค่า DHT: [ccbt.toml:118-125](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L118-L125)
- การตั้งค่า PEX: [ccbt.toml:128-129](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L128-L129)
- การตั้งค่า Tracker: [ccbt.toml:132-135](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: ช่วงเวลาการประกาศ tracker เป็นวินาที (ค่าเริ่มต้น: 1800.0, ช่วง: 60.0-86400.0)
  - `tracker_scrape_interval`: ช่วงเวลาการ scrape tracker เป็นวินาทีสำหรับการ scrape แบบเป็นระยะ (ค่าเริ่มต้น: 3600.0, ช่วง: 60.0-86400.0)
  - `tracker_auto_scrape`: Scrape tracker โดยอัตโนมัติเมื่อเพิ่ม torrent (BEP 48) (ค่าเริ่มต้น: false)
  - ตัวแปรสภาพแวดล้อม: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

โมเดลการกำหนดค่าการค้นพบ: [ccbt/models.py:DiscoveryConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่าขีดจำกัด

ขีดจำกัดอัตรา: [ccbt.toml:138-152](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L138-L152)

- ขีดจำกัดทั่วโลก: [ccbt.toml:140-141](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L140-L141)
- ขีดจำกัดต่อ Torrent: [ccbt.toml:144-145](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L144-L145)
- ขีดจำกัดต่อ Peer: [ccbt.toml:148](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L148)
- การตั้งค่า Scheduler: [ccbt.toml:151](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L151)

โมเดลการกำหนดค่าขีดจำกัด: [ccbt/models.py:LimitsConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่าความสามารถในการสังเกต

การตั้งค่าความสามารถในการสังเกต: [ccbt.toml:154-171](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L154-L171)

- การบันทึก: [ccbt.toml:156-160](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L156-L160)
- เมตริก: [ccbt.toml:163-165](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L163-L165)
- การติดตามและแจ้งเตือน: [ccbt.toml:168-170](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L168-L170)

โมเดลการกำหนดค่าความสามารถในการสังเกต: [ccbt/models.py:ObservabilityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่าความปลอดภัย

การตั้งค่าความปลอดภัย: [ccbt.toml:173-178](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L173-L178)

โมเดลการกำหนดค่าความปลอดภัย: [ccbt/models.py:SecurityConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

#### การกำหนดค่า Encryption

ccBitTorrent รองรับ BEP 3 Message Stream Encryption (MSE) และ Protocol Encryption (PE) สำหรับการเชื่อมต่อ peer ที่ปลอดภัย

**การตั้งค่า Encryption:**

- `enable_encryption` (bool, ค่าเริ่มต้น: `false`): เปิดใช้งานการรองรับการเข้ารหัสโปรโตคอล
- `encryption_mode` (str, ค่าเริ่มต้น: `"preferred"`): โหมดการเข้ารหัส
  - `"disabled"`: ไม่มีการเข้ารหัส (การเชื่อมต่อแบบธรรมดาเท่านั้น)
  - `"preferred"`: ลองเข้ารหัส, ถอยกลับเป็นแบบธรรมดาหากไม่พร้อมใช้งาน
  - `"required"`: การเข้ารหัสจำเป็น, การเชื่อมต่อล้มเหลวหากการเข้ารหัสไม่พร้อมใช้งาน
- `encryption_dh_key_size` (int, ค่าเริ่มต้น: `768`): ขนาดคีย์ Diffie-Hellman เป็นบิต (768 หรือ 1024)
- `encryption_prefer_rc4` (bool, ค่าเริ่มต้น: `true`): เลือก cipher RC4 เพื่อความเข้ากันได้กับไคลเอนต์รุ่นเก่า
- `encryption_allowed_ciphers` (list[str], ค่าเริ่มต้น: `["rc4", "aes"]`): ประเภท cipher ที่อนุญาต
  - `"rc4"`: Cipher สตรีม RC4 (เข้ากันได้มากที่สุด)
  - `"aes"`: Cipher AES ในโหมด CFB (ปลอดภัยกว่า)
  - `"chacha20"`: Cipher ChaCha20 (ยังไม่ได้ใช้งาน)
- `encryption_allow_plain_fallback` (bool, ค่าเริ่มต้น: `true`): อนุญาตให้ถอยกลับเป็นการเชื่อมต่อแบบธรรมดาหากการเข้ารหัสล้มเหลว (ใช้ได้เฉพาะเมื่อ `encryption_mode` เป็น `"preferred"`)

**ตัวแปรสภาพแวดล้อม:**

- `CCBT_ENABLE_ENCRYPTION`: เปิด/ปิดการเข้ารหัส (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: โหมดการเข้ารหัส (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: ขนาดคีย์ DH (`768` หรือ `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: เลือก RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: รายการที่คั่นด้วยเครื่องหมายจุลภาค (เช่น `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: อนุญาตให้ถอยกลับแบบธรรมดา (`true`/`false`)

**ตัวอย่างการกำหนดค่า:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**ข้อพิจารณาด้านความปลอดภัย:**

1. **ความเข้ากันได้ของ RC4**: RC4 รองรับเพื่อความเข้ากันได้ แต่มีความแข็งแกร่งทางคริปโตกราฟีต่ำ ใช้ AES เพื่อความปลอดภัยที่ดีกว่าเมื่อเป็นไปได้
2. **ขนาดคีย์ DH**: คีย์ DH 768 บิตให้ความปลอดภัยที่เพียงพอสำหรับกรณีการใช้งานส่วนใหญ่ 1024 บิตให้ความปลอดภัยที่แข็งแกร่งกว่าแต่เพิ่มความหน่วงของ handshake
3. **โหมดการเข้ารหัส**:
   - `preferred`: เหมาะที่สุดสำหรับความเข้ากันได้ - ลองเข้ารหัสแต่ถอยกลับอย่างสง่างาม
   - `required`: ปลอดภัยที่สุดแต่อาจล้มเหลวในการเชื่อมต่อกับ peer ที่ไม่รองรับการเข้ารหัส
4. **ผลกระทบต่อประสิทธิภาพ**: การเข้ารหัสเพิ่มค่าใช้จ่ายขั้นต่ำ (~1-5% สำหรับ RC4, ~2-8% สำหรับ AES) แต่ปรับปรุงความเป็นส่วนตัวและช่วยหลีกเลี่ยงการปรับรูปร่างการจราจร

**รายละเอียดการใช้งาน:**

การใช้งานการเข้ารหัส: [ccbt/security/encryption.py:EncryptionManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/encryption.py#L131)

- MSE Handshake: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/mse_handshake.py#L45)
- Cipher Suites: [ccbt/security/ciphers/__init__.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- การแลกเปลี่ยน Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/security/dh_exchange.py)

### การกำหนดค่า ML

การตั้งค่า machine learning: [ccbt.toml:180-183](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L180-L183)

โมเดลการกำหนดค่า ML: [ccbt/models.py:MLConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

### การกำหนดค่า Dashboard

การตั้งค่า dashboard: [ccbt.toml:185-191](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L185-L191)

โมเดลการกำหนดค่า dashboard: [ccbt/models.py:DashboardConfig](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/models.py)

## ตัวแปรสภาพแวดล้อม

ตัวแปรสภาพแวดล้อมใช้คำนำหน้า `CCBT_` และทำตามโครงร่างการตั้งชื่อแบบลำดับชั้น

อ้างอิง: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)

รูปแบบ: `CCBT_<SECTION>_<OPTION>=<value>`

ตัวอย่าง:
- เครือข่าย: [env.example:10-58](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L10-L58)
- ดิสก์: [env.example:62-102](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L62-L102)
- กลยุทธ์: [env.example:106-121](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L106-L121)
- การค้นพบ: [env.example:125-141](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L125-L141)
- ความสามารถในการสังเกต: [env.example:145-162](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L145-L162)
- ขีดจำกัด: [env.example:166-180](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L166-L180)
- ความปลอดภัย: [env.example:184-189](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/yourusername/ccbittorrent/blob/main/env.example#L193-L196)

การแยกวิเคราะห์ตัวแปรสภาพแวดล้อม: [ccbt/config/config.py:_get_env_config](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

## โครงร่างการกำหนดค่า

โครงร่างการกำหนดค่าและการตรวจสอบ: [ccbt/config/config_schema.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_schema.py)

โครงร่างกำหนด:
- ประเภทฟิลด์และข้อจำกัด
- ค่าเริ่มต้น
- กฎการตรวจสอบ
- เอกสาร

## ความสามารถในการกำหนดค่า

ความสามารถในการกำหนดค่าและการตรวจจับคุณสมบัติ: [ccbt/config/config_capabilities.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_capabilities.py)

## เทมเพลตการกำหนดค่า

เทมเพลตการกำหนดค่าที่กำหนดไว้ล่วงหน้า: [ccbt/config/config_templates.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_templates.py)

เทมเพลตสำหรับ:
- การตั้งค่าประสิทธิภาพสูง
- การตั้งค่าแหล่งข้อมูลต่ำ
- การตั้งค่าที่เน้นความปลอดภัย
- การตั้งค่าการพัฒนา

## ตัวอย่างการกำหนดค่า

ตัวอย่างการกำหนดค่ามีอยู่ในไดเรกทอรี [examples/](examples/):

- การกำหนดค่าพื้นฐาน: [example-config-basic.toml](examples/example-config-basic.toml)
- การกำหนดค่าขั้นสูง: [example-config-advanced.toml](examples/example-config-advanced.toml)
- การกำหนดค่าประสิทธิภาพ: [example-config-performance.toml](examples/example-config-performance.toml)
- การกำหนดค่าความปลอดภัย: [example-config-security.toml](examples/example-config-security.toml)

## Hot Reload

การรองรับการโหลดซ้ำแบบร้อนของการกำหนดค่า: [ccbt/config/config.py:ConfigManager](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py#L40)

ระบบการกำหนดค่ารองรับการโหลดซ้ำการเปลี่ยนแปลงโดยไม่ต้องรีสตาร์ทไคลเอนต์

## การย้ายการกำหนดค่า

เครื่องมือการย้ายการกำหนดค่า: [ccbt/config/config_migration.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_migration.py)

เครื่องมือสำหรับการย้ายระหว่างเวอร์ชันการกำหนดค่า

## การสำรองข้อมูลและ Diff การกำหนดค่า

เครื่องมือการจัดการการกำหนดค่า:
- การสำรองข้อมูล: [ccbt/config/config_backup.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_backup.py)
- Diff: [ccbt/config/config_diff.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_diff.py)

## การกำหนดค่าแบบมีเงื่อนไข

การรองรับการกำหนดค่าแบบมีเงื่อนไข: [ccbt/config/config_conditional.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config_conditional.py)

## เคล็ดลับและแนวทางปฏิบัติที่ดีที่สุด

### การปรับแต่งประสิทธิภาพ

- เพิ่ม `disk.write_buffer_kib` สำหรับการเขียนแบบลำดับขนาดใหญ่: [ccbt.toml:64](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L64)
- เปิดใช้งาน `direct_io` บน Linux/NVMe เพื่อปรับปรุง throughput การเขียน: [ccbt.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L81)
- ปรับ `network.pipeline_depth` และ `network.block_size_kib` สำหรับเครือข่ายของคุณ: [ccbt.toml:11-13](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L11-L13)

### การปรับปรุงทรัพยากร

- ปรับ `disk.hash_workers` ตาม CPU cores: [ccbt.toml:70](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L70)
- กำหนดค่า `disk.cache_size_mb` ตาม RAM ที่มี: [ccbt.toml:78](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L78)
- ตั้งค่า `network.max_global_peers` ตาม bandwidth: [ccbt.toml:6](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L6)

### การกำหนดค่าเครือข่าย

- กำหนดค่า timeouts ตามสภาวะเครือข่าย: [ccbt.toml:22-26](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L22-L26)
- เปิด/ปิดโปรโตคอลตามความจำเป็น: [ccbt.toml:34-36](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L34-L36)
- ตั้งค่าขีดจำกัดอัตราอย่างเหมาะสม: [ccbt.toml:39-42](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml#L39-L42)

สำหรับการปรับแต่งประสิทธิภาพโดยละเอียด ดู [คู่มือการปรับแต่งประสิทธิภาพ](performance.md)
































































































































































































