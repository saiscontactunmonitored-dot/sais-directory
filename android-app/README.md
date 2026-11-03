# SAIS Animal Directory — Android app

Initial Android Trusted Web Activity (TWA) project for the Somerset Animal Information Services business directory.

- Website: https://directory.somersetanimalinformationservices.com/
- Android application ID: `uk.co.sais.animaldirectory`
- Display name: SAIS Animal Directory
- Minimum Android version: Android 7.0 (API 24)
- Target Android version: Android 16 (API 36)

## Not ready for public release yet

A live inspection displayed a directory-loading error. Fix and test the directory data connection before publishing.

The site exposes `/manifest.json`. Before a TWA can be verified and released, the site owner must:
1. Ensure the directory works reliably on mobile.
2. Implement and test a service worker/offline experience. A manifest alone does not provide offline access.
3. Add `/.well-known/assetlinks.json` after generating the release signing certificate fingerprint.
4. Confirm the manifest icons are owned, stable, and suitable for the Play Store.
5. Publish a public privacy policy and confirm the app's data practices.

## Build

Uses AndroidX Browser Helper's `LauncherActivity` to open the owned website as a Trusted Web Activity. The website's Digital Asset Links association must be configured for verified full-screen display.

Use Android Studio with JDK 17 and Android SDK 36, or Gradle 8.11.1:

```bash
gradle bundleRelease
```

Expected output: `app/build/outputs/bundle/release/app-release.aab`.

Do not upload until the signed app has been tested on a physical Android device and website association configured. Keep signing keys private; never commit them to GitHub.

## Offline access

Offline access is not provided by this Android wrapper alone. It must be implemented and tested on the website (service worker plus a real save-for-offline feature). Do not advertise offline access until this is complete.

New phone/tablet apps submitted from 31 August 2026 must target API 36 or higher. Check Play Console for account-specific testing requirements.
