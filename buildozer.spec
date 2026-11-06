[app]
title = Photo To Telegram
package.name = photototelegram
package.domain = org.student
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

# إصدارات محددة لتجنب مشاكل البناء
requirements = python3,kivy==2.3.0,pyjnius>=1.6.1,android

android.permissions = INTERNET, READ_MEDIA_IMAGES
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.allow_backup = True

orientation = portrait
fullscreen = 0
