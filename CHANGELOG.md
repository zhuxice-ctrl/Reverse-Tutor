# Changelog

## v0.17.0 - 2026-05-19

- 新增 LLM 流式原语：`openai_text_stream()` 支持 SSE 解析并自动降级非流式；`anthropic_text_stream()` 处理 `content_block_delta`；统一路由器 `chat_text_stream()` 兼容 Mock 模式逐字输出（25-60ms 间隔）。
- 新增 Eval 专用调用 `chat_json_eval_only()`：只输出 evaluation/action/anchor_updates，不含 reply 文本，解决 JSON mode 与 streaming 互斥。
- Engine 流式分支：`run_turn` 新增 `opts.stream`，Eval call 与 Reply call 双路并行；流式 token 通过 `onStreamToken` / `onBubbleComplete` 回调推送；Mock 模式复用同一 `mockResponse` 保证一致性。
- 流式 UI 渲染：`getOrCreateStreamingBubble()` / `updateStreamingBubble()` / `finalizeStreamingBubble()` 实时更新气泡，带 ● 生成中指示器，AI 回复逐字出现。
- 用户多消息队列：生成中可连续发送，消息自动排队（按钮显示「发送 (N)」），`processMessageQueue()` 依次消费，聊天区显示 ⏳ N 条消息待发送。
- AI 多气泡输出：流式路径中 `shapeReplyBubbles(reply, 3)`，LLM 用 `|||` 分隔可生成多条连续消息气泡。

## v0.16.1 - 2026-05-19

- 修复后台通知：退到桌面后 LLM 继续生成，完成时弹出系统通知；新增原生通知插件，设置页可直达通知开关。
- 修复输入法光标跳转：中文输入不再跳到末尾，输入过程中不触碰 textarea 样式，兼容华为鸿蒙 WebView。
- 新增消息长按菜单：引用回复、创建随笔、回档、删除，模仿 QQ 在气泡上方弹出，点击空白关闭。
- 替换应用图标与启动画面，减少启动白屏；聊天界面图标统一为 Lucide，主动对话改为分段控件。

## v0.16.0 - 2026-05-17

- 升级文档知识库：上传资料会进入检索、图谱和按需单支分析流程。
- 新增 TXT、Markdown、HTML、PPTX、EPUB 导入，继续支持 PDF 和 DOCX。
- 洞察图谱新增资料节点、章节节点、未解锁节点、诊断节点和随笔节点。
- 图谱节点支持编辑纠正、用户命名锁定和回顾聊天。
- 聊天消息支持长按或右键创建随笔，并同步显示在图谱中。
- 优化文档卡片、资料快照、节点简介和数理化文本显示，减少原文倾倒和噪声标题。

## v0.15.9 - 2026-05-17

- 设置页底部新增 QQ 群反馈入口，方便用户反馈问题和获取更新说明。
- GitHub 主页新增 QQ 群二维码和群号，并把交流群入口移动到页面底部。
- 放大 README 顶部展示图，并修正功能卡片小字的横向对齐。

## v0.15.8 - 2026-05-16

- 重做接口类型配置：现在明确分为 OpenAI 和 Anthropic 两类协议，不再把接口类型写成含糊的兼容模式。
- 更新 DeepSeek 预设：提供 OpenAI / Anthropic 两个入口，并把默认模型调整为 deepseek-v4-flash 和 deepseek-v4-pro。
- Android 后台 LLM 服务补齐 Anthropic Messages API 支持，让后台回复和前台测试走同一套协议语义。
- 替换 Capacitor 默认启动封面，并加入应用自己的进入动画。

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
- Added local PDF, DOCX, TXT, Markdown, HTML, PPTX, and EPUB import for source anchors. Files are parsed on device and are not uploaded.
- Added localStorage backup for LLM configuration and automatic restore when the app becomes visible or focused again.
- Built in the default GitHub `latest.json` update feed so users can check for APK updates without entering a URL.
- Refreshed PWA and Android app icons, including manifest and service-worker cache updates.
- Enabled Android HTTP and mixed-content access to support local or self-hosted LLM endpoints.
