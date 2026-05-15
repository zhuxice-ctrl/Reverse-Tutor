# Background LLM Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Android keep generating the currently submitted LLM reply after the app goes to background, then notify the user and restore the reply when the app opens again.

**Architecture:** A small Capacitor plugin accepts a fully prepared chat-completion job from the WebView. An Android foreground service performs the OpenAI-compatible HTTP request, stores the parsed result in app-private SharedPreferences, and posts a notification. The WebView keeps IndexedDB as the source of truth and imports completed native jobs on startup/focus.

**Tech Stack:** Capacitor 6, Java Android foreground service, AndroidX notifications, WebView JavaScript, pytest text-level regression tests, Gradle APK build.

---

### Task 1: Regression Tests

**Files:**
- Create: `tests/test_android_background_llm.py`

- [x] Add tests asserting manifest foreground-service permissions, service declaration, custom plugin sources, and frontend bridge calls.
- [x] Run the tests and verify they fail before implementation.

### Task 2: Android Native Worker

**Files:**
- Create: `mobile/android/app/src/main/java/com/reversetutor/app/BackgroundLlmPlugin.java`
- Create: `mobile/android/app/src/main/java/com/reversetutor/app/BackgroundLlmService.java`
- Modify: `mobile/android/app/src/main/java/com/reversetutor/app/MainActivity.java`
- Modify: `mobile/android/app/src/main/AndroidManifest.xml`

- [ ] Implement plugin methods: `enqueueTurn`, `getCompletedTurns`, `clearCompletedTurn`, `isAvailable`.
- [ ] Implement a foreground service that performs one OpenAI-compatible request, stores result JSON, and posts a completion/failure notification.
- [ ] Register plugin in `MainActivity`.

### Task 3: Frontend Integration

**Files:**
- Modify: `static/app/index.html`

- [ ] Add `NativeBackgroundLlm` wrapper.
- [ ] In `ENGINE.run_turn`, after writing the user message and building system/messages, enqueue a native job when available and live LLM config exists.
- [ ] Add startup/focus import that writes completed native assistant replies into IndexedDB.
- [ ] Keep browser/PWA fallback unchanged.

### Task 4: Verification

**Commands:**
- `pytest -q`
- JavaScript inline parse check for `static/app/index.html`, `mobile/www/index.html`, and Android assets.
- `npm run build:apk` from `mobile`.

