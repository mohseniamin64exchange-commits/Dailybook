# ROADMAP — DailyBook

آخرین بروزرسانی: ۱۴۰۵/۰۶/۲۹  
نسخه جاری: `1.0.0-rc5.6`

## وضعیت فعلی

- [x] Backend Flask/SQLite و احراز هویت
- [x] ثبت درآمد/هزینه با تاریخ شمسی و ذخیره Gregorian
- [x] محدودسازی رکوردهای User به مالک همان رکورد
- [x] نمایش ۱۰ ثبت اخیر هر User
- [x] صفحات مدیریتی Admin
- [x] Design System نهایی Dark/Light
- [x] سایدبار ثابت سمت راست فقط برای Admin روی کنسول/کامپیوتر سرور (localhost)
- [x] حذف Sidebar برای Userهای عادی
- [x] Theme Toggle با حفظ انتخاب کاربر
- [x] به‌روزرسانی تست ساختار Sidebar/User
- [ ] اجرای کامل pytest روی محیط دارای dependency
- [ ] تست بصری Dark/Light در مرورگر واقعی
- [x] آماده‌سازی کامل Build pipeline برای Windows x64 Setup
- [ ] تولید فایل نهایی `DailyBook-Setup-x64.exe` روی Windows x64
- [ ] Clean Install / Upgrade / Uninstall روی Windows 10/11
- [ ] تست نهایی LAN با ۳ تا ۵ User

## مرحله فعلی

**آماده‌سازی Windows Setup** — اسکریپت ساخت Installer استاندارد آماده است؛ تولید فایل نهایی EXE باید روی Windows x64 انجام شود.

## مراحل باقی‌مانده تا تکمیل

**۵ مرحله**: pytest، تأیید بصری، تولید EXE روی Windows، تست نصب، تست LAN.

## نکته اجرایی

صفحه Admin و User از یک Design System مشترک استفاده می‌کنند، اما Sidebar فقط برای Admin روی کنسول سرور (`127.0.0.1` یا `::1`) رندر می‌شود. کلاینت‌های LAN سایدبار ندارند؛ User عادی فقط فرم ثبت و ۱۰ رکورد اخیر متعلق به خودش را می‌بیند.

- [x] نمایش عنوان رویدادهای Audit Log در رابط مدیر به فارسی انجام شد؛ مقدار استاندارد انگلیسی در دیتابیس بدون تغییر باقی می‌ماند.

- [x] ساده‌سازی ستون جزئیات Audit Log: نمایش JSON و کلیدهای فنی حذف و اطلاعات قبل/بعد با برچسب‌های فارسی و خوانا نمایش داده می‌شود.

- [x] بازطراحی یکپارچه تمام منوهای Admin (گزارش‌ها، کاربران، بکاپ، لاگ فعالیت‌ها و تنظیمات) با Design System تأییدشده Dark/Light.

- [x] اصلاح Build ویندوز: حذف وابستگی ثابت به Python 3.11 و تشخیص خودکار Python نصب‌شده (از جمله Python 3.14.6).

- [x] افزودن گزینه «اجرای اتوماتیک بعد از روشن شدن ویندوز» در تنظیمات Admin و اتصال آن به Startup Type سرویس Windows (Automatic/Manual).
- [x] هماهنگ‌سازی تست گزارش با عنوان جدید ستون «کاربر» در UI بازطراحی‌شده.


## GitHub Actions Windows Build — 2026-09-20
- [x] Workflow `.github/workflows/build-windows.yml` روی Runner نوع `windows-latest` فعال شد.
- [x] نصب Dependencyها، اجرای کامل تست‌ها، ساخت `DailyBook.exe` و `DailyBookServer.exe` و ساخت Setup فقط در GitHub Actions انجام می‌شود.
- [x] اجرای تأییدشده #35495484693 با Commit `4732f46e9bee5bf1dc7a7504ec52e841e7b1a447` سبز شد.
- [x] Artifact نهایی `DailyBook-Setup-x64` با فایل `DailyBook-Setup-x64.exe` ایجاد شد.
- [ ] تست نصب روی Windows واقعی و تست شبکه LAN همچنان مرحله بعدی است.
