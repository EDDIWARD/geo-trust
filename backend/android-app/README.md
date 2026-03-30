# Geo-Trust Android App

## Current scope

This project only covers the farmer registration flow:

- load bootstrap config and regions
- request location permission
- validate current location
- submit product registration
- show success or rejection result

## Notes

- backend base URL is controlled by `apiBaseUrl` in `gradle.properties`
- default value `http://10.0.2.2:8000/` is suitable for Android emulator
- for a physical phone, change it to `http://<your-pc-lan-ip>:8000/`
- this workspace does not currently include Gradle wrapper files
- local build verification was not completed here because `gradle` and `java` were not available in the shell environment

## Physical phone test

1. Start backend with:
   `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
2. Make sure phone and computer are on the same LAN
3. Set `apiBaseUrl` in `gradle.properties`, for example:
   `apiBaseUrl=http://192.168.1.23:8000/`
4. Sync and run again
