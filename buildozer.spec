[app]
title = Pocket RPG
package.name = pocketrpg
package.domain = org.nikita
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = tests, bin, .github, .buildozer
version = 0.1.0
requirements = python3,kivy==2.3.0
orientation = portrait
fullscreen = 0

android.api = 34
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
