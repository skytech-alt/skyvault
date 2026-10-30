[app]
title = SkyVault
package.name = skyvault
package.domain = org.skyvault

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,atlas,txt
source.include_patterns = screens/*.py

version = 1.0.0

requirements = python3,kivy==2.1.0,kivymd==1.1.1,cryptography,plyer

orientation = portrait
fullscreen = 0

android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, CAMERA

android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True

p4a.branch = develop

osx.python_version = 3
osx.kivy_version = 2.1.0
