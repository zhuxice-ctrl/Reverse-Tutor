# Changelog

## v0.15.7 - 2026-05-16

- Added background APK update downloads through an Android foreground service, so downloads can continue after leaving the app and notify when ready to install.
- Added automatic mirror fallback for update downloads before falling back to browser-based download behavior.
- Fixed the mobile LLM settings layout by replacing cramped two-column controls with full-width scrollable option chips.
- Tightened LLM provider summaries and helper copy to reduce visual clutter on small screens.

## v0.15.6 - 2026-05-16

- Refined the in-session LLM settings UI with a custom provider picker, segmented controls for API type and model capability, and quick model chips.
- Suppressed in-chat popups for foreground replies when the user is already viewing the chat.
- Added post-history reply instructions to keep role replies shorter, single-turn, and aligned with non-learning goals.
- Displayed user-initiated background-completed turns as regular chat replies instead of generic background replies.

## v0.15.5 - 2026-05-16

- Added proactive conversation controls with online, offline, and sleep modes. Online mode triggers naturally every 30-60 minutes, while offline mode stays silent.
- Changed in-app message popups and Android background notifications to show the actual LLM reply preview instead of generic text.
- Fixed in-app updates so Android downloads the APK natively and opens the system installer directly, with a first-run permission handoff when needed.
- Kept non-learning goals in goal-support mode so the assistant no longer forces every persona into a study flow.

## v0.12.0 - 2026-05-15

- Upgraded knowledge mastery into an interactive memory graph with canvas force layout, drag, pinch zoom, node selection, and bottom-sheet details.
- Added local Word/PDF import for source anchors. Files are parsed on device and are not uploaded.
- Added localStorage backup for LLM configuration and automatic restore when the app becomes visible or focused again.
- Built in the default GitHub `latest.json` update feed so users can check for APK updates without entering a URL.
- Refreshed PWA and Android app icons, including manifest and service-worker cache updates.
- Enabled Android HTTP and mixed-content access to support local or self-hosted LLM endpoints.
