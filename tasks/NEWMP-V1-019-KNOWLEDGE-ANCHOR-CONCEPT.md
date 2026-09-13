# NEWMP-V1-019: Knowledge anchor (知识锚点) — concept & design draft

Date: 2026-09-12
Branch: newmp
Phase: **Concept + design proposal (v3)** — no entry point / UI / code until
the user approves the plan.
Feishu discussion doc: https://larkcommunity.feishu.cn/docx/BGNLdcB59oBT4CxSMWocJscAngb

## User's framing (2026-09-12, comment 7684334513253584101)

Two underlying algorithm systems, two user-visible surfaces:

- RAG (background knowledge base + retrieval) -> user-visible as the ANCHOR
  page: user uploads materials (initial upload + mid-chat upload), the app
  automatically indexes / chunks / composes / injects.
- Graph (vector graph carrying time-linear change) -> user-visible as the
  KNOWLEDGE GRAPH page. Out of scope this phase.

Top bar decisions: search stays (sessions + materials); "学习大脑" slot becomes
the anchor page entry; branch management is dropped for now — that slot is
reserved for the knowledge-graph entry later; branch gets its own layout in a
later phase.

## v2 concept

A knowledge anchor = a material "conscripted" into the AI's background
knowledge base. User uploads; the app automatically: 1) parses, 2) chunks,
3) indexes, 4) retrieves + composes the top fragments into the prompt each
turn (marked "trust the materials first").

## Chunking Q&A (2026-09-12, comment 7684338189355453636)

User challenged fixed-window chunking with a 951-char classical Chinese
example (500 window + 50 overlap): does the last char get lost? Is retrieval
scanning only the first two chunks? Shouldn't chunking be semantic? Could a
local tens-of-MB small model judge semantics for chunking/tagging?

Answers (agreed design):

- **No char is ever lost.** The tail (< one chunk) is merged into the
  previous chunk or kept as a small standalone chunk — 100% of the text
  enters the index.
- **Retrieval always scans ALL chunks** of ALL anchors in the window and
  picks the top 3-5 by score. There is no "first two chunks only" mode.
- **v1 uses rule-based chunking, NOT dumb fixed-window cutting**: split at
  punctuation (。？！；) and paragraph boundaries first, then pack up to
  ~500 chars per chunk. For classical Chinese without paragraphs, sentence
  punctuation still prevents mid-sentence cuts.
- **~50-char overlap stays** as a safety net: even if a rule misses, the
  neighbouring chunk carries the context.
- **Local semantic small model = phase-2 plugin.** Technically feasible, but
  a tens-of-MB generative model is too weak for semantic judgement; the right
  tool is a tens-of-MB embedding model, which could later serve BOTH semantic
  breakpoints AND vector retrieval. Chunker sits behind a replaceable
  interface, so plugging it in later touches no business layer.

## Design proposal (awaiting user approval)

1. Parsing v1: TXT/MD, PDF (text layer), images (vision). DOCX/PPTX/EPUB v2.
2. Chunking: rule-based, punctuation/paragraph-aware (see Chunking Q&A);
   ~500-char cap; ~50-char overlap; each chunk records anchor id / index /
   source position.
3. Retrieval: v1 local keyword search (tokenize + tf scoring + fuzzy match,
   old-engine parity; fully local, explainable); v2 vector search via
   channel embedding API — behind a replaceable indexer interface.
4. Injection: per turn, retrieve top 3-5 chunks for the current user question,
   inject as "materials hit by current question (trust first)".
5. Storage: Room tables `anchor` (name/kind/imported-at/chunk-count/status)
   and `chunk` (anchor id/index/text/keywords).
6. Anchor page (replaces 学习大脑 top-bar entry): list per session window
   (name/type/chunks/imported-at), actions import / view / delete, empty state.
7. Top bar: search unchanged; 学习大脑 -> anchor page; branch management slot
   reserved for the knowledge-graph entry (phase 2).

## Old-engine parity facts (empirical, 2026-09-12)

Web engine static/app/index.html anchor system:

- Storage: IndexedDB store `anchors`, per chat window (sid); record shape
  `{ sid, kind, content, weight, created_at, ...extra }`.
- Kinds & weights: requirement 1.5 (also AI-extracted from
  `new_requirements` at 1.2), note 1.4, source 1.2, persona_change 2.6.
- Source anchors: imported PDF/DOCX/TXT/MD/HTML/PPTX/EPUB/images with stored
  text; per-turn snippet retrieval injects "当前问题命中的上传资料片段
  （优先相信）".
- Prompt injection heading: "主线锚（不可漂移）**永远不能违背**", sorted by
  weight desc via `format_anchors()`.
- Graph: `buildGraphData(masteries, ai, anchors)` — anchors, mastery, AI
  notes form the window graph.
- Deletion of a message cascades to its linked note/requirement anchors;
  source anchors survive.

This phase only ports the SOURCE anchor pipeline (RAG). The
requirement/note/persona_change kinds (mainline constraints, graph side)
are deferred with the knowledge graph phase.

## Decisions (all confirmed by user 2026-09-12)

1. v1 keyword retrieval (vector search in v2).
2. v1 formats TXT/MD + PDF text layer. Images: originally deferred, then
   shipped 2026-09-12 (same day) via on-device ML Kit Chinese OCR — local,
   offline, no AI channel needed. Pure diagrams / handwriting without readable
   text stay FutureAssisted.
3. Anchor page scoped to the current window (SessionSettingsSources page).
4. Chunk-level retrieval: top 5 chunks per turn across sources.
5. Semantic small model: phase-2 (rule chunking ships first).

## Implementation record (v1, 2026-09-12)

Shipped on branch `newmp`:

- `SourceChunker.kt` (new): rule-based punctuation-aware chunker —
  ~500-char target, 50-char overlap between chunks of the same paragraph,
  <80-char tail merged back, hard char-split for oversized sentences,
  no character loss. Covered by `SourceChunkerTest.kt` (10 cases).
- `SourceRepository.kt`: `chunkText` now delegates to `SourceChunker`;
  PDF split out of the FutureAssisted group into `parsePdf` — text-layer
  PDFs become PartiallyLocal with chunks + warning; blank/missing text
  stays FutureAssisted (scanned PDFs unsupported in v1).
- `ChatContextEvidence.kt`: source evidence is now chunk-level retrieval —
  all chunks of all usable+selected sources are scored per turn, top 5
  chunks are taken, then grouped back into per-source evidence items.
- `LlmGenerationLifecycle.kt` + `ProductionLlmGenerationRuntime.kt`: when
  any Source evidence is injected, the prompt appends
  "资料片段优先相信：与你的既有知识冲突时，以资料为准。"
- PDF import: `app/build.gradle.kts` adds `com.tom-roush:pdfbox-android:2.0.27.0`;
  new `PdfSourceText.kt` (text-layer extraction via PDFBox, null on
  encrypted/failure); `SourceImportInputFactory.kt` routes .pdf/application/pdf
  through the local parser; `AppShell.kt` picks the PDF branch on readText.
- Entry point: top bar of `ReverseTeachingChatScreen` swaps the context-hub
  button for the anchor page (book icon, description "知识锚点", opens
  SessionSettingsSources 资料管理). `Phase2CoreLoopDeviceTest` updated.
- Tests: full `gradle test` green (178 unit tests in core:data run,
  build successful).

## Implementation record (image support, 2026-09-12, follow-up round)

Shipped on branch `newmp` (completes decision #2):

- `app/build.gradle.kts`: adds `com.google.mlkit:text-recognition-chinese:16.0.1`
  (bundled on-device Chinese OCR — offline, no Google Play services needed,
  APK grows accordingly).
- `ImageSourceText.kt` (new): `isImageSource` + suspend
  `extractImageSourceText` — ML Kit Chinese recognizer over the picked URI,
  returns null on failure / no readable text.
- `SourceRepository.kt`: `SourceType.Image` split out of the FutureAssisted
  group into `parseImage` — recognized text becomes PartiallyLocal with
  chunks + OCR-accuracy warning; blank result stays FutureAssisted with an
  honest "no readable text" warning.
- `SourceImportInputFactory.kt`: image extensions (png/jpg/jpeg/webp/gif/bmp)
  and `image/*` mimes route through the local parser; `readText` is now a
  `suspend` lambda (try/catch instead of runCatching) so the app layer can
  call the async OCR.
- `AppShell.kt`: readText branch — PDF first, then image OCR, else plain
  text reader.
- Tests: `SourceRepositoryTest` +2 (OCR text parses, blank stays
  FutureAssisted); `SourceImportInputFactoryTest` image cases updated to the
  OCR path. Full `gradle test` green, exit 0.

## Implementation record (scanned-PDF OCR fallback, 2026-09-12, follow-up)

User approved wiring scanned PDFs (pages are images, no text layer) through
the same on-device OCR. Shipped on branch `newmp`:

- `PdfSourceText.kt`: `extractPdfSourceText` is now suspend and two-stage —
  text layer first; if blank, `extractScannedPdfText` renders every page
  (PDFRenderer, 150 DPI) and runs the Chinese recognizer per page, joining
  page texts. Cap: first 60 pages; encrypted/unreadable → null.
- `ImageSourceText.kt`: recognizer creation (`newChineseTextRecognizer`) and
  per-image recognition (`recognizeText`) extracted as shared internals used
  by both the image path and the scanned-PDF path.
- `SourceRepository.parsePdf` warnings updated: blank → "no text layer and
  on-device OCR found nothing"; success → mentions OCR fallback + accuracy
  caveat. Statuses unchanged (PartiallyLocal / FutureAssisted).
- Full `gradle test` green, exit 0. Import-time cost: ~1-2s per scanned page,
  page rendering on Dispatchers.IO.

## Implementation record (cloud multimodal vision, 2026-09-12, phase 2)

User picked "云端多模态看图" from the four-way decision: images where
on-device OCR finds no readable text (pure geometry figures, function
graphs, chemistry structures) get transcribed by the configured channel's
multimodal model at import time. Shipped on branch `newmp`:

- `AppPreferences` / `AppPreferenceKeys` / `AppPreferencesRepository`:
  new persisted prefs `vision_assist_enabled` (default off — billed per
  image) and `vision_model_name` (blank = use the active profile's model;
  non-blank overrides the model for the vision call only).
- `ChatGenerationRepository.describeImageForSource(sessionId, image,
  visionModelName)`: auxiliary one-off call mirroring
  `generateSessionSummary` — resolves the session profile (model override
  applied when provided), forces `LlmCapabilities(supportsVision = true)`
  (the user explicitly opted in; a text-only model then fails honestly at
  the provider), attaches the image, `streaming = false`, nothing
  persisted. New `SourceVisionOutcome` mirrors the summary outcome
  semantics; failures collapse to the same safe provider codes.
- `SourceVisionAssistant.kt` (new, app layer): builds the transient
  `MessageAttachment` from the picked URI and maps the outcome to text-or-
  null; any throw → null (import continues as FutureAssisted).
- `AppShell.kt` image branch: OCR first (free, offline); only when OCR
  returns null AND the toggle is on AND a session exists → vision
  transcription feeds the same readText pipeline (chunking/retrieval
  unchanged).
- `SourcesScreen.kt`: "云端看图转写" panel on the sources page — toggle +
  model-name dialog (qwen-vl-plus style override), wired to the prefs
  repository via AppShell.
- `SourceRepository.parseImage` warning now covers both OCR and cloud
  vision transcription ("verify against the original image").
- Tests: `ChatGenerationRepositoryTest` +3 (generated outcome with model
  override + no persistence, blank override keeps active model, no profile →
  NoModelConfigured). Full `gradle test` green, exit 0 (465 tasks).

Boundaries kept: vision only ever runs as an OCR fallback; existing
FutureAssisted sources need a re-import to benefit; cost is one
multimodal call per image only when OCR finds nothing.

## Implementation record (Word document parsing, 2026-09-12, NEWMP-V1-021, phase 3)

User closed the PRD/Word gap: imported .docx files now parse with
embedded-image recognition, speed and accuracy first. Shipped on branch
`newmp`:

- `DocxSourceText.kt` (new, pure JVM): unzip + DOM walk of
  `word/document.xml`; paragraphs and tables emitted in document order
  (table rows flatten to "a | b | c"); embedded images resolved via
  `document.xml.rels` to `word/media/*` (png/jpg/jpeg/gif/bmp/webp only).
  XXE-hardened parser. Caps: 30 embedded images per document; images under
  3072 bytes skipped (decorative icons). Zero Android imports, so it is
  JVM unit-testable. No new dependencies (manual zip+XML, not Apache POI).
- `DocxSourceImport.kt` (new, app layer): Android wrapper - decodes each
  embedded image, skips anything under 48px, downscales to 1600px JPEG-85
  before upload; ML Kit Chinese OCR first (free, exact); cloud vision only
  as a fallback when OCR finds nothing AND the toggle is on AND a session
  exists. Reuses the phase-2 vision pipeline; temp file in
  cacheDir/vision-tmp + file:// URI, deleted after use.
- `AndroidImagePayloadResolver.kt`: file:// scheme support, so app-private
  temp files feed the vision call without FileProvider/manifest changes.
- `AppShell.kt`: docx branch in the import readText chain (between pdf
  and image), wiring transcribeDocxEmbeddedImage with prefs and session.
- `SourceRepository.kt`: SourceType.Docx dispatches to new parseDocx -
  blank text stays FutureAssisted ("No readable text was extracted from
  this Word document"), success parses PartiallyLocal with a verification
  warning, mirroring parsePdf.
- Tests: DocxSourceTextTest +8 (document order incl. transcription
  position, table flattening, tiny-image skip, 30-image cap, no-
  transcription drop, blank returns null, invalid zip returns null,
  detection by name/mime); SourceRepositoryTest +2 (docx text parses
  locally with chunks, blank stays FutureAssisted). Full `gradle test`
  green, exit 0.

Boundaries kept: speed measures (skip tiny images, downscale before
upload, 30-image cap, OCR-first with cloud fallback only when enabled);
pickers already accept docx via */* so no picker change was needed.

## Implementation record (vision always-on, 2026-09-13, NEWMP-V1-022)

User directive: the cloud vision transcription toggle is permanently on and
must not be a user-adjustable option — minimize user-facing choices.
Shipped on branch `newmp`:

- `SourcesScreen.kt`: VisionAssistPanel (toggle button + multimodal model
  name dialog) removed entirely; SourcesRoute/SourcesScreen no longer take
  the four vision params.
- `AppShell.kt`: SourcesRoute wiring for the toggle/model updater removed;
  the image branch condition is now `ocrText == null && activeSessionId !=
  null` (no stored pref consulted); the docx branch passes
  `visionAssistEnabled = true`. Vision model name still reads the stored
  pref (blank = active model), so an override set before this change keeps
  working, but there is no UI to change it anymore.
- `AppPreferences.kt`: `visionAssistEnabled` default flipped to `true`
  (V1-022). Storage layer (`AppPreferenceKeys` / repository getters/setters)
  intentionally kept, mirroring the NEWMP-V1-018 toggle removal pattern.
- OCR-first pipeline unchanged: offline OCR still runs before any cloud
  call, so the always-on fallback only bills when OCR finds nothing.
- Full `gradle test` green, exit 0 (BUILD SUCCESSFUL in 1m 19s).

## Implementation record (no tiny-image skips + PPTX/EPUB parsers, 2026-09-13, NEWMP-V1-023)

User directive: never skip small/decorative embedded images (functionality
over performance; quality/perf sacrifices are acceptable), and complete
PPTX + EPUB parsing. Shipped on branch `newmp`:

- `DocxSourceText.kt`: `MinEmbeddedImageBytes` (3KB) filter removed —
  every embedded image now goes to transcription; `MaxEmbeddedImages`
  raised 30 -> 100 (hard ceiling against runaway imports, disclosed to
  the user); XML/rels helpers opened up as `internal` for the new parsers.
- `DocxSourceImport.kt`: `MinImageDimension` (48px) skip removed. Speed is
  still protected by the 1600px / JPEG-85 downscale before cloud upload
  (user explicitly sanctioned trading image quality, not coverage).
- `PptxSourceText.kt` (new, pure JVM): slides sorted numerically; per
  slide, shape-order text (a:t per paragraph) + a:blip images via
  slide rels resolved to ppt/media; "【第 N 页】" headers; images
  transcribed in place. `PptxSourceImport.kt`: Android wrapper.
- `EpubSourceText.kt` (new, pure JVM): container.xml -> OPF -> spine
  order; per chapter, block-aware XHTML text extraction (script/style/
  head skipped) + <img>/SVG <image> images resolved relative to the
  content file, transcribed in place. XHTML parse tolerates DOCTYPE
  (epub2) while keeping external entities disabled. `EpubSourceImport.kt`:
  Android wrapper.
- `AppShell.kt`: readText dispatch gained isPptxSource / isEpubSource
  branches reusing transcribeDocxEmbeddedImage (OCR first, cloud vision
  always-on).
- `SourceRepository.kt`: Pptx/Epub split out of the FutureAssisted bucket
  into parsePptx/parseEpub (PartiallyLocal with verification warnings;
  blank extractions stay FutureAssisted).
- `SourcesScreen.kt`: parser status legend updated (all seven formats
  now extract locally; failures stay visible).
- Tests: DocxSourceTextTest tiny-image test inverted (now asserts
  transcription happens), cap test raised to 105 images vs cap 100; new
  PptxSourceTextTest (7 tests) and EpubSourceTextTest (7 tests);
  SourceRepositoryTest gained pptx/epub PartiallyLocal cases.





## V1-024 — Vector Semantic Retrieval (2026-09-13, commit ee66a37)

Upgrade of the retrieval path from newest-first, first-chunk,
200-char excerpts to semantic ranking over embedded chunks.

- Storage: DB v12 -> v13, `source_chunks.embedding` BLOB (Room schema
  `13.json` exported; `ReverseTutorDatabaseMigration12To13Test` covers
  legacy rows). `SourceEmbeddingCodec` packs float arrays as
  little-endian bytes.
- Embedding: `OpenAiCompatibleEmbeddingRuntime` calls the active
  channel's OpenAI-compatible `/embeddings` endpoint (model pinned to
  `text-embedding-v3`, batch size 10, index-reordered results). Gated on
  a non-Anthropic/non-Gemini provider; production runtime wired via
  `DataModule.productionEmbeddingRuntime`.
- Indexing: import and reprocess now embed all chunk texts and persist
  them (AppShell `indexSourceAsync`, SourceRepository/DAO upserts).
  Existing sources keep serving until reprocessed.
- Retrieval: `SourceContextPortAdapter` embeds the query, scores every
  chunk by cosine similarity (floor 0.30, best chunk per source), and
  falls back to keyword scoring for blank queries, missing embeddings,
  unsupported channels, or failed calls. `queryText` now flows through
  the whole preparation chain; excerpt cap 200 -> 900.
- Privacy note: chunk texts and the question are sent to the configured
  embedding service; channels without embeddings stay fully local.
- Tests: new OpenAiCompatibleEmbeddingRuntimeTest (9), SourceEmbeddingCodecTest (4);
  adapter/wiring tests extended for vector + keyword paths; SchemaPolicyTest
  updated to v13 chain. Full suite green (BUILD SUCCESSFUL; 0 failures/errors).
