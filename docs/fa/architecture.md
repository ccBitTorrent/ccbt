# نمای کلی معماری

این مستند نمای فنی از معماری، اجزا و جریان داده ccBitTorrent را ارائه می‌دهد.

## معماری کلی

ccBitTorrent یک کلاینت BitTorrent با کارایی بالا با معماری مدرن است که از الگوهای ناهمزمان و رویدادمحور استفاده می‌کند.

### لایه‌های معماری

1. **لایه CLI**: رابط خط فرمان و تعامل کاربر
2. **لایه جلسه**: مدیریت چرخه حیات torrent و هماهنگی اجزا
3. **لایه هسته**: منطق دامنه BitTorrent بدون وابستگی‌های CLI/جلسه
4. **لایه شبکه**: مدیریت اتصال همتا و ارتباطات پروتکل
5. **لایه ذخیره‌سازی**: عملیات I/O دیسک و مدیریت فایل

### مدیریت جلسه

`AsyncSessionManager` جلسات چند torrent را هماهنگ می‌کند و به کنترل‌کننده‌های تخصصی واگذار می‌کند:

- `ccbt/session/announce.py`: اعلان‌های tracker
- `ccbt/session/checkpointing.py`: عملیات checkpoint
- `ccbt/session/download_startup.py`: مقداردهی اولیه دانلود
- `ccbt/session/torrent_addition.py`: جریان افزودن torrent
- `ccbt/session/manager_startup.py`: توالی راه‌اندازی اجزا

### تزریق وابستگی

تزریق وابستگی اختیاری از طریق `ccbt/utils/di.py`: `DIContainer` برای کارخانه‌ها (امنیت، DHT، NAT، سرور TCP)

### ExecutorManager

مدیریت اجرای دستورات یکپارچه برای CLI و دیمن.

### XetSyncManager

مدیریت همگام‌سازی پوشه برای پروتکل XET (BEP XET).

## اجزای کلیدی

### مدیریت همتا

- `AsyncPeerConnectionManager`: مدیریت اتصالات همتا با استخر اتصال
- `AsyncPeerConnection`: اتصال همتا ناهمزمان با خط لوله، خفگی tit-for-tat و اندازه بلوک تطبیقی

### مدیریت قطعه

- `AsyncPieceManager`: انتخاب قطعه پیشرفته با نادرترین اول و endgame
- `FileSelectionManager`: مدیریت انتخاب و اولویت‌بندی فایل برای torrentهای چند فایلی

### کشف

- `AsyncDHTClient`: کلاینت DHT بهبود یافته (BEP 5) با پیاده‌سازی کامل Kademlia
- `AsyncTrackerClient`: ارتباط tracker ناهمزمان با کارایی بالا
- `AsyncUDPTrackerClient`: پیاده‌سازی کلاینت tracker UDP ناهمزمان (BEP 15)

### ذخیره‌سازی

- `DiskIOManager`: مدیر I/O دیسک با کارایی بالا با پیش‌تخصیص، دسته‌ای، I/O نگاشت حافظه و عملیات ناهمزمان
- `FileAssembler`: مونتاژ قطعات به فایل‌های کامل
- `CheckpointManager`: مدیریت checkpoint برای عملکرد از سرگیری

## منابع بیشتر

- [راهنمای شروع](getting-started.md) - راهنمای شروع سریع
- [راهنمای پیکربندی](configuration.md) - پیکربندی دقیق
- [مرجع API](API.md) - مستندات کامل API

