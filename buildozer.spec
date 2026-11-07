[app]

# اسم التطبيق كما سيظهر على الهاتف
title = Photo To Telegram

# اسم الحزمة (يجب أن يكون بالإنجليزية وبدون مسافات)
package.name = photototelegram
package.domain = org.student

# مسار الملفات
source.dir = .
source.include_exts = py,png,jpg,kv,atlas

# إصدار التطبيق
version = 1.0

# المتطلبات الأساسية لتشغيل Kivy على أندرويد
requirements = python3,kivy==2.3.0,pyjnius,android

# الصلاحيات المطلوبة (الإنترنت لتيليجرام، وقراءة الصور)
android.permissions = INTERNET, READ_MEDIA_IMAGES, READ_EXTERNAL_STORAGE

# إصدارات أندرويد المستهدفة
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

# قبول تراخيص أندرويد تلقائياً (هذا السطر يحل مشكلة الفشل السابقة)
android.accept_sdk_license = True

# إعدادات الشاشة
orientation = portrait
fullscreen = 0
