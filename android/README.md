# Recetary Android

Small offline companion app for browsing a Recetary SQLite database.

## Current scope

- Import a copy of `data/recetary.db` with the Android file picker.
- Import the `data/images/` folder to display recipe images offline.
- Search recipes by title, subtitle, or source URL.
- Browse results in pages and open a random matching recipe.
- Open ingredients, preparation, and HTTP source links.
- No recipe capture, backend, network service, or AI features.

The app opens the imported database read-only. It does not modify the desktop
database and does not include the repository's personal database in the APK.

## Build

Open this `android/` folder in Android Studio, or build from a terminal with
JDK 17:

```powershell
.\gradlew.bat assembleDebug
```

The APK is written to
`app/build/outputs/apk/debug/app-debug.apk`. Install it on an Android device
or emulator from Android Studio or with `adb install`.

To use the app, copy the desktop `data/recetary.db` to the phone and choose it
with **Importar DB**. To display covers, copy the desktop `data/images/` folder
to the phone and choose it with **Imágenes**. The app remains fully offline.
