# Echo Android App — ready-to-build project

> **In this repository:** this project lives in the `android/` folder.
> It is the actual Echo phone app (versionName 3.6, versionCode 36).
> Source only in this release — no prebuilt APK is attached yet; one
> will be added to the release once it has been built with the Android
> toolchain (Android Studio). Build steps are below.

Oma's Echo app code (`MainActivity.kt` + `EchoLookup.kt`) wrapped in a complete,
standard Android Studio project, so the APK build on the laptop is just
open → sync → build. The original loose files in `echo-app-by-oma/` are untouched.

## Fixes made while packaging (in this copy only)
1. **EchoLookup.kt would not compile** — it uses `horizontalScroll` and
   `rememberScrollState` but never imported them. Imports added.
2. **The "Look it up" panel was never shown** — `EchoLookupPanel()` existed but
   nothing called it. MainActivity now has a "Look it up" button that opens it.
3. **Approve/Deny taps would not visibly stick** — the buttons changed fields on
   the message object in place, which Compose doesn't notice. They now replace
   the item with an updated copy, so "Approved"/"Denied" shows right away.
4. **Input box colors** moved to the current Material3 API
   (`OutlinedTextFieldDefaults.colors`) — the old call is removed in current
   library versions.

## Honest status
This project has NOT been compiled yet — Muse's workspace has no Android SDK,
so the first real compile happens in Android Studio on the laptop. The versions
are pinned to a stable set (AGP 8.5.2, Kotlin 2.0.20, Compose BOM 2024.09.00,
compileSdk/targetSdk 34, minSdk 26). If Android Studio offers to upgrade the
Gradle wrapper or AGP on first open, say **Don't remind me / keep current** —
the pinned versions work together.

## Build steps (laptop)
1. Copy this whole `echo-android-project` folder to the laptop.
2. Open Android Studio → **Open** → pick the `echo-android-project` folder.
3. Wait for Gradle Sync to finish (first time downloads the libraries — needs internet).
4. Menu: **Build → Build App Bundle(s) / APK(s) → Build APK(s)**.
5. When it finishes, click **locate** — the file is
   `app/build/outputs/apk/debug/app-debug.apk`.
6. Send `app-debug.apk` to the phone (email it to yourself, or USB).
7. On the phone, tap the APK → **Install** (allow installs from your files app if asked).
8. Echo gets her own icon, like any app.
