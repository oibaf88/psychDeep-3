# PsychDeep Android local inference

This module is the native Android client for the mobile-local deployment.

## Runtime

It uses a prebuilt llama.cpp Android AAR from Maven Central. The current library documents GGUF loading from app-private storage and on-device chat completion; models are not bundled because of their size. The official llama.cpp Android documentation also supports an embedded Android binding and app-private GGUF model loading.

The app:
- imports a GGUF model into app-private storage;
- computes a SHA-256 checksum for the selected model;
- runs inference locally;
- stores the interaction in an offline SQLite queue;
- protects the session token and raw prompt marker with Android Keystore AES-GCM;
- uploads only event metadata, input hash and generated output;
- retries outbound HTTPS synchronization through WorkManager;
- never opens an inbound port and does not require Cloudflare Tunnel.

## Server

Default API:

https://psychdeep-api.onrender.com

The server endpoint is:

POST /api/v1/mobile/inference-events

Authentication uses the existing PsychDeep patient bearer token. The mobile client must never contain Anthropic, Supabase service-role, Render or Cloudflare secrets.

## Model selection

The first implementation deliberately uses user-supplied GGUF files instead of silently downloading model weights. This keeps model provenance explicit and avoids embedding multi-GB model files in the application.

For smaller devices, begin with a compact quantized model. llama.cpp's current Android documentation recommends keeping context sizes reasonable because excessive context can increase memory use.

## Build

Open mobile/android in Android Studio or build it from a machine with Android SDK/Gradle:

gradle --no-daemon :app:assembleDebug

Repository CI builds the debug APK automatically when this module changes.

## Important boundary

mobile-local is an additional inference mode. It does not replace:
- desktop LM Studio/local-tunnel;
- Anthropic;
- cloud-tuned inference;
- deterministic safety/risk logic.

No provider fallback is automatic.

## Future integration

The standalone native client is intentionally separated from the existing React web client. A later Capacitor/native bridge can expose the same local inference and queue contract to the web UI without making the browser directly access a phone-local HTTP server.
