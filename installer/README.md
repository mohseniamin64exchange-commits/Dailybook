# DailyBook Windows Installer

فایل خروجی این فرایند یک Setup مستقل ۶۴بیتی است. کاربر نهایی به Python،
PowerShell، فایل BAT یا اینترنت نیاز ندارد.

نصب‌کننده برنامه را در C:\Program Files\DailyBook نصب می‌کند و داده‌ها،
تنظیمات، لاگ‌ها و بکاپ‌ها را در C:\ProgramData\DailyBook نگه می‌دارد.
سرویس Windows، فایروال، میانبرها، Upgrade امن و Uninstall نیز خودکار هستند.

ساده‌ترین روش ساخت روی Windows x64، دوبار کلیک روی فایل زیر در ریشه پروژه است:

    BUILD_WINDOWS_SETUP.bat

این فایل Python سازگار (۳.۱۱ یا جدیدتر) و Inno Setup را در صورت نیاز روی سیستم سازنده نصب می‌کند،
تست‌ها را اجرا می‌کند و Setup را می‌سازد. روش دستی برای توسعه‌دهنده:

    .\installer\build_installer.ps1 -Clean

خروجی:

    installer\output\DailyBook-Setup-x64.exe
