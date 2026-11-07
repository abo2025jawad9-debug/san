[app]

title = Photo To Telegram
package.name = photototelegram
package.domain = org.student

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

# تثبيت إصدارات محددة لتجنب أخطاء الترجمة (هذا هو السطر الأهم)
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,pyjnius,android

# الصلاحيات المطلوبة
android.permissions = INTERNET, READ_MEDIA_IMAGES, READ_EXTERNAL_STORAGE

android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

# قبول التراخيص تلقائياً
android.accept_sdk_license = True

orientation = portrait
fullscreen = 0
