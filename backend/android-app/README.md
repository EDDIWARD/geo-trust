# Geo-Trust Android App

## Current scope

This app covers the farmer registration flow:

- load bootstrap config and available regions
- collect location and device risk information
- validate current location against the selected region
- submit product registration
- show accepted or rejected results

## Configuration

- backend base URL is controlled by `apiBaseUrl` in `gradle.properties`
- default value `http://10.0.2.2:8000/` is suitable for the Android emulator
- for a physical phone, change it to `http://<your-pc-lan-ip>:8000/`
- this workspace already includes `gradlew` and `gradlew.bat`

## Build

After Android SDK and JDK are ready:

- Windows: `.\gradlew.bat assembleDebug`
- macOS/Linux: `./gradlew assembleDebug`

## Physical phone test

1. Start backend with `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
2. Make sure phone and computer are on the same LAN
3. Set `apiBaseUrl` in `gradle.properties`, for example `apiBaseUrl=http://192.168.1.23:8000/`
4. Sync and run again
